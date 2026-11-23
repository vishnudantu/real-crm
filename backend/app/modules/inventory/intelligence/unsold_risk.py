"""Explainable risk scoring for inventory that remains unsold."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

UNSOLD_STATUSES = frozenset({"AVAILABLE"})


@dataclass(frozen=True)
class UnsoldRisk:
    """Risk that an available unit remains unsold, based on its listing age."""

    unit_id: Any
    internal_code: str
    status: str
    days_available: int
    risk: str


def predict_unsold_risk(
    *,
    units: Sequence,
    today: date,
    medium_days: int = 60,
    high_days: int = 120,
) -> list[UnsoldRisk]:
    """Score currently available units, oldest first, using day thresholds."""
    if not high_days > medium_days > 0:
        raise ValueError("Thresholds must satisfy high_days > medium_days > 0")

    risks = []
    for unit in units:
        if unit.status not in UNSOLD_STATUSES:
            continue
        days_available = max((today - unit.created_at.date()).days, 0)
        risk = (
            "HIGH"
            if days_available >= high_days
            else "MEDIUM"
            if days_available >= medium_days
            else "LOW"
        )
        risks.append(
            UnsoldRisk(
                unit_id=unit.id,
                internal_code=unit.internal_code,
                status=unit.status,
                days_available=days_available,
                risk=risk,
            )
        )

    return sorted(risks, key=lambda item: (-item.days_available, item.internal_code))
