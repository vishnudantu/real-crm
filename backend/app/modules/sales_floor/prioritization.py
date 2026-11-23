"""Deterministic ranking rules shared by the sales-floor read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from uuid import UUID


class UrgencyBand(IntEnum):
    """Documented urgency ordering; never infer buyer intent or use ML."""

    OVERDUE = 4000
    DUE_TODAY = 3000
    AGING_SILENCE = 2000
    PENDING_APPROVAL = 1000


@dataclass(frozen=True)
class WorkItem:
    kind: str
    id: UUID
    urgency: str
    title: str
    reason: str
    due_at: datetime
    waiting_hours: float
    lead_id: UUID | None = None
    project_id: UUID | None = None
    project_name: str | None = None

    @property
    def priority_score(self) -> int:
        return int(UrgencyBand[self.urgency])


def prioritize(items: list[WorkItem]) -> list[WorkItem]:
    """Order by urgency, recorded timestamp, and stable UUID for repeatability."""

    return sorted(items, key=lambda item: (-item.priority_score, _as_utc(item.due_at), str(item.id)))


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
