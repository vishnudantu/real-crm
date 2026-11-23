"""Service desk API: ticket queue, SLA breach filter, comments, assignment.

Staff-role scoped (ADMIN and SALES_EXECUTIVE) for the queue and knowledge
base authoring, plus buyer-portal surfaces that admit BUYER (and staff):
the help center (published KB search/list/read) and CSAT rating for the
buyer's own closed tickets. CSAT follows the buyer_docs /mine pattern —
identity is resolved server-side from the authenticated account to its
Contact and answers 404 rather than 403 on unresolvable identity or foreign
tickets, so existence is never disclosed.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.service_desk import service
from app.modules.service_desk.models import (
    KbArticleStatus,
    TicketPriority,
    TicketStatus,
)
from app.modules.service_desk.schemas import (
    AgentSuggestionResponse,
    CsatStatsResponse,
    KbArticleCreateRequest,
    KbArticleListResponse,
    KbArticleResponse,
    KbArticleUpdateRequest,
    SatisfactionSubmitRequest,
    TicketAssignRequest,
    TicketCommentCreateRequest,
    TicketCommentResponse,
    TicketCreateRequest,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
    TicketSatisfactionResponse,
    TicketStatusUpdateRequest,
)
from app.modules.users.models import User
from app.modules.users.permissions import SERVICE_DESK_USE

router = APIRouter(prefix="/service-desk", tags=["service-desk"])
StaffUser = Annotated[User, Depends(require_permission(SERVICE_DESK_USE))]
BuyerPortalUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE, RoleName.BUYER)),
]
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    payload: TicketCreateRequest, actor: StaffUser, db: Database
) -> TicketResponse:
    """Open a support ticket; the TCK number and SLA deadline are assigned here."""

    ticket = service.create_ticket(
        db,
        actor=actor,
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        contact_id=payload.contact_id,
        booking_id=payload.booking_id,
    )
    return TicketResponse.model_validate(ticket)


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets(
    actor: StaffUser,
    db: Database,
    ticket_status: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
    assigned_to_id: UUID | None = None,
    breach_only: Annotated[bool, Query(description="Only unresolved tickets past their SLA deadline")] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = service.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketListResponse:
    return service.list_tickets(
        db,
        actor=actor,
        status=ticket_status,
        priority=priority,
        assigned_to_id=assigned_to_id,
        breach_only=breach_only,
        limit=limit,
        offset=offset,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket(ticket_id: UUID, actor: StaffUser, db: Database) -> TicketDetailResponse:
    return service.get_ticket_detail(db, actor=actor, ticket_id=ticket_id)


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=TicketCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    ticket_id: UUID,
    payload: TicketCommentCreateRequest,
    actor: StaffUser,
    db: Database,
) -> TicketCommentResponse:
    """Append a comment to the thread; the first staff comment starts the SLA
    first-response clock."""

    return service.add_comment(
        db, actor=actor, ticket_id=ticket_id, body=payload.body, is_internal=payload.is_internal
    )


@router.post("/tickets/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: UUID, payload: TicketAssignRequest, actor: StaffUser, db: Database
) -> TicketResponse:
    ticket = service.assign_ticket(
        db, actor=actor, ticket_id=ticket_id, assigned_to_id=payload.assigned_to_id
    )
    return TicketResponse.model_validate(ticket)


@router.patch("/tickets/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusUpdateRequest,
    actor: StaffUser,
    db: Database,
) -> TicketResponse:
    """Move the ticket through the status machine.

    Moving to CLOSED also opens the CSAT survey row for the ticket (idempotent:
    re-closing never stacks duplicate surveys).
    """

    ticket = service.update_status(
        db,
        actor=actor,
        ticket_id=ticket_id,
        new_status=payload.status,
        resolution_note=payload.resolution_note,
    )
    return TicketResponse.model_validate(ticket)


# --------------------------------------------------------------------------- #
# Knowledge base — staff authoring surface
# --------------------------------------------------------------------------- #


@router.post(
    "/kb/articles",
    response_model=KbArticleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_kb_article(
    payload: KbArticleCreateRequest, actor: StaffUser, db: Database
) -> KbArticleResponse:
    """Draft a knowledge-base article (status DRAFT until published)."""

    article = service.create_article(
        db,
        actor=actor,
        title=payload.title,
        body_markdown=payload.body_markdown,
        category=payload.category,
        slug=payload.slug,
    )
    return KbArticleResponse.model_validate(article)


@router.get("/kb/articles", response_model=KbArticleListResponse)
def list_kb_articles(
    actor: StaffUser,
    db: Database,
    article_status: Annotated[KbArticleStatus | None, Query(alias="status")] = None,
    category: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = service.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KbArticleListResponse:
    """Staff list over every status; ``search`` is simple case-insensitive LIKE."""

    return service.list_articles(
        db,
        actor=actor,
        article_status=article_status,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/kb/articles/{article_id}", response_model=KbArticleResponse)
def update_kb_article(
    article_id: UUID,
    payload: KbArticleUpdateRequest,
    actor: StaffUser,
    db: Database,
) -> KbArticleResponse:
    article = service.update_article(
        db,
        actor=actor,
        article_id=article_id,
        title=payload.title,
        body_markdown=payload.body_markdown,
        category=payload.category,
    )
    return KbArticleResponse.model_validate(article)


@router.post("/kb/articles/{article_id}/publish", response_model=KbArticleResponse)
def publish_kb_article(
    article_id: UUID, actor: StaffUser, db: Database
) -> KbArticleResponse:
    """Publish an article, making it visible to the buyer help center."""

    article = service.publish_article(db, actor=actor, article_id=article_id)
    return KbArticleResponse.model_validate(article)


@router.get("/tickets/{ticket_id}/suggestions", response_model=list[AgentSuggestionResponse])
def ticket_kb_suggestions(
    ticket_id: UUID, actor: StaffUser, db: Database
) -> list[AgentSuggestionResponse]:
    """Top-3 published articles matching this ticket's subject words."""

    return service.ticket_suggestions(db, actor=actor, ticket_id=ticket_id)


