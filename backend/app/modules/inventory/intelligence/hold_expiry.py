"""Deterministic expiry-risk heuristics for active inventory holds."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC for safe subtraction."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(frozen=True)
class HoldExpiryRisk:
    """Expiry urgency for one active hold."""

    hold_id: str
    unit_id: str
    expires_at: datetime
    hours_remaining: float
    extension_count: int
    risk: str


def _risk_for(hours_remaining: float, extension_count: int) -> str:
    if hours_remaining <= 6:
        return "HIGH"
    if hours_remaining <= 24:
        return "HIGH" if extension_count >= 2 else "MEDIUM"
    return "MEDIUM" if extension_count >= 2 else "LOW"


def assess_hold_expiry(*, holds: Sequence, now: datetime) -> list[HoldExpiryRisk]:
    """Assess active holds, returning the most urgent expiry risks first."""
    risks = []
    for hold in holds:
        if hold.state != "ACTIVE":
            continue
        hours_remaining = (_as_utc(hold.expires_at) - now).total_seconds() / 3600
        risks.append(
            HoldExpiryRisk(
                hold_id=str(hold.id),
                unit_id=str(hold.unit_id),
                expires_at=_as_utc(hold.expires_at),
                hours_remaining=hours_remaining,
                extension_count=hold.extension_count,
                risk=_risk_for(hours_remaining, hold.extension_count),
            )
        )

    return sorted(risks, key=lambda risk: risk.hours_remaining)
