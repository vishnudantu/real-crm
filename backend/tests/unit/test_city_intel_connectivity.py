"""Unit tests for the deterministic City Intelligence connectivity scoring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.city_intel.connectivity import (
    CATEGORY_ORDER,
    CLOSE_PROXIMITY_KM,
    VALID_CATEGORIES,
    ConnectivityScore,
    connectivity_score,
    summarize_categories,
)


def _poi(
    category: str,
    *,
    distance_km: float,
    travel_minutes: int,
    name: str = "POI",
    source_ref: str | None = None,
) -> SimpleNamespace:
    """Build a minimal curated POI, mirroring the admin-authored row shape."""
    return SimpleNamespace(
        category=category,
        name=name,
        distance_km=distance_km,
        travel_minutes=travel_minutes,
        source_ref=source_ref,
    )


class TestSummaryOfEmptyInput:
    """Every category is reported even when nothing was curated."""

    def test_empty_poi_set_yields_all_categories_with_zero_counts(self) -> None:
        # Arrange / Act
        result = connectivity_score(pois=[])

        # Assert
        assert isinstance(result, ConnectivityScore)
        assert [summary.category for summary in result.by_category] == list(
            CATEGORY_ORDER
        )
        assert all(summary.count == 0 for summary in result.by_category)
        assert all(summary.nearest_km is None for summary in result.by_category)
        assert all(
            summary.nearest_travel_minutes is None for summary in result.by_category
        )
        assert result.score == 0
        assert result.notes == ["No curated points of interest yet"]


class TestSummarizeCategories:
    """Per-category counts and nearest values."""

    def test_counts_and_nearest_values_are_minima_per_category(self) -> None:
        # Arrange
        pois = [
            _poi("school", distance_km=4.0, travel_minutes=18, name="Far School"),
            _poi("school", distance_km=1.2, travel_minutes=7, name="Near School"),
            _poi("school", distance_km=2.5, travel_minutes=11, name="Mid School"),
            _poi("transit", distance_km=0.8, travel_minutes=4, name="Metro"),
        ]

        # Act
        summaries = summarize_categories(pois=pois)

        # Assert
        by_name = {summary.category: summary for summary in summaries}
        school = by_name["school"]
        assert school.count == 3
        assert school.nearest_km == 1.2
        assert school.nearest_travel_minutes == 7
        transit = by_name["transit"]
        assert transit.count == 1
        assert transit.nearest_km == 0.8
        assert transit.nearest_travel_minutes == 4
        assert by_name["hospital"].count == 0
        assert by_name["hospital"].nearest_km is None
        assert by_name["hospital"].nearest_travel_minutes is None

    def test_fixed_category_order_matches_canonical_tuple(self) -> None:
        # Arrange
        pois = [
            _poi("amenity", distance_km=1.0, travel_minutes=5),
            _poi("school", distance_km=3.0, travel_minutes=12),
        ]

        # Act
        summaries = summarize_categories(pois=pois)

        # Assert
        assert [summary.category for summary in summaries] == [
            "school",
            "hospital",
            "transit",
            "employment",
            "amenity",
        ]
        assert set(CATEGORY_ORDER) == set(VALID_CATEGORIES)


class TestConnectivityScoring:
    """Presence-based points and the close-proximity bonus."""

    def test_presence_only_without_close_poi_scores_partial_points(self) -> None:
        # Arrange: one distant school, no category has a POI within 2 km.
        pois = [_poi("school", distance_km=8.0, travel_minutes=25)]

        # Act
        result = connectivity_score(pois=pois, max_per_category=20)

        # Assert: base = 20 * min(1, 3) // 3 = 6, no proximity bonus.
        assert result.score == 6
        school = result.by_category[0]
        assert school.count == 1
        assert "Strong school access" not in result.notes

    def test_proximity_bonus_turns_a_close_category_into_full_marks(self) -> None:
        # Arrange: a single transit POI exactly at the proximity threshold.
        pois = [_poi("transit", distance_km=CLOSE_PROXIMITY_KM, travel_minutes=5)]

        # Act
        result = connectivity_score(pois=pois, max_per_category=20)

        # Assert: proximity completes the category to full marks.
        assert result.score == 20
        assert "Strong transit access" in result.notes

    def test_three_pois_without_proximity_earn_full_base_but_not_bonus(self) -> None:
        # Arrange: three distant hospitals -> full presence base, no bonus.
        pois = [
            _poi("hospital", distance_km=5.0, travel_minutes=16),
            _poi("hospital", distance_km=6.0, travel_minutes=19),
            _poi("hospital", distance_km=7.5, travel_minutes=22),
        ]

        # Act
        result = connectivity_score(pois=pois, max_per_category=20)

        # Assert: base = 20 * 3 // 3 = 20, which already fills the category.
        assert result.score == 20
        assert "Strong hospital access" in result.notes


class TestScoreBoundsAndCoverage:
    """Totals stay within 0-100 and full coverage approaches the ceiling."""

    def test_full_coverage_across_all_categories_scores_one_hundred(self) -> None:
        # Arrange: every category has a close POI so each earns full marks.
        pois = [
            _poi(category, distance_km=0.5, travel_minutes=3)
            for category in CATEGORY_ORDER
        ]

        # Act
        result = connectivity_score(pois=pois)

        # Assert
        assert result.score == 100
        assert len(result.notes) == len(CATEGORY_ORDER)

    def test_score_is_clamped_to_one_hundred_with_large_max_per_category(self) -> None:
        # Arrange: generous cap would sum to 5 * 100 = 500 without clamping.
        pois = [
            _poi(category, distance_km=0.3, travel_minutes=2)
            for category in CATEGORY_ORDER
        ]

        # Act
        result = connectivity_score(pois=pois, max_per_category=100)

        # Assert
        assert result.score == 100

    def test_score_is_never_negative_for_sparse_data(self) -> None:
        # Arrange
        pois = [_poi("amenity", distance_km=9.9, travel_minutes=30)]

        # Act
        result = connectivity_score(pois=pois)

        # Assert
        assert 0 <= result.score <= 100


class TestNotes:
    """Notes explain both gaps and strengths."""

    def test_notes_report_zero_data_categories_and_full_mark_strengths(self) -> None:
        # Arrange: only transit is curated, and it is close.
        pois = [_poi("transit", distance_km=1.0, travel_minutes=4)]

        # Act
        result = connectivity_score(pois=pois)

        # Assert
        assert "Strong transit access" in result.notes
        assert "No school data curated" in result.notes
        assert "No hospital data curated" in result.notes
        assert "No employment data curated" in result.notes
        assert "No amenity data curated" in result.notes
        assert "No transit data curated" not in result.notes


class TestValidation:
    """Reject nonsensical scoring configuration."""

    @pytest.mark.parametrize("bad_max", [0, -1, -20])
    def test_non_positive_max_per_category_raises(self, bad_max: int) -> None:
        with pytest.raises(ValueError, match="max_per_category"):
            connectivity_score(pois=[], max_per_category=bad_max)
