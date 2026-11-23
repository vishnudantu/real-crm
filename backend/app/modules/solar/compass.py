"""Compass bearing utilities: 16-point labels, validation, normalization."""

from __future__ import annotations

__all__ = [
    "COMPASS_LABELS",
    "bearing_to_compass",
    "normalize_bearing",
    "validate_bearing",
]

# 16-point compass rose, clockwise from north.
COMPASS_LABELS: tuple[str, ...] = (
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
)

_SECTOR_DEG = 360.0 / len(COMPASS_LABELS)  # 22.5°


def normalize_bearing(bearing: float) -> float:
    """Normalize a bearing to the range [0, 360)."""
    return bearing % 360.0


def validate_bearing(bearing: float) -> float:
    """Validate that a bearing is in [0, 360). Returns the normalized value.

    Raises ``ValueError`` if the input is not a finite number or if the
    caller supplies a value outside [0, 360] (360 is accepted and mapped
    to 0 for convenience).
    """
    if not isinstance(bearing, (int, float)):
        raise ValueError(f"bearing must be numeric, got {type(bearing).__name__}")
    if bearing != bearing:  # NaN check
        raise ValueError("bearing must be a finite number")
    if bearing < 0 or bearing > 360:
        raise ValueError(f"bearing must be in [0, 360], got {bearing}")
    return normalize_bearing(float(bearing))


def bearing_to_compass(bearing: float) -> str:
    """Convert a bearing (degrees clockwise from north) to a 16-point label.

    The bearing is first normalized to [0, 360) then snapped to the nearest
    compass sector.
    """
    normalized = normalize_bearing(bearing)
    index = int((normalized + _SECTOR_DEG / 2) / _SECTOR_DEG) % len(COMPASS_LABELS)
    return COMPASS_LABELS[index]
