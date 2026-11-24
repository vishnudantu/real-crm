"""Deterministic connectivity scoring from admin-curated points of interest.

No geocoding, external APIs, or database access: every figure comes from the
curated POI rows supplied by the caller, so the score is reproducible.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "CATEGORY_ORDER",
    "CLOSE_PROXIMITY_KM",
    "VALID_CATEGORIES",
    "CategorySummary",
    "ConnectivityScore",
    "connectivity_score",
    "summarize_categories",
]

VALID_CATEGORIES = frozenset({"school", "hospital", "transit", "employment", "amenity"})

# Fixed presentation order; the by_category list always follows this sequence.
CATEGORY_ORDER = ("school", "hospital", "transit", "employment", "amenity")

# A POI at or under this distance is "close" and earns its category full marks.
CLOSE_PROXIMITY_KM = 2.0


@dataclass(frozen=True)
class CategorySummary:
    """Aggregated view of one POI category."""

    category: str
    count: int
    nearest_km: float | None
    nearest_travel_minutes: int | None


@dataclass(frozen=True)
class ConnectivityScore:
    """Explainable connectivity score (0-100) with per-category evidence."""

    score: int
    by_category: list[CategorySummary]
    notes: list[str]


def summarize_categories(*, pois: Sequence) -> list[CategorySummary]:
    """Return one summary per category in fixed order, including empty ones."""
    buckets: dict[str, list] = {category: [] for category in CATEGORY_ORDER}
    for poi in pois:
        bucket = buckets.get(getattr(poi, "category", None))
        if bucket is not None:
            bucket.append(poi)

    summaries: list[CategorySummary] = []
    for category in CATEGORY_ORDER:
        bucket = buckets[category]
        distances = [poi.distance_km for poi in bucket if poi.distance_km is not None]
        minutes = [
            poi.travel_minutes for poi in bucket if poi.travel_minutes is not None
        ]
        summaries.append(
            CategorySummary(
                category=category,
                count=len(bucket),
                nearest_km=min(distances) if distances else None,
                nearest_travel_minutes=min(minutes) if minutes else None,
            )
        )
    return summaries


def connectivity_score(
    *, pois: Sequence, max_per_category: int = 20
) -> ConnectivityScore:
    """Score a project's connectivity from its curated POI set.

    Each category earns up to ``max_per_category`` points: a presence base
    scaled by count (capped at 3), replaced by full marks when any POI there is
    within ``CLOSE_PROXIMITY_KM``. The total is clamped to 0-100.
    """
    if max_per_category <= 0:
        raise ValueError("max_per_category must be a positive integer")

    by_category = summarize_categories(pois=pois)
    if not pois:
        return ConnectivityScore(
            score=0,
            by_category=by_category,
            notes=["No curated points of interest yet"],
        )

    close_categories = {
        poi.category for poi in pois
        if poi.distance_km is not None and poi.distance_km <= CLOSE_PROXIMITY_KM
    }

    total = 0
    notes: list[str] = []
    for summary in by_category:
        category = summary.category
        if summary.count == 0:
            notes.append(f"No {category} data curated")
            continue
        is_full = category in close_categories
        points = (
            max_per_category
            if is_full
            else max_per_category * min(summary.count, 3) // 3
        )
        total += points
        if points >= max_per_category:
            notes.append(f"Strong {category} access")

    return ConnectivityScore(
        score=max(0, min(100, total)),
        by_category=by_category,
        notes=notes,
    )
