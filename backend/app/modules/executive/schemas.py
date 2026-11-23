"""Public API contracts for the executive cockpit and morning briefing."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MonthPoint(BaseModel):
    """One calendar-month bucket of an executive trend series."""

    model_config = ConfigDict(from_attributes=True)

    month: date = Field(description="First day (UTC) of the month bucket.")
    enquiries: int = Field(ge=0)
    visits_completed: int = Field(ge=0)
    bookings: int = Field(ge=0)
    booking_value_paise: int = Field(ge=0)


class CollectionsMonthPoint(BaseModel):
    """Live receipts for one calendar month (voided receipts excluded)."""

    model_config = ConfigDict(from_attributes=True)

    month: date
    collected_paise: int = Field(ge=0)
    receipt_count: int = Field(ge=0)


class InventorySummary(BaseModel):
    """Unit availability plus unsold inventory value for one project.

    ``unsold_value_paise`` sums the live (non-voided) booking consideration of
    every non-terminal sale booking attached to each unsold unit; units without
    a booking contribute zero because their price is not in ``sale_bookings``.
    """

    model_config = ConfigDict(from_attributes=True)

    project_id: UUID | None
    total_units: int = Field(ge=0)
    counts_by_status: dict[str, int]
    available: int = Field(ge=0)
    on_hold: int = Field(ge=0)
    reserved: int = Field(ge=0)
    booked: int = Field(ge=0)
    sold: int = Field(ge=0)
    unsold_value_paise: int = Field(ge=0)


class ApprovalsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_count: int = Field(ge=0)
    pending_amount_paise: int = Field(ge=0)
    by_type: dict[str, int]


class OverdueInstallmentRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    installment_id: UUID
    unit_number: str
    milestone: str
    amount_paise: int
    due_on: date
    days_overdue: int = Field(ge=0)


class OverdueInstallmentsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count: int = Field(ge=0)
    amount_paise: int = Field(ge=0)
    oldest_due_on: date | None
    sample: list[OverdueInstallmentRow] = Field(default_factory=list)


class TicketSlaSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    breaching_count: int = Field(ge=0)
    open_count: int = Field(ge=0)
    by_priority: dict[str, int]


class ProjectRankRow(BaseModel):
    """One project's trailing-window velocity used for ranking."""

    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    project_name: str
    enquiries: int = Field(ge=0)
    visits_completed: int = Field(ge=0)
    bookings: int = Field(ge=0)
    booking_value_paise: int = Field(ge=0)
    collected_paise: int = Field(ge=0)
    unsold_units: int = Field(ge=0)
    velocity_score: float = Field(
        description="Ranking score: bookings*3 + visits_completed + enquiries*0.1 "
        "over the trailing window. Deterministic; see service docstring."
    )


class CockpitResponse(BaseModel):
    """Aggregated executive view; every number is read-only from existing tables."""

    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    tenant_id: UUID
    project_id: UUID | None
    window_months: int
    sales_velocity: list[MonthPoint]
    collections: list[CollectionsMonthPoint]
    inventory: InventorySummary
    approvals: ApprovalsSummary
    overdue_installments: OverdueInstallmentsSummary
    ticket_sla: TicketSlaSummary
    project_ranking: list[ProjectRankRow]


class BriefingDayCounts(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leads: int = Field(ge=0)
    visits_completed: int = Field(ge=0)
    visit_bookings_created: int = Field(ge=0)
    visit_bookings_cancelled: int = Field(ge=0)
    sale_bookings: int = Field(ge=0)
    sale_booking_value_paise: int = Field(ge=0)
    receipts: int = Field(ge=0)
    receipts_paise: int = Field(ge=0)
    tickets_created: int = Field(ge=0)
    tickets_resolved: int = Field(ge=0)
    approvals_decided: int = Field(ge=0)


class BriefingOpenItems(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approvals_pending: int = Field(ge=0)
    tickets_breaching_sla: int = Field(ge=0)
    overdue_installments: int = Field(ge=0)
    overdue_amount_paise: int = Field(ge=0)
    unassigned_active_leads: int = Field(ge=0)
    active_sale_bookings: int = Field(ge=0)


class BriefingResponse(BaseModel):
    """Deterministic morning digest: facts plus template-rendered lines.

    The briefing is rendered from SQL counts with no LLM/AI call; rendering the
    same day against the same database always produces the same text.
    """

    model_config = ConfigDict(from_attributes=True)

    briefing_date: date
    generated_at: datetime
    tenant_id: UUID
    counts: BriefingDayCounts
    open_items: BriefingOpenItems
    lines: list[str]
