"""Pydantic contracts for units, holds, and availability."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from app.modules.inventory.models import (
    DiscountStatus,
    HoldReleaseSource,
    HoldState,
    UnitEventSource,
    UnitStatus,
)


class UnitCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    internal_code: str = Field(min_length=1, max_length=64)
    configuration: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=64)
    position: str | None = Field(default=None, max_length=64)
    tower: str | None = Field(default=None, max_length=64)
    carpet_area_sqft: int | None = Field(default=None, ge=1)
    built_up_area_sqft: int | None = Field(default=None, ge=1)
    plot_number: str | None = Field(default=None, max_length=64)
    facing: str | None = Field(default=None, max_length=64)
    views: str | None = Field(default=None, max_length=255)
    saleable: bool = True
    status: UnitStatus = UnitStatus.DRAFT
    status_reason: str | None = Field(default=None, max_length=2000)
    rera_disclosure_json: dict = Field(default_factory=dict)


class UnitUpdateRequest(BaseModel):
    """Edit mutable unit fields. Status changes go through the state machine.

    ``internal_code`` is immutable (it is the canonical identity used across
    holds, bookings, and documents) and is intentionally absent here.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    configuration: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=64)
    position: str | None = Field(default=None, max_length=64)
    tower: str | None = Field(default=None, max_length=64)
    carpet_area_sqft: int | None = Field(default=None, ge=1)
    built_up_area_sqft: int | None = Field(default=None, ge=1)
    plot_number: str | None = Field(default=None, max_length=64)
    facing: str | None = Field(default=None, max_length=64)
    views: str | None = Field(default=None, max_length=255)
    saleable: bool | None = None
    rera_disclosure_json: dict | None = None


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    internal_code: str
    configuration: str | None
    floor: str | None
    position: str | None
    tower: str | None
    carpet_area_sqft: int | None
    built_up_area_sqft: int | None
    plot_number: str | None
    facing: str | None
    views: str | None
    saleable: bool
    status: UnitStatus
    status_reason: str | None
    approved_discount_paise: int | None = None
    discount_status: DiscountStatus = DiscountStatus.NONE
    rera_disclosure_json: dict
    created_at: datetime
    updated_at: datetime


class UnitListResponse(BaseModel):
    items: list[UnitResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UnitStatusEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    unit_id: UUID
    from_status: UnitStatus
    to_status: UnitStatus
    actor_user_id: UUID | None
    reason: str | None
    source: UnitEventSource
    effective_at: datetime
    event_meta: dict = Field(default_factory=dict, validation_alias="meta")


class UnitDetailResponse(UnitResponse):
    status_history: list[UnitStatusEventResponse] = Field(default_factory=list)


class UnitStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_status: UnitStatus
    reason: str | None = Field(default=None, max_length=2000)
    source: UnitEventSource = UnitEventSource.MANUAL
    approved: bool = Field(
        default=False,
        description="Required for BLOCKED: records that the block is approved.",
    )


class BulkUnitCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[UnitCreateRequest] = Field(min_length=1, max_length=500)


class BulkRowResult(BaseModel):
    index: int
    internal_code: str
    ok: bool
    unit_id: UUID | None = None
    reason: str | None = None


class BulkUnitCreateResponse(BaseModel):
    dry_run: bool
    results: list[BulkRowResult]
    created: int
    failed: int


class HoldCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    unit_id: UUID
    lead_id: UUID | None = None
    opportunity_ref: str | None = Field(default=None, max_length=128)
    hours: int = Field(default=48, ge=1, le=720)
    reason: str | None = Field(default=None, max_length=2000)


class HoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    lead_id: UUID | None
    opportunity_ref: str | None
    owner_user_id: UUID
    reason: str | None
    state: HoldState
    expires_at: datetime
    extension_count: int
    converted_booking_id: UUID | None
    released_at: datetime | None
    release_source: HoldReleaseSource | None
    created_at: datetime


class HoldExtendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours: int = Field(default=24, ge=1, le=720)
    reason: str | None = Field(default=None, max_length=2000)


class HoldReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class HoldConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consideration_paise: int = Field(ge=0)
    booked_on: date | None = None


class HoldConvertResponse(BaseModel):
    hold: HoldResponse
    booking_id: UUID


class AvailabilityResponse(BaseModel):
    project_id: UUID
    counts: dict[str, int]
    total: int


class DiscountRequestCreateRequest(BaseModel):
    """Input payload for a discount proposal on a canonical unit.

    ``amount_paise`` is the proposed discount in paise; it must be strictly
    positive and is capped at 20% of the unit price once units carry one.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount_paise: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    approver_id: UUID | None = None
