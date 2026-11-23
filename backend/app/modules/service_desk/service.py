"""Service-desk domain services: SLA clock, comments, assignment, status flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.buyer_docs.service import resolve_buyer_contact
from app.modules.customers.models import Contact
from app.modules.postsales.models import SaleBooking
from app.modules.service_desk import repository
from app.modules.service_desk.exceptions import (
    ArticleNotFoundError,
    CommentBodyError,
    InvalidStatusTransitionError,
    SurveyNotOpenError,
    TicketAssigneeError,
    TicketNotFoundError,
)
from app.modules.service_desk.models import (
    KbArticle,
    KbArticleStatus,
    Ticket,
    TicketCategory,
    TicketComment,
    TicketPriority,
    TicketSatisfaction,
    TicketStatus,
)
from app.modules.service_desk.schemas import (
    AgentSuggestionResponse,
    CsatPeriodStat,
    CsatStatsResponse,
    KbArticleListResponse,
    KbArticleResponse,
    OpenTicketTrendPoint,
    TicketCommentResponse,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
)
from app.modules.service_desk.search import SuggestionCandidate, top_suggestions
from app.modules.users.models import Role, RoleName, User

# Response/resolution SLA deadline per priority, measured from creation.
SLA_BY_PRIORITY: dict[TicketPriority, timedelta] = {
    TicketPriority.URGENT: timedelta(hours=4),
    TicketPriority.HIGH: timedelta(hours=24),
    TicketPriority.MEDIUM: timedelta(hours=72),
    TicketPriority.LOW: timedelta(hours=168),
}

# Explicit allowed status transitions. RESOLVED only closes (no reopening in
# this foundation); OPEN may jump straight to CLOSED for misfiled tickets.
ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.OPEN: frozenset(
        {
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_ON_CUSTOMER,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
        }
    ),
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.WAITING_ON_CUSTOMER, TicketStatus.RESOLVED}
    ),
    TicketStatus.WAITING_ON_CUSTOMER: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED}
    ),
    TicketStatus.RESOLVED: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
}

# A ticket is "breached" while unresolved and past its SLA deadline.
BREACH_STATUSES = frozenset({TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value})

STAFF_ROLES = (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value)

DEFAULT_LIMIT = 50

# SQLite has no advisory locks; guard number allocation in-process for the
# test/dev engine so concurrent creates never collide on TCK numbers.
_ticket_issue_lock = Lock()


def _get_ticket(session: Session, *, ticket_id: UUID, tenant_id: UUID) -> Ticket:
    ticket = repository.get_ticket(session, ticket_id, tenant_id=tenant_id)
    if ticket is None:
        raise TicketNotFoundError()
    return ticket


def _validate_links(session: Session, *, tenant_id: UUID, contact_id, booking_id) -> None:
    """Optional links must reference rows in the same tenant."""
    if contact_id is not None:
        contact = session.scalar(
            select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
        )
        if contact is None:
            raise TicketAssigneeError("The linked contact must exist in your organization.")
    if booking_id is not None:
        booking = session.scalar(
            select(SaleBooking).where(
                SaleBooking.id == booking_id, SaleBooking.tenant_id == tenant_id
            )
        )
        if booking is None:
            raise TicketAssigneeError("The linked booking must exist in your organization.")


def create_ticket(
    session: Session,
    *,
    actor: User,
    subject: str,
    description: str,
    category: TicketCategory = TicketCategory.GENERAL,
    priority: TicketPriority = TicketPriority.MEDIUM,
    contact_id: UUID | None = None,
    booking_id: UUID | None = None,
) -> Ticket:
    """Create an OPEN ticket with a sequential TCK number and SLA deadline."""

    _validate_links(session, tenant_id=actor.tenant_id, contact_id=contact_id, booking_id=booking_id)
    now = datetime.now(UTC)

    def issue() -> Ticket:
        repository.lock_ticket_allocation(session, tenant_id=actor.tenant_id)
        number = repository.next_ticket_number(session, tenant_id=actor.tenant_id)
        ticket = Ticket(
            tenant_id=actor.tenant_id,
            ticket_number=number,
            subject=subject,
            description=description,
            category=category.value,
            priority=priority.value,
            status=TicketStatus.OPEN.value,
            contact_id=contact_id,
            booking_id=booking_id,
            created_by_id=actor.id,
            sla_due_at=now + SLA_BY_PRIORITY[priority],
            created_at=now,
            updated_at=now,
        )
        session.add(ticket)
        session.flush()  # materialize ticket.id before any reference
        session.commit()
        session.refresh(ticket)
        return ticket

    try:
        if session.get_bind().dialect.name == "sqlite":
            with _ticket_issue_lock:
                return issue()
        return issue()
    except IntegrityError as exc:
        session.rollback()
        raise TicketAssigneeError(
            "Ticket creation conflicted with a concurrent request. Retry the request."
        ) from exc


def _staff_user(session: Session, *, tenant_id: UUID, user_id: UUID) -> User:
    user = session.scalar(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(
            User.tenant_id == tenant_id,
            User.id == user_id,
            User.is_active.is_(True),
            Role.name.in_(STAFF_ROLES),
        )
    )
    if user is None:
        raise TicketAssigneeError()
    return user


def add_comment(
    session: Session,
    *,
    actor: User,
    ticket_id: UUID,
    body: str,
    is_internal: bool = False,
) -> TicketComment:
    """Append a comment; the first staff comment stamps first_response_at."""

    ticket = _get_ticket(session, ticket_id=ticket_id, tenant_id=actor.tenant_id)
    body = body.strip()
    if not 1 <= len(body) <= 4000:
        raise CommentBodyError()
    now = datetime.now(UTC)
    comment = TicketComment(
        tenant_id=actor.tenant_id,
        ticket_id=ticket.id,
        author_id=actor.id,
        body=body,
        is_internal=is_internal,
        created_at=now,
    )
    session.add(comment)
    if ticket.first_response_at is None:
        ticket.first_response_at = now
        ticket.updated_at = now
        session.add(ticket)
    session.flush()
    session.commit()
    session.refresh(comment)
    return comment


def assign_ticket(
    session: Session, *, actor: User, ticket_id: UUID, assigned_to_id: UUID
) -> Ticket:
    ticket = _get_ticket(session, ticket_id=ticket_id, tenant_id=actor.tenant_id)
    assignee = _staff_user(session, tenant_id=actor.tenant_id, user_id=assigned_to_id)
    ticket.assigned_to_id = assignee.id
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def update_status(
    session: Session,
    *,
    actor: User,
    ticket_id: UUID,
    new_status: TicketStatus,
    resolution_note: str | None = None,
) -> Ticket:
    ticket = _get_ticket(session, ticket_id=ticket_id, tenant_id=actor.tenant_id)
    current = TicketStatus(ticket.status)
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStatusTransitionError(current.value, new_status.value)
    now = datetime.now(UTC)
    ticket.status = new_status.value
    ticket.updated_at = now
    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = now
    if resolution_note is not None:
        ticket.resolution_note = resolution_note
    session.add(ticket)
    if new_status == TicketStatus.CLOSED:
        ticket.closed_at = now
        _open_survey(session, ticket=ticket, now=now)
    session.commit()
    session.refresh(ticket)
    return ticket


def _open_survey(session: Session, *, ticket: Ticket, now: datetime) -> TicketSatisfaction:
    """Ensure a closed ticket has exactly one unanswered CSAT survey row.

    Idempotent: re-closing (or a race) never stacks duplicate surveys, because
    the tenant+ticket unique key plus this pre-check keep one row per ticket.
    """
    existing = repository.get_satisfaction(
        session, ticket_id=ticket.id, tenant_id=ticket.tenant_id
    )
    if existing is not None:
        return existing
    survey = TicketSatisfaction(
        tenant_id=ticket.tenant_id, ticket_id=ticket.id, created_at=now
    )
    session.add(survey)
    session.flush()
    return survey


def list_tickets(
    session: Session,
    *,
    actor: User,
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    assigned_to_id: UUID | None = None,
    breach_only: bool = False,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> TicketListResponse:
    conditions = [Ticket.tenant_id == actor.tenant_id]
    if status is not None:
        conditions.append(Ticket.status == status.value)
    if priority is not None:
        conditions.append(Ticket.priority == priority.value)
    if assigned_to_id is not None:
        conditions.append(Ticket.assigned_to_id == assigned_to_id)
    if breach_only:
        conditions.append(Ticket.status.in_(BREACH_STATUSES))
        conditions.append(Ticket.sla_due_at < datetime.now(UTC))

    total = session.scalar(select(func.count()).select_from(Ticket).where(*conditions)) or 0
    items = list(
        session.scalars(
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc(), Ticket.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_ticket_detail(
    session: Session, *, actor: User, ticket_id: UUID
) -> TicketDetailResponse:
    ticket = _get_ticket(session, ticket_id=ticket_id, tenant_id=actor.tenant_id)
    return TicketDetailResponse.model_validate(ticket)


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #


def create_article(
    session: Session,
    *,
    actor: User,
    title: str,
    body_markdown: str,
    category: str,
    slug: str | None = None,
) -> KbArticle:
    """Draft a KB article; the slug is derived from the title when omitted."""
    resolved_slug = repository.unique_article_slug(
        session, tenant_id=actor.tenant_id, title=title, base=slug
    )
    now = datetime.now(UTC)
    article = KbArticle(
        tenant_id=actor.tenant_id,
        title=title,
        slug=resolved_slug,
        body_markdown=body_markdown,
        category=category,
        status=KbArticleStatus.DRAFT.value,
        author_id=actor.id,
        created_at=now,
        updated_at=now,
    )
    session.add(article)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise TicketAssigneeError(
            "The slug collided with a concurrent article. Retry the request."
        ) from exc
    session.refresh(article)
    return article


def update_article(
    session: Session,
    *,
    actor: User,
    article_id: UUID,
    title: str | None = None,
    body_markdown: str | None = None,
    category: str | None = None,
) -> KbArticle:
    article = repository.get_article(session, article_id=article_id, tenant_id=actor.tenant_id)
    if article is None:
        raise ArticleNotFoundError()
    if title is not None:
        article.title = title
    if body_markdown is not None:
        article.body_markdown = body_markdown
    if category is not None:
        article.category = category
    # Slugs stay stable across edits so published deep links survive.
    article.updated_at = datetime.now(UTC)
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def publish_article(session: Session, *, actor: User, article_id: UUID) -> KbArticle:
    """Flip an article to PUBLISHED; republishing is idempotent."""
    article = repository.get_article(session, article_id=article_id, tenant_id=actor.tenant_id)
    if article is None:
        raise ArticleNotFoundError()
    now = datetime.now(UTC)
    if article.status != KbArticleStatus.PUBLISHED.value:
        article.status = KbArticleStatus.PUBLISHED.value
        article.published_at = now
        article.updated_at = now
        session.add(article)
        session.commit()
    session.refresh(article)
    return article


def list_articles(
    session: Session,
    *,
    actor: User,
    article_status: KbArticleStatus | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> KbArticleListResponse:
    items, total = repository.list_articles(
        session,
        tenant_id=actor.tenant_id,
        article_status=article_status.value if article_status else None,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    return KbArticleListResponse(
        items=[KbArticleResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_published_article(session: Session, *, actor: User, article_id: UUID) -> KbArticle:
    """Buyer read path: drafts answer 404 like missing articles — no existence leak."""
    article = repository.get_article(session, article_id=article_id, tenant_id=actor.tenant_id)
    if article is None or article.status != KbArticleStatus.PUBLISHED.value:
        raise ArticleNotFoundError()
    return article


def search_published_articles(
    session: Session,
    *,
    actor: User,
    search: str | None = None,
    category: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> KbArticleListResponse:
    items, total = repository.list_articles(
        session,
        tenant_id=actor.tenant_id,
        article_status=KbArticleStatus.PUBLISHED.value,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    return KbArticleListResponse(
        items=[KbArticleResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------------- #
# CSAT
# --------------------------------------------------------------------------- #


def _buyer_ticket(session: Session, *, actor: User, ticket_id: UUID) -> Ticket:
    """Resolve one of the actor's OWN tickets through the server-side contact.

    Exact /buyer-docs/mine semantics: the Contact is derived from the
    authenticated account (never from the request), and a missing contact,
    a missing ticket, or a ticket whose ``contact_id`` is not the resolved
    contact all answer the same 404 — existence of other tickets is never
    disclosed. Tickets raised without a contact link stay staff-only.
    """
    contact = resolve_buyer_contact(session, actor)
    if contact is None:
        raise TicketNotFoundError()
    ticket = repository.get_ticket(session, ticket_id, tenant_id=actor.tenant_id)
    if ticket is None or ticket.contact_id != contact.id:
        raise TicketNotFoundError()
    return ticket


def list_my_tickets(
    session: Session,
    *,
    actor: User,
    status: TicketStatus | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> TicketListResponse:
    """The buyer's own ticket queue: tenant + server-resolved contact scoped."""
    contact = resolve_buyer_contact(session, actor)
    if contact is None:
        raise TicketNotFoundError()
    conditions = [Ticket.tenant_id == actor.tenant_id, Ticket.contact_id == contact.id]
    if status is not None:
        conditions.append(Ticket.status == status.value)
    total = session.scalar(select(func.count()).select_from(Ticket).where(*conditions)) or 0
    items = list(
        session.scalars(
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc(), Ticket.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return TicketListResponse(
        items=[TicketResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_my_ticket_detail(session: Session, *, actor: User, ticket_id: UUID) -> TicketDetailResponse:
    """One of the buyer's own tickets with internal staff notes filtered out.

    The survey row rides along so the portal can render the CSAT widget;
    ``is_internal`` comments are never serialized on this surface.
    """
    ticket = _buyer_ticket(session, actor=actor, ticket_id=ticket_id)
    detail = TicketDetailResponse.model_validate(ticket)
    public = [
        TicketCommentResponse.model_validate(comment)
        for comment in ticket.comments
        if not comment.is_internal
    ]
    return detail.model_copy(update={"comments": public})


def submit_satisfaction(
    session: Session,
    *,
    actor: User,
    ticket_id: UUID,
    rating: int,
    feedback: str | None = None,
) -> TicketSatisfaction:
    """Record (or replace) the CSAT rating for the buyer's own closed ticket.

    Only CLOSED tickets accept ratings — the close transition opens a survey
    row, and tickets closed before the feature lazily open one here. A rating
    on an open ticket is 409; anything not owned is 404. Re-submission updates
    the same row so customers can revise their answer.
    """
    ticket = _buyer_ticket(session, actor=actor, ticket_id=ticket_id)
    if ticket.status != TicketStatus.CLOSED.value:
        raise SurveyNotOpenError()
    now = datetime.now(UTC)
    survey = _open_survey(session, ticket=ticket, now=now)
    survey.rating = rating
    survey.feedback = feedback
    survey.responded_at = now
    session.add(survey)
    session.commit()
    session.refresh(survey)
    return survey


def get_satisfaction_for_buyer_ticket(
    session: Session, *, actor: User, ticket_id: UUID
) -> TicketSatisfaction | None:
    """Read a buyer's own survey row (None = survey open but unanswered)."""
    ticket = _buyer_ticket(session, actor=actor, ticket_id=ticket_id)
    return repository.get_satisfaction(session, ticket_id=ticket.id, tenant_id=ticket.tenant_id)


CSAT_PERIODS: dict[str, timedelta] = {
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "365d": timedelta(days=365),
}

_HISTOGRAM_BUCKETS = (1, 2, 3, 4, 5)


def csat_stats(session: Session, *, actor: User, period: str = "90d") -> CsatStatsResponse:
    """Average CSAT by period plus open/close ticket trends for the desk board.

    Surveys are bucketed by their creation month (the close date), not the
    response date, so period buckets describe cohorts of closed work; the
    average is over rated surveys only, and response_rate over all surveys.
    """
    window = CSAT_PERIODS.get(period)
    if window is None:
        raise TicketAssigneeError("period must be one of 30d, 90d or 365d.")
    since = datetime.now(UTC) - window
    survey_rows, ticket_rows = repository.csat_aggregates(
        session, tenant_id=actor.tenant_id, since=since
    )

    histogram = {bucket: 0 for bucket in _HISTOGRAM_BUCKETS}
    by_month: dict[str, list[int | None]] = {}
    total = 0
    rated = 0
    rating_sum = 0
    for rating, _responded_at, created_at in survey_rows:
        total += 1
        bucket = created_at.strftime("%Y-%m")
        by_month.setdefault(bucket, []).append(rating)
        if rating is not None:
            rated += 1
            rating_sum += rating
            histogram[int(rating)] += 1

    periods = []
    for bucket in sorted(by_month):
        ratings = [r for r in by_month[bucket] if r is not None]
        periods.append(
            CsatPeriodStat(
                period=bucket,
                surveys=len(by_month[bucket]),
                rated=len(ratings),
                average_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            )
        )

    opened_by_month: dict[str, int] = {}
    closed_by_month: dict[str, int] = {}
    for created_at, closed_at in ticket_rows:
        opened_by_month[created_at.strftime("%Y-%m")] = (
            opened_by_month.get(created_at.strftime("%Y-%m"), 0) + 1
        )
        if closed_at is not None:
            key = closed_at.strftime("%Y-%m")
            closed_by_month[key] = closed_by_month.get(key, 0) + 1
    trends = [
        OpenTicketTrendPoint(
            period=bucket,
            opened=opened_by_month.get(bucket, 0),
            closed=closed_by_month.get(bucket, 0),
        )
        for bucket in sorted(set(opened_by_month) | set(closed_by_month))
    ]

    status_counts = repository.open_ticket_counts(session, tenant_id=actor.tenant_id)
    unresolved = sum(status_counts.get(state, 0) for state in OPEN_TICKET_STATUSES)
    return CsatStatsResponse(
        period=period,
        surveys=total,
        rated=rated,
        average_rating=round(rating_sum / rated, 2) if rated else None,
        response_rate=round(rated / total, 4) if total else None,
        rating_histogram=histogram,
        unresolved_tickets=unresolved,
        periods=periods,
        ticket_trends=trends,
    )


OPEN_TICKET_STATUSES = (
    TicketStatus.OPEN.value,
    TicketStatus.IN_PROGRESS.value,
    TicketStatus.WAITING_ON_CUSTOMER.value,
)


# --------------------------------------------------------------------------- #
# Agent suggestions
# --------------------------------------------------------------------------- #


def ticket_suggestions(
    session: Session, *, actor: User, ticket_id: UUID
) -> list[AgentSuggestionResponse]:
    """Top-3 published KB articles matching the ticket subject words.

    Fetches the tenant's published corpus (bounded by the repository) and
    ranks in pure Python (search.top_suggestions) so scoring stays testable
    without a database.
    """
    ticket = _get_ticket(session, ticket_id=ticket_id, tenant_id=actor.tenant_id)
    articles = repository.published_articles_for_suggestions(
        session, tenant_id=actor.tenant_id
    )
    candidates = [
        SuggestionCandidate(
            article_id=article.id,
            title=article.title,
            slug=article.slug,
            category=article.category,
            body_markdown=article.body_markdown,
        )
        for article in articles
    ]
    return [
        AgentSuggestionResponse(
            article_id=match.article_id,
            title=match.title,
            slug=match.slug,
            category=match.category,
            score=score,
        )
        for match, score in top_suggestions(ticket.subject, candidates)
    ]
