"""Deterministic aggregation of inventory age, status, and booked revenue."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RevenueRow:
    """Age and booked consideration for one inventory unit."""

    unit_id: str
    internal_code: str
    status: str
    booked_value_paise: int | None
    age_days: int


@dataclass(frozen=True)
class RevenueMap:
    """Portfolio-level revenue and ageing summary with per-unit detail."""

    total_units: int
    by_status: dict[str, int]
    total_booked_value_paise: int
    avg_unit_age_days: float
    oldest_unit_age_days: int
    rows: list[RevenueRow]


def build_revenue_map(
    *, units: Sequence, booked_values: Mapping[str, int], today: date
) -> RevenueMap:
    """Build a revenue map from fetched units and booking consideration values."""
    rows = []
    for unit in units:
        unit_id = str(unit.id)
        age_days = max(0, (today - unit.created_at.date()).days)
        rows.append(
            RevenueRow(
                unit_id=unit_id,
                internal_code=unit.internal_code,
                status=str(unit.status),
                booked_value_paise=booked_values.get(unit_id),
                age_days=age_days,
            )
        )

    rows.sort(key=lambda row: (-row.age_days, row.internal_code))
    ages = [row.age_days for row in rows]
    return RevenueMap(
        total_units=len(rows),
        by_status=dict(Counter(row.status for row in rows)),
        total_booked_value_paise=sum(booked_values.values()),
        avg_unit_age_days=round(sum(ages) / len(ages), 1) if ages else 0.0,
        oldest_unit_age_days=max(ages, default=0),
        rows=rows,
    )
