"""Collections contracts: calendar rows, promises, escalations, stats."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PromiseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount_paise: int = Field(ge=0)
    promised_on: date
    note: str | None = Field(default=None, max_length=500)


class PromiseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    installment_id: UUID
    amount_paise: int
    promised_on: date
    note: str | None
    created_at: datetime


class CalendarRow(BaseModel):
    installment_id: UUID
    booking_id: UUID
    plan_id: UUID
    project_id: UUID
    customer_name: str | None
    unit_number: str
    milestone: str
    due_on: date
    amount_paise: int
    paid_paise: int
    outstanding_paise: int
    status: str
    days_overdue: int
    demand_letter_status: str
    demand_letter_sent_at: datetime | None
    last_reminder_at: datetime | None
    has_overdue_promise: bool


class CalendarDay(BaseModel):
    date: date
    due_paise: int
    rows: list[CalendarRow]


class CalendarResponse(BaseModel):
    month: str
    project_id: UUID | None
    days: list[CalendarDay]
    overdue_aging: dict[str, int]
    due_this_month_paise: int


class EscalationRow(BaseModel):
    booking_id: UUID
    project_id: UUID
    customer_name: str | None
    unit_number: str
    severity: str
    oldest_due_on: date
    days_overdue: int
    outstanding_paise: int
    overdue_installments: int
    last_actions: dict[str, Any]
    suggested_action: str


class EscalationsResponse(BaseModel):
    groups: dict[str, list[EscalationRow]]
    thresholds: dict[str, int]


class StatsResponse(BaseModel):
    project_id: UUID | None
    recovered_30d_paise: int
    recovered_90d_paise: int
    outstanding_paise: int
    aging_buckets_paise: dict[str, int]
    reminder_payment_counts: dict[str, int]
