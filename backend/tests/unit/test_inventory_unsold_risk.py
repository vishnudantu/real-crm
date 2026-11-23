"""Unit tests for explainable unsold-inventory risk scoring."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.inventory.intelligence.unsold_risk import predict_unsold_risk

_TODAY = date(2026, 11, 23)


def _unit(
    code: str,
    *,
    status: str = "AVAILABLE",
    days_ago: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"unit-{code}",
        internal_code=code,
        status=status,
        created_at=datetime.combine(_TODAY - timedelta(days=days_ago), datetime.min.time(), UTC),
    )


def test_non_available_units_are_not_scored() -> None:
    # Arrange
    units = [
        _unit("AVAILABLE-1"),
        *[_unit(status, status=status) for status in ("SOLD", "BOOKED", "ON_HOLD", "DRAFT")],
    ]

    # Act
    result = predict_unsold_risk(units=units, today=_TODAY)

    # Assert
    assert [item.internal_code for item in result] == ["AVAILABLE-1"]


@pytest.mark.parametrize(
    ("days_available", "expected_risk"),
    [(59, "LOW"), (60, "MEDIUM"), (119, "MEDIUM"), (120, "HIGH")],
)
def test_risk_thresholds_include_their_boundary_days(
    days_available: int,
    expected_risk: str,
) -> None:
    # Arrange
    units = [_unit("A-101", days_ago=days_available)]

    # Act
    result = predict_unsold_risk(units=units, today=_TODAY)

    # Assert
    assert result[0].days_available == days_available
    assert result[0].risk == expected_risk


def test_future_creation_date_clamps_days_available_to_zero() -> None:
    # Arrange
    units = [_unit("FUTURE-1", days_ago=-10)]

    # Act
    result = predict_unsold_risk(units=units, today=_TODAY)

    # Assert
    assert result[0].days_available == 0
    assert result[0].risk == "LOW"


@pytest.mark.parametrize(
    ("medium_days", "high_days"),
    [(0, 120), (-1, 120), (60, 60), (61, 60)],
)
def test_invalid_thresholds_raise_value_error(
    medium_days: int,
    high_days: int,
) -> None:
    # Arrange
    units = [_unit("A-101")]

    # Act / Assert
    with pytest.raises(ValueError, match="high_days > medium_days > 0"):
        predict_unsold_risk(
            units=units,
            today=_TODAY,
            medium_days=medium_days,
            high_days=high_days,
        )


def test_results_sort_oldest_first_then_by_internal_code() -> None:
    # Arrange
    units = [
        _unit("B-102", days_ago=60),
        _unit("A-101", days_ago=120),
        _unit("A-102", days_ago=60),
        _unit("C-101", days_ago=30),
    ]

    # Act
    result = predict_unsold_risk(units=units, today=_TODAY)

    # Assert
    assert [item.internal_code for item in result] == [
        "A-101",
        "A-102",
        "B-102",
        "C-101",
    ]
