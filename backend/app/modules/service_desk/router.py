"""Service desk API: ticket queue, SLA breach filter, comments, assignment.

Staff-role scoped for now (ADMIN and SALES_EXECUTIVE). A buyer self-service
portal — where a customer raises and tracks only their own tickets — arrives
with the buyer-passport work later and will reuse these services through a
tenant+contact predicate; until then buyers receive no access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.service_desk import service
from app.modules.service_desk.models import TicketCategory, TicketPriority, TicketStatus
from app.modules.service_desk.schemas import (
    TicketAssignRequest,
    TicketCommentCreateRequest,
    TicketCommentResponse,
    TicketCreateRequest,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
    TicketStatusUpdateRequest,
)
from app.modules.users.models import User
from app.modules.users.permissions import SERVICE_DESK_USE

router = APIRouter(prefix="/service-desk", tags=["service-desk"])
StaffUser = Annotated[User, Depends(require_permission(SERVICE_DESK_USE))]
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
    ticket = service.update_status(
        db,
        actor=actor,
        ticket_id=ticket_id,
        new_status=payload.status,
        resolution_note=payload.resolution_note,
    )
    return TicketResponse.model_validate(ticket)
