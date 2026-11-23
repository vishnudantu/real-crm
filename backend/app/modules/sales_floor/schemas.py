"""Typed, read-only contracts for the sales-floor workspaces."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Urgency = Literal["OVERDUE", "DUE_TODAY", "AGING_SILENCE", "PENDING_APPROVAL"]
MyDayKind = Literal["FOLLOW_UP", "VISIT", "FIRST_RESPONSE", "CONVERSATION", "APPROVAL"]


class MyDayItem(BaseModel):
    kind: MyDayKind
    id: UUID
    urgency: Urgency
    priority_score: int = Field(description="Deterministic urgency-band score; higher comes first.")
    title: str
    reason: str
    lead_id: UUID | None
    project_id: UUID | None
    project_name: str | None
    due_at: datetime
    waiting_hours: float
    link: str


class MyDayResponse(BaseModel):
    date: date
    scope: Literal["PERSONAL", "TEAM"]
    items: list[MyDayItem]
    counts: dict[str, int]
    priority_explanation: str
    promises_included: bool


class ExecutiveActivity(BaseModel):
    executive_id: UUID
    full_name: str
    visits_today: int
    new_leads: int
    bookings_created: int


class SourceCount(BaseModel):
    source: str
    count: int


class FunnelCounts(BaseModel):
    enquiries: int
    visits: int
    bookings: int


class FunnelAverage(BaseModel):
    enquiries: float
    visits: float
    bookings: float


class ProjectFunnel(BaseModel):
    project_id: UUID
    project_name: str
    today: FunnelCounts
    seven_day_average: FunnelAverage


class WarRoomResponse(BaseModel):
    date: date
    comparison_start: datetime
    executive_activity: list[ExecutiveActivity]
    new_leads_by_source: list[SourceCount]
    new_leads_total: int
    visits_today: int
    bookings_created_today: int
    pending_discount_approvals: int
    unassigned_leads_count: int
    project_funnels: list[ProjectFunnel]


class RoutingLead(BaseModel):
    id: UUID
    project_id: UUID
    language: str
    contact_methods: list[str]


class RoutingCandidate(BaseModel):
    executive_id: UUID
    full_name: str
    current_open_leads: int
    prior_project_leads: int
    score: int
    reasons: list[str]


class RoutingSuggestionResponse(BaseModel):
    lead: RoutingLead
    candidates: list[RoutingCandidate]
    language_matching_available: bool
    rules: list[str]
