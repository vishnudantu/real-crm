"""Validated API contracts for the handover workspace."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.handover.models import HandoverStatus, SnagSeverity, SnagStatus


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HandoverCaseCreate(Contract):
    unit_id: UUID
    booking_id: UUID | None = None
    registration_date: date | None = None
    registration_reference: str | None = Field(default=None, max_length=128)
    possession_date: date | None = None


class HandoverCasePatch(Contract):
    registration_date: date | None = None
    registration_reference: str | None = Field(default=None, max_length=128)
    possession_date: date | None = None


class HandoverCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    unit_id: UUID
    unit_number: str | None = None
    booking_reference: str | None = None
    booking_id: UUID | None
    status: HandoverStatus
    readiness: dict
    registration_date: date | None
    registration_reference: str | None
    possession_date: date | None
    override_reason: str | None
    override_by_id: UUID | None
    override_at: datetime | None
    handed_over_at: datetime | None
    handed_over_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class HandoverCaseList(BaseModel):
    items: list[HandoverCaseResponse]
    total: int


class ChecklistCondition(BaseModel):
    code: str
    label: str
    met: bool
    detail: str


class ReadinessBlocker(BaseModel):
    code: str
    label: str
    detail: str
    required_count: int = 5


class FinancialReadiness(BaseModel):
    planned_paise: int | None
    collected_paise: int | None
    outstanding_paise: int | None
    live_receipt_count: int


class HandoverChecklist(BaseModel):
    case_id: UUID
    score: int
    required_count: int
    met_count: int
    conditions: list[ChecklistCondition]
    blockers: list[ReadinessBlocker]
    financials: FinancialReadiness
    snag_count: int
    unresolved_snag_count: int
    checked_at: datetime


class SnagCreate(Contract):
    room: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=5000)
    severity: SnagSeverity = SnagSeverity.MINOR
    assigned_user_id: UUID | None = None


class SnagPatch(Contract):
    room: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    severity: SnagSeverity | None = None
    assigned_user_id: UUID | None = None


class SnagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    room: str
    description: str
    severity: SnagSeverity
    status: SnagStatus
    photo_evidence_path: str | None
    assigned_user_id: UUID | None
    fixed_by_id: UUID | None
    fixed_at: datetime | None
    verified_by_id: UUID | None
    verified_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KeyCreate(Contract):
    keys_count: int = Field(default=0, ge=0, le=1000)
    cards_count: int = Field(default=0, ge=0, le=1000)
    handed_to_name: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class KeyPatch(Contract):
    keys_count: int | None = Field(default=None, ge=0, le=1000)
    cards_count: int | None = Field(default=None, ge=0, le=1000)
    handed_to_name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class KeyCollect(Contract):
    notes: str | None = Field(default=None, max_length=5000)


class KeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    keys_count: int
    cards_count: int
    handed_to_name: str
    handed_at: datetime
    collected_id: UUID | None
    collected_at: datetime | None
    collected_notes: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CompleteRequest(Contract):
    override_reason: str | None = Field(default=None, min_length=10, max_length=5000)


class BuyerSnag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room: str
    description: str
    severity: SnagSeverity
    status: SnagStatus
    photo_evidence_path: str | None


class BuyerCase(BaseModel):
    id: UUID
    unit_id: UUID
    unit_number: str
    status: HandoverStatus
    expected_possession: date | None
    possession_date: date | None
    handed_over_at: datetime | None
    snags: list[BuyerSnag]


class BuyerCaseList(BaseModel):
    items: list[BuyerCase]
    total: int
