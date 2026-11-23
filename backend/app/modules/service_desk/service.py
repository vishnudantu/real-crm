"""Service-desk domain services: SLA clock, comments, assignment, status flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.customers.models import Contact
from app.modules.postsales.models import SaleBooking
from app.modules.service_desk import repository
from app.modules.service_desk.exceptions import (
    CommentBodyError,
    InvalidStatusTransitionError,
    TicketAssigneeError,
    TicketNotFoundError,
)
from app.modules.service_desk.models import (
    Ticket,
    TicketCategory,
    TicketComment,
    TicketPriority,
    TicketStatus,
)
from app.modules.service_desk.schemas import (
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
)
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
    session.commit()
    session.refresh(ticket)
    return ticket


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
