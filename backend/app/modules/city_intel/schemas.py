"""Pydantic v2 contracts for City Intelligence Engine (Phase 1)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.city_intel.models import CONFIDENCE_LEVELS


# ---- Demand intelligence ----


class LocalityDemand(BaseModel):
    project_id: str
    locality: str
    project_name: str
    lead_count: int
    booking_count: int
    conversion_pct: float
    median_budget_paise: int | None
    top_price_band: str
    top_property_type: str


class DemandResponse(BaseModel):
    items: list[LocalityDemand]
    total: int


# ---- Curated POI / connectivity ----


class AmenityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    category: str = Field(pattern=r"^(school|hospital|transit|employment|amenity)$")
    name: str = Field(min_length=1, max_length=255)
    distance_km: float = Field(ge=0.0, default=0.0)
    travel_minutes: int = Field(ge=0, default=0)
    source_ref: str | None = Field(default=None, max_length=500)
    confidence: str = Field(default="estimated")
    as_of: date | None = None

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_LEVELS:
            raise ValueError(f"confidence must be one of {CONFIDENCE_LEVELS}")
        return value


class AmenityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: str
    name: str
    distance_km: float
    travel_minutes: int
    source_ref: str | None
    confidence: str
    as_of: date | None
    created_at: datetime


class AmenityListResponse(BaseModel):
    items: list[AmenityResponse]
    total: int


class CategorySummary(BaseModel):
    category: str
    count: int
    nearest_km: float | None
    nearest_travel_minutes: int | None


class ConnectivityResponse(BaseModel):
    project_id: UUID
    score: int
    by_category: list[CategorySummary]
    notes: list[str]


# ---- Locality reports ----


class ReportSource(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    ref: str | None = Field(default=None, max_length=500)
    observed_on: date | None = None
    confidence: str = Field(default="estimated")

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_LEVELS:
            raise ValueError(f"confidence must be one of {CONFIDENCE_LEVELS}")
        return value


class LocalityReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    sources: list[ReportSource] = Field(default_factory=list)
    as_of: date | None = None


class LocalityReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    body: str
    sources: list[ReportSource]
    status: str
    as_of: date | None
    created_at: datetime


class LocalityReportListResponse(BaseModel):
    items: list[LocalityReportResponse]
    total: int
