"""Sun-exposure classification, comfort scoring, Vastu notes, pricing hints.

Scoring model
-------------
Given a unit's facing bearing and the site's latitude/longitude, the module
classifies the unit into one of four exposure categories and produces:

- A **comfort score** (0-100) reflecting thermal comfort for Indian conditions.
- A **Vastu-alignment note** (factual framing, not a guarantee).
- A **pricing-premium hint** (advisory percentage range, clearly approximate).

The scoring is deterministic and India-first: east-facing units score highest
because they receive morning sun without afternoon heat. West-facing units
score lowest due to harsh afternoon sun. North-facing units get diffused
light (cool, comfortable). South-facing units are bright and warm.

Corner units (e.g. NE, SE, NW, SW) receive a small bonus for cross-ventilation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.solar.compass import bearing_to_compass, normalize_bearing

__all__ = [
    "SunScore",
    "score_unit_facing",
]


@dataclass(frozen=True)
class SunScore:
    """Result of a unit-facing sun-exposure assessment."""

    facing_bearing: float  # normalized [0, 360)
    facing_label: str  # 16-point compass label
    exposure_class: str  # "morning", "afternoon", "diffused", "bright"
    comfort_score: int  # 0-100
    vastu_note: str
    pricing_premium_min_pct: float  # advisory lower bound
    pricing_premium_max_pct: float  # advisory upper bound
    pricing_advisory: str  # human-readable advisory string


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_exposure(bearing: float) -> str:
    """Classify a bearing into one of four exposure categories."""
    normalized = normalize_bearing(bearing)
    if 45 <= normalized < 135:
        return "morning"  # East-facing sector
    if 135 <= normalized < 225:
        return "bright"  # South-facing sector
    if 225 <= normalized < 315:
        return "afternoon"  # West-facing sector
    return "diffused"  # North-facing sector (315-360, 0-45)


def _base_comfort_score(exposure: str) -> int:
    """Return a base comfort score by exposure class."""
    return {
        "morning": 85,  # Preferred — cooler, energising
        "diffused": 75,  # Cool, comfortable, even light
        "bright": 60,  # Warm, bright — can be hot in summer
        "afternoon": 40,  # Harsh afternoon heat in India
    }[exposure]


def _corner_bonus(label: str) -> int:
    """Small bonus for corner-facing units (cross-ventilation)."""
    if len(label) >= 2 and label not in ("N", "E", "S", "W"):
        return 5
    return 0


def _vastu_note(exposure: str, label: str) -> str:
    """Return a factual Vastu-alignment note (not a guarantee)."""
    notes = {
        "morning": (
            "East-facing units are traditionally preferred in Vastu Shastra "
            "for morning sunlight and positive energy flow."
        ),
        "diffused": (
            "North-facing units are traditionally preferred in Vastu Shastra "
            "for cool, diffused light throughout the day."
        ),
        "bright": (
            "South-facing units receive bright, warm light. In Vastu Shastra, "
            "south-facing is generally acceptable but may need shading in summer."
        ),
        "afternoon": (
            "West-facing units receive strong afternoon sun. In Vastu Shastra, "
            "west and south-west orientations traditionally require care — "
            "consider shading and ventilation."
        ),
    }
    base = notes[exposure]
    if len(label) >= 2 and label not in ("N", "E", "S", "W"):
        base += " Corner orientation adds cross-ventilation benefit."
    return base


def _pricing_premium(exposure: str, label: str) -> tuple[float, float, str]:
    """Return advisory pricing premium range (min_pct, max_pct, description)."""
    base_ranges = {
        "morning": (3.0, 7.0),
        "diffused": (1.0, 4.0),
        "bright": (0.0, 2.0),
        "afternoon": (-2.0, 0.0),
    }
    min_pct, max_pct = base_ranges[exposure]
    # Corner units get a small additional premium.
    if len(label) >= 2 and label not in ("N", "E", "S", "W"):
        min_pct += 1.0
        max_pct += 2.0
    advisory = (
        f"Advisory premium: {min_pct:+.0f}% to {max_pct:+.0f}%. "
        "This is approximate and should be validated against local market data."
    )
    return min_pct, max_pct, advisory


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_unit_facing(
    facing_bearing: float,
    latitude: float,
    longitude: float,
) -> SunScore:
    """Compute a sun-exposure score for a unit.

    Parameters
    ----------
    facing_bearing : float
        The unit's facing bearing in degrees (0-360, clockwise from north).
    latitude : float
        Site latitude in degrees.
    longitude : float
        Site longitude in degrees.

    Returns
    -------
    SunScore
        Comfort score, Vastu note, and advisory pricing hint.
    """
    normalized = normalize_bearing(facing_bearing)
    label = bearing_to_compass(normalized)
    exposure = _classify_exposure(normalized)
    base = _base_comfort_score(exposure)
    bonus = _corner_bonus(label)
    comfort = min(100, base + bonus)
    note = _vastu_note(exposure, label)
    min_pct, max_pct, advisory = _pricing_premium(exposure, label)

    return SunScore(
        facing_bearing=normalized,
        facing_label=label,
        exposure_class=exposure,
        comfort_score=comfort,
        vastu_note=note,
        pricing_premium_min_pct=min_pct,
        pricing_premium_max_pct=max_pct,
        pricing_advisory=advisory,
    )
