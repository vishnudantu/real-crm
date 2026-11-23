"""Public API contracts for deal-desk cost sheets, discount matrix and quotes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

COST_SHEET_COMPONENTS: tuple[str, ...] = (
    "land", "construction", "amenities", "margin",
)


def validate_components(components: dict[str, int]) -> dict[str, int]:
    """Normalise the breakdown to exactly the four integer-paise components."""

    unknown = sorted(set(components) - set(COST_SHEET_COMPONENTS))
    if unknown:
        raise ValueError(
            f"Unknown cost components: {', '.join(unknown)}. "
            f"Allowed: {', '.join(COST_SHEET_COMPONENTS)}."
        )
    missing = [key for key in COST_SHEET_COMPONENTS if key not in components]
    if missing:
        raise ValueError(f"Missing cost components: {', '.join(missing)}.")
    normalized = {key: int(components[key]) for key in COST_SHEET_COMPONENTS}
    negative = sorted(key for key, value in normalized.items() if value < 0)
    if negative:
        raise ValueError(f"Cost components must be non-negative paise: {', '.join(negative)}.")
    return normalized


class CostComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    land: int = Field(ge=0)
    construction: int = Field(ge=0)
    amenities: int = Field(ge=0)
    margin: int = Field(ge=0)

    def as_paise_dict(self) -> dict[str, int]:
        return validate_components(self.model_dump())


class CostSheetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    unit_id: UUID | None = None
    components: CostComponents
    note: str | None = Field(default=None, max_length=500)


class CostSheetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    components: CostComponents
    note: str | None = Field(default=None, max_length=500)


class CostSheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID
    unit_id: UUID | None
    land_paise: int
    construction_paise: int
    amenities_paise: int
    margin_paise: int
    total_paise: int
    cost_breakdown_json: dict
    note: str | None
    created_at: datetime
    updated_at: datetime


class CostSheetListResponse(BaseModel):
    items: list[CostSheetResponse]
    total: int


class MatrixBandInput(BaseModel):
    max_discount_percent: Decimal | None = Field(
        default=None, gt=0, le=100,
        description="Upper bound of this band; omit for the open-ended ceiling band.",
    )
    reason_required: bool = False
    blocked: bool = False
    description: str | None = Field(default=None, max_length=255)


class MatrixUpdateRequest(BaseModel):
    """Replace the tenant's band policy wholesale — partial edits of a policy
    matrix invite gaps, so the whole ladder is submitted and validated."""

    model_config = ConfigDict(extra="forbid")

    bands: list[MatrixBandInput] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_ladder(self) -> "MatrixUpdateRequest":
        covered = [band.max_discount_percent for band in self.bands if band.max_discount_percent is not None]
        if len(covered) + 1 != len(self.bands):
            raise ValueError("Exactly one band (the last) must omit max_discount_percent as the ceiling band.")
        if self.bands[-1].max_discount_percent is not None or not self.bands[-1].blocked:
            raise ValueError("The last band must be the open-ended ceiling band and must be blocked.")
        for index in range(len(covered) - 1):
            if covered[index] >= covered[index + 1]:
                raise ValueError("Band thresholds must ascend strictly.")
        for band in self.bands[:-1]:
            if band.blocked:
                raise ValueError("Only the ceiling band may be blocked.")
        return self


class MatrixBandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    band_number: int
    max_discount_percent: Decimal | None
    reason_required: bool
    blocked: bool
    description: str | None


class MatrixResponse(BaseModel):
    tenant_id: UUID
    bands: list[MatrixBandResponse]


class QuoteCreateRequest(BaseModel):
    """Discount is proposed as a percent of gross; paise amounts are computed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    unit_id: UUID
    gross_price_paise: int = Field(gt=0)
    discount_percent: Decimal = Field(ge=0, le=100)
    customer_ref: str | None = Field(default=None, max_length=128)


class QuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID
    unit_id: UUID
    cost_sheet_id: UUID | None
    gross_price_paise: int
    discount_paise: int
    discount_percent: Decimal
    net_price_paise: int
    band_number: int
    status: Literal["QUOTED", "REQUESTED"]
    customer_ref: str | None
    created_at: datetime
    updated_at: datetime


class QuoteListResponse(BaseModel):
    items: list[QuoteResponse]
    total: int


class DiscountRequestCreate(BaseModel):
    """Raise the quote's discount into the approval pipeline."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=2000)


class DealDiscountRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_request_id: UUID
    quote_id: UUID
    unit_id: UUID
    band_number: int
    discount_percent: Decimal
    status: str
    amount_paise: int
    net_price_paise: int
