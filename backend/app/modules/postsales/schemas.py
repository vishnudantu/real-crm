"""Post-sales contracts: sale bookings, plans, installments, receipts, brokers."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.postsales.models import (
    CommissionStatus,
    InstallmentStatus,
    PaymentPlanType,
    ReceiptChannel,
    SaleStatus,
)


class SaleBookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    lead_id: UUID
    unit_number: str = Field(min_length=1, max_length=64)
    unit_id: UUID | None = Field(
        default=None,
        description="Canonical unit (PF-010). Optional; must be same-tenant and same-project when set.",
    )
    configuration: str | None = Field(default=None, max_length=100)
    carpet_area_sqft: int | None = Field(default=None, ge=1)
    consideration_paise: int = Field(ge=0)
    booked_on: date | None = None


class SaleBookingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SaleStatus | None = None
    agreement_date: date | None = None
    expected_possession: date | None = None
    unit_number: str | None = Field(default=None, min_length=1, max_length=64)
    carpet_area_sqft: int | None = Field(default=None, ge=1)


class SaleBookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    lead_id: UUID
    project_id: UUID
    customer_id: UUID | None
    unit_number: str
    unit_id: UUID | None
    configuration: str | None
    carpet_area_sqft: int | None
    consideration_paise: int
    status: SaleStatus
    booked_on: date
    agreement_date: date | None
    expected_possession: date | None
    created_at: datetime


class SaleBookingListResponse(BaseModel):
    items: list[SaleBookingResponse]
    total: int
    page: int
    page_size: int
    pages: int


class InstallmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    milestone: str = Field(min_length=1, max_length=160)
    amount_paise: int = Field(ge=0)
    due_on: date


class PaymentPlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=128)
    plan_type: PaymentPlanType
    installments: list[InstallmentSpec] = Field(min_length=1, max_length=240)


class PaymentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_booking_id: UUID
    name: str
    plan_type: PaymentPlanType
    is_active: bool
    created_at: datetime


class InstallmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_on: date | None = None
    amount_paise: int | None = Field(default=None, ge=0)
    status: InstallmentStatus | None = None


class InstallmentWithPaid(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    sequence_no: int
    milestone: str
    amount_paise: int
    due_on: date
    status: InstallmentStatus
    demand_letter_sent_at: datetime | None
    paid_paise: int
    outstanding_paise: int


class ReceiptVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)


class ReceiptCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    installment_id: UUID
    amount_paise: int = Field(gt=0)
    channel: ReceiptChannel
    reference: str | None = Field(default=None, max_length=160)
    idempotency_key: str | None = Field(
        default=None,
        max_length=160,
        description=(
            "Optional client-supplied key. A repeated request with the same "
            "tenant + key returns the original receipt without a new posting."
        ),
    )
    notes: str | None = Field(default=None, max_length=2000)
    paid_at: datetime | None = None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    installment_id: UUID
    receipt_number: str
    amount_paise: int
    channel: ReceiptChannel
    reference: str | None
    idempotency_key: str | None
    received_by_id: UUID | None
    paid_at: datetime
    notes: str | None
    voided_at: datetime | None = None
    voided_by_id: UUID | None = None
    void_reason: str | None = None


class BrokerCommissionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    broker_name: str = Field(min_length=1, max_length=255)
    broker_phone: str | None = Field(default=None, max_length=32)
    amount_paise: int = Field(ge=0)
    basis: dict = Field(default_factory=dict)


class BrokerCommissionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CommissionStatus | None = None


class BrokerCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_booking_id: UUID
    broker_name: str
    broker_phone: str | None
    basis: dict
    amount_paise: int
    status: CommissionStatus
    paid_at: datetime | None
    created_at: datetime


class SaleLedgerResponse(BaseModel):
    booking: SaleBookingResponse
    plans: list[PaymentPlanResponse]
    installments: list[InstallmentWithPaid]
    receipts: list[ReceiptResponse]
    commissions: list[BrokerCommissionResponse]
    collected_paise: int
    outstanding_paise: int
