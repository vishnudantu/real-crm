"""Tenant billing endpoints plus the signature-verified Razorpay webhook."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.billing import service
from app.modules.billing.models import Invoice, Subscription
from app.modules.billing.schemas import (
    BillingSummaryResponse,
    CreateSubscriptionRequest,
    SubscriptionResponse,
)
from app.modules.plans.models import Plan

router = APIRouter(tags=["billing"])


@router.get("/billing/summary", response_model=BillingSummaryResponse)
def billing_summary(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.summary(db, tenant_id=admin.tenant_id)


@router.get("/billing/plans")
def available_plans(admin: AdminUser, db: Annotated[Session, Depends(get_db)]):
    return [
        {"id": p.id, "code": p.code, "name": p.name, "price_paise": p.price_paise, "max_users": p.max_users, "leads_per_month": p.leads_per_month, "whatsapp_msgs_per_month": p.whatsapp_msgs_per_month, "features": p.features}
        for p in db.scalars(select(Plan).where(Plan.is_active.is_(True))).all()
    ]


@router.post("/billing/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: CreateSubscriptionRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return service.create_subscription(
        db, tenant_id=admin.tenant_id, plan_id=payload.plan_id, settings=settings
    )


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return service.process_webhook(
        db,
        raw_body=await request.body(),
        signature=request.headers.get("X-Razorpay-Signature", ""),
        settings=settings,
    )
