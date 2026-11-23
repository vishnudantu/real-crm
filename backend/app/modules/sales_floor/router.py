"""HTTP endpoints for read-only sales executive and manager workspaces."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import ManagerUser, require_roles
from app.modules.sales_floor import service
from app.modules.sales_floor.schemas import MyDayResponse, RoutingSuggestionResponse, WarRoomResponse
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/sales-floor", tags=["sales-floor"])
SalesFloorUser = Annotated[
    User,
    Depends(require_roles(RoleName.SALES_EXECUTIVE, RoleName.MANAGER, RoleName.ADMIN)),
]


@router.get("/my-day", response_model=MyDayResponse, summary="Prioritized sales work for today")
def my_day(user: SalesFloorUser, db: Annotated[Session, Depends(get_db)]) -> MyDayResponse:
    """Return own work for executives, tenant work for managers and admins."""
    return service.get_my_day(db, actor=user)


@router.get("/war-room", response_model=WarRoomResponse, summary="Today's tenant sales rollup")
def war_room(user: ManagerUser, db: Annotated[Session, Depends(get_db)]) -> WarRoomResponse:
    """Aggregate today's tenant activity without changing any source records."""
    return service.get_war_room(db, actor=user)


@router.get(
    "/lead-routing/suggest",
    response_model=RoutingSuggestionResponse,
    summary="Rank eligible lead assignees with explicit rules",
)
def suggest_lead_routing(
    lead_id: UUID,
    user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> RoutingSuggestionResponse:
    """Feed an existing assignment flow; this endpoint does not assign the lead."""
    return service.suggest_lead_routing(db, actor=user, lead_id=lead_id)
