"""Tenant ADMIN messaging configuration and delivery-log endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.messaging import service
from app.modules.messaging.schemas import (
    MessageDeliveryListResponse,
    MessageDeliveryResponse,
    MessageTemplateCreateRequest,
    MessageTemplateListResponse,
    MessageTemplateResponse,
    MessageTemplateUpdateRequest,
    SendTestRequest,
    TriggerRuleCreateRequest,
    TriggerRuleListResponse,
    TriggerRuleResponse,
    TriggerRuleUpdateRequest,
)

router = APIRouter(prefix="/messaging", tags=["messaging"])


@router.post("/templates", response_model=MessageTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template_endpoint(
    payload: MessageTemplateCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_template(db, actor=admin, payload=payload)


@router.get("/templates", response_model=MessageTemplateListResponse)
def list_templates_endpoint(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    items = service.list_templates(db, actor=admin)
    return MessageTemplateListResponse(items=items, total=len(items))


@router.patch("/templates/{template_id}", response_model=MessageTemplateResponse)
def update_template_endpoint(
    template_id: UUID,
    payload: MessageTemplateUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_template(db, actor=admin, template_id=template_id, payload=payload)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template_endpoint(
    template_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.delete_template(db, actor=admin, template_id=template_id)


@router.post("/rules", response_model=TriggerRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule_endpoint(
    payload: TriggerRuleCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_rule(db, actor=admin, payload=payload)


@router.get("/rules", response_model=TriggerRuleListResponse)
def list_rules_endpoint(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    items = service.list_rules(db, actor=admin)
    return TriggerRuleListResponse(items=items, total=len(items))


@router.patch("/rules/{rule_id}", response_model=TriggerRuleResponse)
def update_rule_endpoint(
    rule_id: UUID,
    payload: TriggerRuleUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_rule(db, actor=admin, rule_id=rule_id, payload=payload)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule_endpoint(
    rule_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.delete_rule(db, actor=admin, rule_id=rule_id)


@router.get("/deliveries", response_model=MessageDeliveryListResponse)
def list_deliveries_endpoint(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    channel: str | None = None,
):
    return service.list_deliveries(
        db, actor=admin, page=page, page_size=page_size, status_filter=status_filter, channel=channel
    )


@router.post("/send-test", response_model=MessageDeliveryResponse, status_code=status.HTTP_201_CREATED)
def send_test_endpoint(
    payload: SendTestRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.send_test(db, actor=admin, payload=payload)


@router.post("/seed-lifecycle")
def seed_lifecycle_endpoint(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Seed default lifecycle templates + trigger rules for the caller's tenant.

    Idempotent: existing rules/templates are skipped, so a tenant's own edits
    are preserved on re-seed. This is what makes the thank-you-after-visit,
    booking-confirmation, and receipt emails actually fire.
    """
    return service.seed_lifecycle_for_tenant(db, actor=admin)
