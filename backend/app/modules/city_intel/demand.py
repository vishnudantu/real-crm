"""Deterministic catchment-demand aggregation by locality, price band and property type.

Pure logic over already-fetched domain rows: no database, no network, no framework.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PriceBand:
    """An inclusive residential price band, expressed in paise."""

    label: str
    min_paise: int
    max_paise: int


DEFAULT_PRICE_BANDS: tuple[PriceBand, ...] = (
    PriceBand("<50L", 0, 5_000_000),
    PriceBand("50L-1Cr", 5_000_001, 10_000_000),
    PriceBand("1-2Cr", 10_000_001, 20_000_000),
    PriceBand(">2Cr", 20_000_001, 10**18),
)


@dataclass(frozen=True)
class LocalityDemand:
    """Catchment demand metrics for a single project locality."""

    project_id: str
    locality: str
    project_name: str
    lead_count: int
    booking_count: int
    conversion_pct: float
    median_budget_paise: int | None
    top_price_band: str
    top_property_type: str


def price_band_for(paise: int, bands: Sequence[PriceBand] = DEFAULT_PRICE_BANDS) -> str:
    """Return the label of the band containing ``paise``, or ``"UNKNOWN"``."""
    if paise < 0:
        return UNKNOWN
    for band in bands:
        if band.min_paise <= paise <= band.max_paise:
            return band.label
    return UNKNOWN


def _budget_midpoint(lead: Any) -> float | None:
    low, high = lead.budget_min, lead.budget_max
    if low is not None and high is not None:
        return (low + high) / 2
    single = low if low is not None else high
    return float(single) if single is not None else None


def _top_band(values: Sequence[int], bands: Sequence[PriceBand]) -> str:
    """Most common band label; ties resolve by band order, ``UNKNOWN`` if none match."""
    order = {band.label: index for index, band in enumerate(bands)}
    labels = (price_band_for(value, bands) for value in values)
    counts = Counter(label for label in labels if label != UNKNOWN)
    return min(counts, key=lambda label: (-counts[label], order[label])) if counts else UNKNOWN


def _top_property_type(leads: Sequence[Any]) -> str:
    """Most common configuration, grouped case-insensitively, ties alphabetical."""
    groups: dict[str, Counter[str]] = {}
    for lead in leads:
        raw = lead.preferred_configuration
        if raw is not None and raw.strip():
            value = raw.strip()
            groups.setdefault(value.casefold(), Counter())[value] += 1
    if not groups:
        return UNKNOWN
    # Display the most common original casing per group, then the largest group.
    displays = [
        min(counter, key=lambda value: (-counter[value], value.casefold(), value))
        for counter in groups.values()
    ]
    return min(
        displays,
        key=lambda value: (-sum(groups[value.casefold()].values()), value.casefold(), value),
    )


def aggregate_demand(
    *,
    projects: Sequence[Any],
    leads: Sequence[Any],
    bookings: Sequence[Any],
    bands: Sequence[PriceBand] = DEFAULT_PRICE_BANDS,
) -> list[LocalityDemand]:
    """Build one :class:`LocalityDemand` per project, sorted by demand then locality."""
    leads_by_project: dict[Any, list[Any]] = {}
    for lead in leads:
        leads_by_project.setdefault(lead.project_id, []).append(lead)
    bookings_by_project: dict[Any, list[Any]] = {}
    for booking in bookings:
        bookings_by_project.setdefault(booking.project_id, []).append(booking)

    results: list[LocalityDemand] = []
    for project in projects:
        project_leads = leads_by_project.get(project.id, [])
        project_bookings = bookings_by_project.get(project.id, [])
        midpoints = [
            midpoint
            for midpoint in (_budget_midpoint(lead) for lead in project_leads)
            if midpoint is not None
        ]
        considerations = [booking.consideration_paise for booking in project_bookings]
        lead_count, booking_count = len(project_leads), len(project_bookings)
        results.append(
            LocalityDemand(
                project_id=str(project.id),
                locality=project.location,
                project_name=project.name,
                lead_count=lead_count,
                booking_count=booking_count,
                conversion_pct=round(booking_count / lead_count * 100, 1) if lead_count else 0.0,
                median_budget_paise=round(median(midpoints)) if midpoints else None,
                top_price_band=_top_band([*midpoints, *considerations], bands),
                top_property_type=_top_property_type(project_leads),
            )
        )
    results.sort(key=lambda d: (-d.lead_count, d.locality, d.project_name, d.project_id))
    return results
