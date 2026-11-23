"""Pydantic v2 contracts for Advanced Inventory Intelligence (Module 20)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RevenueRow(BaseModel):
    """One unit's booked value and age in the revenue map."""

    unit_id: str
    internal_code: str
    status: str
    booked_value_paise: int | None = None
    age_days: int


class RevenueMapResponse(BaseModel):
    """Inventory value, realization, reservation status and aging."""

    total_units: int
    by_status: dict[str, int]
    total_booked_value_paise: int
    avg_unit_age_days: float
    oldest_unit_age_days: int
    rows: list[RevenueRow]


class HoldExpiryRisk(BaseModel):
    """An ACTIVE hold assessed for risk of expiring without conversion."""

    hold_id: str
    unit_id: str
    expires_at: datetime
    hours_remaining: float
    extension_count: int
    risk: str  # LOW | MEDIUM | HIGH


class HoldExpiryResponse(BaseModel):
    items: list[HoldExpiryRisk]
    total: int


class UnsoldRisk(BaseModel):
    """Heuristic prolonged-selling-period risk for an available unit."""

    unit_id: str
    internal_code: str
    status: str
    days_available: int
    risk: str  # LOW | MEDIUM | HIGH


class UnsoldRiskResponse(BaseModel):
    items: list[UnsoldRisk]
    total: int
    medium_days: int
    high_days: int


class UnitConflict(BaseModel):
    """An inconsistent booking/reservation/payment/sale state."""

    unit_id: str
    code: str
    kind: str
    detail: str


class ConflictResponse(BaseModel):
    items: list[UnitConflict]
    total: int


class UnitRecommendation(BaseModel):
    """An available alternative unit ranked by similarity to the request."""

    unit_id: str
    internal_code: str
    score: int = Field(ge=0, le=100)
    reasons: list[str]


class RecommendationResponse(BaseModel):
    requested_unit_id: str
    items: list[UnitRecommendation]
    total: int
