"""Unit tests for deterministic unit-state conflict detection."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from app.modules.inventory.intelligence.conflict_detection import detect_unit_conflicts

_UNIT_UUID = UUID("12345678-1234-5678-1234-567812345678")


def _unit(unit_id: object, code: str = "A-101") -> SimpleNamespace:
    return SimpleNamespace(id=unit_id, internal_code=code)


def _hold(unit_id: object) -> SimpleNamespace:
    return SimpleNamespace(unit_id=unit_id)


def test_multiple_active_holds_are_flagged_once_with_count() -> None:
    # Arrange
    units = [_unit("unit-1")]
    active_holds = [_hold("unit-1"), _hold("unit-1"), _hold("unit-1")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids=set(),
        booked_unit_ids=set(),
    )

    # Assert
    assert len(result) == 1
    assert result[0].kind == "MULTIPLE_ACTIVE_HOLDS"
    assert "3" in result[0].detail


def test_active_hold_for_unknown_unit_is_flagged_with_unit_id() -> None:
    # Arrange
    units = [_unit("known-unit")]
    active_holds = [_hold("missing-unit")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids=set(),
        booked_unit_ids=set(),
    )

    # Assert
    assert len(result) == 1
    assert result[0].kind == "HOLD_WITHOUT_UNIT"
    assert "missing-unit" in result[0].detail


def test_sold_unit_with_active_hold_is_flagged() -> None:
    # Arrange
    units = [_unit("unit-1")]
    active_holds = [_hold("unit-1")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids={"unit-1"},
        booked_unit_ids=set(),
    )

    # Assert
    assert [item.kind for item in result] == ["SOLD_WITH_ACTIVE_HOLD"]


def test_booked_unit_with_active_hold_is_not_double_flagged_as_sold() -> None:
    # Arrange
    units = [_unit("booked-unit", "B-101"), _unit("sold-unit", "S-101")]
    active_holds = [_hold("booked-unit"), _hold("sold-unit")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids={"sold-unit", "booked-unit"},
        booked_unit_ids={"booked-unit"},
    )

    # Assert
    booked_conflicts = [item for item in result if item.unit_id == "booked-unit"]
    assert [item.kind for item in booked_conflicts] == ["SOLD_WITH_ACTIVE_HOLD"]
    assert {item.kind for item in result} == {"SOLD_WITH_ACTIVE_HOLD"}


def test_booked_unit_with_active_hold_is_flagged() -> None:
    # Arrange
    units = [_unit("unit-1")]
    active_holds = [_hold("unit-1")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids=set(),
        booked_unit_ids={"unit-1"},
    )

    # Assert
    assert [item.kind for item in result] == ["BOOKED_WITH_ACTIVE_HOLD"]


def test_uuid_and_string_ids_refer_to_the_same_unit() -> None:
    # Arrange
    units = [_unit(_UNIT_UUID)]
    active_holds = [_hold(str(_UNIT_UUID)), _hold(_UNIT_UUID)]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids={str(_UNIT_UUID)},
        booked_unit_ids=set(),
    )

    # Assert
    assert {item.kind for item in result} == {
        "MULTIPLE_ACTIVE_HOLDS",
        "SOLD_WITH_ACTIVE_HOLD",
    }
    assert all(item.code == "A-101" for item in result)


def test_empty_inputs_yield_no_conflicts() -> None:
    # Arrange / Act
    result = detect_unit_conflicts(
        units=[],
        active_holds=[],
        sold_unit_ids=set(),
        booked_unit_ids=set(),
    )

    # Assert
    assert result == []


def test_conflicts_sort_by_kind_then_code() -> None:
    # Arrange
    units = [_unit("unit-b", "B-101"), _unit("unit-a", "A-101")]
    active_holds = [_hold("unit-b"), _hold("unit-a"), _hold("unit-a")]

    # Act
    result = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids=set(),
        booked_unit_ids={"unit-b"},
    )

    # Assert
    assert [(item.kind, item.code) for item in result] == [
        ("BOOKED_WITH_ACTIVE_HOLD", "B-101"),
        ("MULTIPLE_ACTIVE_HOLDS", "A-101"),
    ]
