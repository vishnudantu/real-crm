"""Unit tests for sun-exposure scoring."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.solar.scoring import SunScore, score_unit_facing

_HYD_LAT = 17.38
_HYD_LNG = 78.48


class TestExposureClassification:
    """Tests for the four exposure categories."""

    def test_east_facing_morning(self) -> None:
        score = score_unit_facing(90, _HYD_LAT, _HYD_LNG)
        assert score.exposure_class == "morning"
        assert score.facing_label == "E"
        assert score.comfort_score >= 80

    def test_west_facing_afternoon(self) -> None:
        score = score_unit_facing(270, _HYD_LAT, _HYD_LNG)
        assert score.exposure_class == "afternoon"
        assert score.facing_label == "W"
        assert score.comfort_score <= 50

    def test_north_facing_diffused(self) -> None:
        score = score_unit_facing(0, _HYD_LAT, _HYD_LNG)
        assert score.exposure_class == "diffused"
        assert score.facing_label == "N"
        assert score.comfort_score >= 70

    def test_south_facing_bright(self) -> None:
        score = score_unit_facing(180, _HYD_LAT, _HYD_LNG)
        assert score.exposure_class == "bright"
        assert score.facing_label == "S"
        assert 50 <= score.comfort_score <= 70


class TestCornerBonus:
    """Corner-facing units get a small comfort bonus."""

    def test_northeast(self) -> None:
        score = score_unit_facing(45, _HYD_LAT, _HYD_LNG)
        assert score.facing_label == "NE"
        assert score.comfort_score >= 85  # 80 base + 5 corner bonus

    def test_southwest(self) -> None:
        score = score_unit_facing(225, _HYD_LAT, _HYD_LNG)
        assert score.facing_label == "SW"
        # SW is west sector (afternoon), gets corner bonus.
        assert score.comfort_score > 40


class TestVastuNote:
    """Vastu notes are factual, not guarantees."""

    def test_east_traditionally_preferred(self) -> None:
        score = score_unit_facing(90, _HYD_LAT, _HYD_LNG)
        assert "traditionally preferred" in score.vastu_note.lower()

    def test_north_traditionally_preferred(self) -> None:
        score = score_unit_facing(0, _HYD_LAT, _HYD_LNG)
        assert "traditionally preferred" in score.vastu_note.lower()

    def test_west_requires_care(self) -> None:
        score = score_unit_facing(270, _HYD_LAT, _HYD_LNG)
        assert "care" in score.vastu_note.lower()


class TestPricingHint:
    """Pricing hints are advisory and clearly approximate."""

    def test_east_premium_range(self) -> None:
        score = score_unit_facing(90, _HYD_LAT, _HYD_LNG)
        assert score.pricing_premium_min_pct >= 0
        assert score.pricing_premium_max_pct > score.pricing_premium_min_pct
        assert "advisory" in score.pricing_advisory.lower()

    def test_west_discount_or_neutral(self) -> None:
        score = score_unit_facing(270, _HYD_LAT, _HYD_LNG)
        assert score.pricing_premium_min_pct <= 0

    def test_corner_gets_extra_premium(self) -> None:
        east = score_unit_facing(90, _HYD_LAT, _HYD_LNG)
        ne = score_unit_facing(45, _HYD_LAT, _HYD_LNG)
        assert ne.pricing_premium_min_pct >= east.pricing_premium_min_pct


class TestScoreDataclass:
    def test_returns_sun_score(self) -> None:
        score = score_unit_facing(90, _HYD_LAT, _HYD_LNG)
        assert isinstance(score, SunScore)

    def test_custom_scoring_date(self) -> None:
        score = score_unit_facing(
            90, _HYD_LAT, _HYD_LNG, scoring_date=date(2026, 6, 21)
        )
        assert isinstance(score, SunScore)

    def test_bearing_normalized(self) -> None:
        score = score_unit_facing(370, _HYD_LAT, _HYD_LNG)
        assert score.facing_bearing == 10.0
