"""Pydantic v2 schemas for the solar-facing module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "ProjectCoordinatesUpdate",
    "TowerOrientationUpsert",
    "TowerOrientationResponse",
    "SunPathResponse",
    "SunPathDay",
    "UnitSunScoreResponse",
]


class ProjectCoordinatesUpdate(BaseModel):
    """Admin input for setting a project's site coordinates."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class TowerOrientationUpsert(BaseModel):
    """Admin input for creating or updating a tower's facade bearing."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    tower_label: str = Field(min_length=1, max_length=64)
    orientation_deg: float = Field(ge=0.0, le=360.0)


class TowerOrientationResponse(BaseModel):
    """Response for a tower orientation record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    tower_label: str
    orientation_deg: float
    created_at: datetime


class SunPathDay(BaseModel):
    """Sunrise/sunset data for one representative day."""

    date: str  # ISO date string
    sunrise: str  # ISO datetime string
    sunset: str  # ISO datetime string
    solar_noon: str  # ISO datetime string
    day_length_hours: float


class SunPathResponse(BaseModel):
    """Full sun-path summary for a project site."""

    project_id: UUID
    latitude: float
    longitude: float
    solstices_and_equinox: list[SunPathDay]


class UnitSunScoreResponse(BaseModel):
    """Sun-exposure score for a single unit."""

    unit_id: UUID
    facing_bearing: float
    facing_label: str
    exposure_class: str
    comfort_score: int
    vastu_note: str
    pricing_premium_min_pct: float
    pricing_premium_max_pct: float
    pricing_advisory: str
