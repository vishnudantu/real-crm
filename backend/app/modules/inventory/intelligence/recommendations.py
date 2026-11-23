"""Deterministic, similarity-ranked recommendations for unavailable units."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

_MAX_SCORE = 100
_AREA_TOLERANCE = 0.10
_SCORING_RULES = (
    ("configuration", 35, "same configuration"),
    ("tower", 20, "same tower"),
    ("facing", 15, "same facing"),
    ("floor", 10, "same floor"),
)


class UnitLike(Protocol):
    """The unit attributes needed for recommendations, without a DB dependency."""

    id: Any
    internal_code: str
    configuration: str | None
    floor: str | None
    tower: str | None
    facing: str | None
    carpet_area_sqft: int | None
    status: str


@dataclass(frozen=True)
class UnitRecommendation:
    """An available alternative and the reasons it resembles the request."""

    unit_id: Any
    internal_code: str
    score: int
    reasons: list[str]


def _score(requested: UnitLike, candidate: UnitLike) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for attribute, points, reason in _SCORING_RULES:
        requested_value = getattr(requested, attribute)
        candidate_value = getattr(candidate, attribute)
        if requested_value is not None and requested_value == candidate_value:
            score += points
            reasons.append(reason)

    requested_area = requested.carpet_area_sqft
    candidate_area = candidate.carpet_area_sqft
    if (
        requested_area is not None
        and candidate_area is not None
        and abs(candidate_area - requested_area) <= requested_area * _AREA_TOLERANCE
    ):
        score += 20
        reasons.append("similar area")

    return min(score, _MAX_SCORE), reasons or ["available alternative"]


def recommend_alternatives(
    *,
    requested: UnitLike,
    candidates: Sequence[UnitLike],
    limit: int = 5,
) -> list[UnitRecommendation]:
    """Rank available alternatives by similarity, excluding the requested unit."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    ranked: list[UnitRecommendation] = []
    for candidate in candidates:
        if candidate.status != "AVAILABLE" or str(candidate.id) == str(requested.id):
            continue
        score, reasons = _score(requested, candidate)
        ranked.append(UnitRecommendation(
            unit_id=candidate.id,
            internal_code=candidate.internal_code,
            score=score,
            reasons=reasons,
        ))

    if any(recommendation.score > 0 for recommendation in ranked):
        ranked = [recommendation for recommendation in ranked if recommendation.score > 0]
    ranked.sort(key=lambda recommendation: (
        -recommendation.score,
        recommendation.internal_code,
    ))
    return ranked[:limit]
