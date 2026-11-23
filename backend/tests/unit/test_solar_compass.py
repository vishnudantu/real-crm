"""Unit tests for compass bearing utilities."""

from __future__ import annotations

import pytest

from app.modules.solar.compass import (
    COMPASS_LABELS,
    bearing_to_compass,
    normalize_bearing,
    validate_bearing,
)


class TestCompassLabels:
    """Tests for 16-point compass conversion."""

    @pytest.mark.parametrize(
        "bearing,expected",
        [
            (0, "N"),
            (22.5, "NNE"),
            (45, "NE"),
            (67.5, "ENE"),
            (90, "E"),
            (112.5, "ESE"),
            (135, "SE"),
            (157.5, "SSE"),
            (180, "S"),
            (202.5, "SSW"),
            (225, "SW"),
            (247.5, "WSW"),
            (270, "W"),
            (292.5, "WNW"),
            (315, "NW"),
            (337.5, "NNW"),
        ],
    )
    def test_cardinal_and_intercardinal(self, bearing: float, expected: str) -> None:
        assert bearing_to_compass(bearing) == expected

    def test_wraparound(self) -> None:
        assert bearing_to_compass(359) == "N"
        assert bearing_to_compass(360) == "N"
        assert bearing_to_compass(361) == "N"

    def test_all_labels_covered(self) -> None:
        """Every 22.5° sector maps to a unique label."""
        seen = set()
        for i in range(16):
            label = bearing_to_compass(i * 22.5)
            assert label in COMPASS_LABELS
            seen.add(label)
        assert len(seen) == 16


class TestNormalizeBearing:
    def test_positive(self) -> None:
        assert normalize_bearing(90) == 90.0

    def test_wrap(self) -> None:
        assert normalize_bearing(370) == 10.0
        assert normalize_bearing(720) == 0.0

    def test_negative(self) -> None:
        assert normalize_bearing(-10) == 350.0


class TestValidateBearing:
    def test_valid(self) -> None:
        assert validate_bearing(0) == 0.0
        assert validate_bearing(180) == 180.0
        assert validate_bearing(360) == 0.0  # normalized

    def test_invalid_range(self) -> None:
        with pytest.raises(ValueError, match="bearing must be in"):
            validate_bearing(361)
        with pytest.raises(ValueError, match="bearing must be in"):
            validate_bearing(-1)

    def test_nan(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            validate_bearing(float("nan"))

    def test_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="numeric"):
            validate_bearing("north")  # type: ignore[arg-type]