@router.get("/stats/csat", response_model=CsatStatsResponse)
def csat_stats(
    actor: StaffUser,
    db: Database,
    period: Annotated[str, Query(description="Rollup window: 30d, 90d or 365d")] = "90d",
) -> CsatStatsResponse:
    """Average CSAT per month plus opened/closed ticket trends for the board."""

    return service.csat_stats(db, actor=actor, period=period)


# --------------------------------------------------------------------------- #
# Buyer portal surfaces — help center and CSAT
#
# Help center reads are tenant + PUBLISHED scoped; drafts are invisible (404),
# never 403, so unpublished work is not disclosed to the portal. CSAT routes
# resolve the buyer's Contact server-side like /buyer-docs/mine: ratings apply
# only to tickets linked to that contact and only once the ticket is CLOSED.
# --------------------------------------------------------------------------- #


@router.get("/help/articles", response_model=KbArticleListResponse)
def search_help_articles(
    buyer: BuyerPortalUser,
    db: Database,
    search: str | None = Query(default=None, max_length=200),
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = service.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KbArticleListResponse:
    """Buyer help-center search over PUBLISHED articles (simple LIKE search)."""

    return service.search_published_articles(
        db, actor=buyer, search=search, category=category, limit=limit, offset=offset
    )


@router.get("/help/articles/{article_id}", response_model=KbArticleResponse)
def read_help_article(
    article_id: UUID, buyer: BuyerPortalUser, db: Database
) -> KbArticleResponse:
    article = service.get_published_article(db, actor=buyer, article_id=article_id)
    return KbArticleResponse.model_validate(article)


@router.get("/mine/tickets", response_model=TicketListResponse)
def list_my_tickets(
    buyer: BuyerPortalUser,
    db: Database,
    ticket_status: Annotated[TicketStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = service.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TicketListResponse:
    """The buyer's own tickets (linked through the server-resolved contact)."""

    return service.list_my_tickets(
        db, actor=buyer, status=ticket_status, limit=limit, offset=offset
    )


@router.get("/mine/tickets/{ticket_id}", response_model=TicketDetailResponse)
def read_my_ticket(
    ticket_id: UUID, buyer: BuyerPortalUser, db: Database
) -> TicketDetailResponse:
    """One of the buyer's own tickets, with the public thread and survey state.

    Internal staff notes stay hidden on this surface; the survey row (if any)
    is included so the portal can render the CSAT widget.
    """

    return service.get_my_ticket_detail(db, actor=buyer, ticket_id=ticket_id)


@router.put(
    "/mine/tickets/{ticket_id}/satisfaction",
    response_model=TicketSatisfactionResponse,
)
def submit_my_ticket_satisfaction(
    ticket_id: UUID,
    payload: SatisfactionSubmitRequest,
    buyer: BuyerPortalUser,
    db: Database,
) -> TicketSatisfactionResponse:
    """Rate a closed ticket of the buyer's own (1-5 plus optional feedback).

    Re-submission replaces the previous rating, so a customer can revise
    their answer until the survey window ends. Tickets that are not CLOSED,
    belong to someone else, or resolve to no contact all answer 404.
    """

    survey = service.submit_satisfaction(
        db,
        actor=buyer,
        ticket_id=ticket_id,
        rating=payload.rating,
        feedback=payload.feedback,
    )
    return TicketSatisfactionResponse.model_validate(survey)


@router.get(
    "/mine/tickets/{ticket_id}/satisfaction",
    response_model=TicketSatisfactionResponse,
)
def read_my_ticket_satisfaction(
    ticket_id: UUID, buyer: BuyerPortalUser, db: Database
) -> TicketSatisfactionResponse:
    """The buyer's current rating for one of their closed tickets.

    404 when no survey exists yet (the ticket is not closed); the detail
    payload's ``satisfaction`` field is the same row with the same semantics.
    """

    survey = service.get_satisfaction_for_buyer_ticket(
        db, actor=buyer, ticket_id=ticket_id
    )
    if survey is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No satisfaction survey for this ticket."
        )
    return TicketSatisfactionResponse.model_validate(survey)
