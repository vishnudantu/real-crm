"""Unit tests for similarity-ranked inventory alternatives."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.inventory.intelligence.recommendations import recommend_alternatives


def make_unit(
    unit_id: str = "requested",
    internal_code: str = "A-1201",
    **overrides,
) -> SimpleNamespace:
    """Build an ORM-free unit with deliberately dissimilar defaults."""
    values = {
        "id": unit_id,
        "internal_code": internal_code,
        "configuration": "3BHK",
        "floor": "12",
        "tower": "A",
        "facing": "East",
        "carpet_area_sqft": 1_000,
        "status": "AVAILABLE",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_requested_unit_is_excluded_even_when_available() -> None:
    # Arrange
    requested = make_unit()
    candidates = [make_unit(), make_unit("other", "A-1202")]

    # Act
    results = recommend_alternatives(requested=requested, candidates=candidates)

    # Assert
    assert [result.unit_id for result in results] == ["other"]


def test_non_available_candidates_are_excluded() -> None:
    # Arrange
    requested = make_unit()
    candidates = [
        make_unit("sold", "A-1202", status="SOLD"),
        make_unit("held", "A-1203", status="ON_HOLD"),
    ]

    # Act
    results = recommend_alternatives(requested=requested, candidates=candidates)

    # Assert
    assert results == []


@pytest.mark.parametrize(
    ("overrides", "expected_score", "expected_reason"),
    [
        ({"configuration": "3BHK"}, 35, "same configuration"),
        ({"tower": "A"}, 20, "same tower"),
        ({"facing": "East"}, 15, "same facing"),
        ({"floor": "12"}, 10, "same floor"),
        ({"carpet_area_sqft": 1_050}, 20, "similar area"),
    ],
)
def test_each_matching_attribute_adds_its_score_and_reason(
    overrides: dict,
    expected_score: int,
    expected_reason: str,
) -> None:
    # Arrange
    requested = make_unit()
    candidate = make_unit(
        "candidate",
        "B-101",
        **{
            "configuration": "2BHK",
            "floor": "1",
            "tower": "B",
            "facing": "West",
            "carpet_area_sqft": 500,
            **overrides,
        },
    )

    # Act
    results = recommend_alternatives(requested=requested, candidates=[candidate])

    # Assert
    assert results[0].score == expected_score
    assert results[0].reasons == [expected_reason]


@pytest.mark.parametrize("area", [900, 1_100])
def test_area_at_ten_percent_boundaries_is_similar(area: int) -> None:
    # Arrange
    requested = make_unit()
    candidate = make_unit(
        "candidate", "B-101", configuration=None, floor=None,
        tower=None, facing=None, carpet_area_sqft=area,
    )

    # Act
    results = recommend_alternatives(requested=requested, candidates=[candidate])

    # Assert
    assert results[0].score == 20
    assert results[0].reasons == ["similar area"]


@pytest.mark.parametrize("area", [899, 1_101])
def test_area_outside_ten_percent_band_does_not_score(area: int) -> None:
    # Arrange
    requested = make_unit()
    candidate = make_unit(
        "candidate", "B-101", configuration=None, floor=None,
        tower=None, facing=None, carpet_area_sqft=area,
    )

    # Act
    results = recommend_alternatives(requested=requested, candidates=[candidate])

    # Assert
    assert results[0].score == 0
    assert results[0].reasons == ["available alternative"]


def test_reasons_follow_scoring_rule_order_and_score_is_capped() -> None:
    # Arrange
    requested = make_unit()
    candidate = make_unit("candidate", "A-1202")

    # Act
    results = recommend_alternatives(requested=requested, candidates=[candidate])

    # Assert
    assert results[0].score == 100
    assert results[0].reasons == [
        "same configuration",
        "same tower",
        "same facing",
        "same floor",
        "similar area",
    ]


def test_results_sort_by_score_descending_then_internal_code() -> None:
    # Arrange
    requested = make_unit()
    candidates = [
        make_unit("low", "B-001", configuration="2BHK", floor="1", tower="B", facing="West"),
        make_unit("tied-b", "A-003", floor="1", facing="West"),
        make_unit("tied-a", "A-002", floor="1", facing="West"),
        make_unit("best", "Z-999"),
    ]

    # Act
    results = recommend_alternatives(requested=requested, candidates=candidates)

    # Assert
    assert [(result.unit_id, result.score) for result in results] == [
        ("best", 100),
        ("tied-a", 75),
        ("tied-b", 75),
        ("low", 20),
    ]


def test_limit_truncates_ranked_results() -> None:
    # Arrange
    requested = make_unit()
    candidates = [
        make_unit("one", "A-001"),
        make_unit("two", "A-002"),
        make_unit("three", "A-003"),
    ]

    # Act
    results = recommend_alternatives(
        requested=requested, candidates=candidates, limit=2,
    )

    # Assert
    assert [result.unit_id for result in results] == ["one", "two"]


@pytest.mark.parametrize("limit", [0, -1])
def test_limit_below_one_raises_value_error(limit: int) -> None:
    # Arrange
    requested = make_unit()

    # Act / Assert
    with pytest.raises(ValueError, match="limit"):
        recommend_alternatives(requested=requested, candidates=[], limit=limit)


def test_zero_match_candidates_are_excluded_when_better_matches_exist() -> None:
    # Arrange
    requested = make_unit()
    candidates = [
        make_unit("match", "A-001", configuration="3BHK", floor="1", tower="B", facing="West", carpet_area_sqft=500),
        make_unit("zero", "A-002", configuration="2BHK", floor="1", tower="B", facing="West", carpet_area_sqft=500),
    ]

    # Act
    results = recommend_alternatives(requested=requested, candidates=candidates)

    # Assert
    assert [result.unit_id for result in results] == ["match"]


def test_zero_match_candidates_are_included_when_they_are_only_options() -> None:
    # Arrange
    requested = make_unit()
    candidates = [
        make_unit("zero-b", "A-002", configuration="2BHK", floor="1", tower="B", facing="West", carpet_area_sqft=500),
        make_unit("zero-a", "A-001", configuration="1BHK", floor="2", tower="C", facing="North", carpet_area_sqft=400),
    ]

    # Act
    results = recommend_alternatives(requested=requested, candidates=candidates)

    # Assert
    assert [result.unit_id for result in results] == ["zero-a", "zero-b"]
    assert all(result.reasons == ["available alternative"] for result in results)
