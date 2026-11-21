"""Tenant billing contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateSubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: UUID


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    plan_id: UUID
    status: str
    razorpay_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    grace_period_end: datetime | None
    created_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID | None
    razorpay_invoice_id: str | None
    amount_paise: int
    currency: str
    status: str
    paid_at: datetime | None
    created_at: datetime


class BillingSummaryResponse(BaseModel):
    plan: dict | None
    subscription: SubscriptionResponse | None
    usage: dict
    invoices: list[InvoiceResponse]
