"""Administrator endpoints for durable external integration connections."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.users.models import User
from app.modules.users.permissions import INTEGRATIONS_MANAGE
from app.modules.integrations.schemas import (
    IntegrationConnectionResponse,
    MetaPageConnectionUpsert,
)
from app.modules.integrations.service import delete_meta_page, list_connections, upsert_meta_page

router = APIRouter(prefix="/integrations", tags=["integrations"])

IntegrationManager = Annotated[User, Depends(require_permission(INTEGRATIONS_MANAGE))]


@router.put("/meta/pages/{page_id}", response_model=IntegrationConnectionResponse)
def configure_meta_page(
    payload: MetaPageConnectionUpsert,
    db: Annotated[Session, Depends(get_db)],
    actor: IntegrationManager,
    page_id: Annotated[str, Path(min_length=1, max_length=128)],
):
    """Upsert encrypted Meta Lead Ads credentials for a page."""

    return upsert_meta_page(db, actor=actor, page_id=page_id, payload=payload)


@router.get("/connections", response_model=list[IntegrationConnectionResponse])
def get_connections(db: Annotated[Session, Depends(get_db)], actor: IntegrationManager):
    """List connection routing and health without exposing credentials."""

    return list_connections(db, tenant_id=actor.tenant_id)


@router.delete("/meta/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_meta_page(
    db: Annotated[Session, Depends(get_db)],
    actor: IntegrationManager,
    page_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> None:
    """Delete the tenant's connection, revoking its routing and credentials."""

    delete_meta_page(db, actor=actor, page_id=page_id)
