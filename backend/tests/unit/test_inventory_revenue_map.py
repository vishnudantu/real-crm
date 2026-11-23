"""Unit tests for the deterministic inventory revenue map."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.modules.inventory.intelligence.revenue_map import RevenueMap, build_revenue_map


def _unit(
    *,
    internal_code: str,
    status: str,
    created_at: datetime,
    unit_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=unit_id or str(uuid4()),
        internal_code=internal_code,
        status=status,
        created_at=created_at,
    )


def test_empty_input_returns_zeroed_revenue_map() -> None:
    # Arrange / Act
    result = build_revenue_map(units=[], booked_values={}, today=date(2026, 11, 23))

    # Assert
    assert result == RevenueMap(
        total_units=0,
        by_status={},
        total_booked_value_paise=0,
        avg_unit_age_days=0.0,
        oldest_unit_age_days=0,
        rows=[],
    )


def test_future_created_at_has_age_clamped_to_zero() -> None:
    # Arrange
    unit = _unit(
        internal_code="A-101",
        status="AVAILABLE",
        created_at=datetime(2026, 11, 24, tzinfo=UTC),
    )

    # Act
    result = build_revenue_map(units=[unit], booked_values={}, today=date(2026, 11, 23))

    # Assert
    assert result.rows[0].age_days == 0
    assert result.avg_unit_age_days == 0.0
    assert result.oldest_unit_age_days == 0


def test_by_status_counts_each_unit_status() -> None:
    # Arrange
    created_at = datetime(2026, 11, 20, tzinfo=UTC)
    units = [
        _unit(internal_code="A-101", status="AVAILABLE", created_at=created_at),
        _unit(internal_code="A-102", status="AVAILABLE", created_at=created_at),
        _unit(internal_code="B-101", status="BOOKED", created_at=created_at),
    ]

    # Act
    result = build_revenue_map(units=units, booked_values={}, today=date(2026, 11, 23))

    # Assert
    assert result.total_units == 3
    assert result.by_status == {"AVAILABLE": 2, "BOOKED": 1}


def test_booked_value_is_attached_only_to_units_in_value_map() -> None:
    # Arrange
    booked = _unit(
        internal_code="A-101",
        status="BOOKED",
        created_at=datetime(2026, 11, 20, tzinfo=UTC),
    )
    available = _unit(
        internal_code="A-102",
        status="AVAILABLE",
        created_at=datetime(2026, 11, 21, tzinfo=UTC),
    )

    # Act
    result = build_revenue_map(
        units=[booked, available],
        booked_values={str(booked.id): 1_250_000},
        today=date(2026, 11, 23),
    )

    # Assert
    values_by_code = {row.internal_code: row.booked_value_paise for row in result.rows}
    assert values_by_code == {"A-101": 1_250_000, "A-102": None}
    assert result.total_booked_value_paise == 1_250_000


def test_rows_are_sorted_by_oldest_age_then_internal_code() -> None:
    # Arrange
    units = [
        _unit(
            internal_code="C-301",
            status="AVAILABLE",
            created_at=datetime(2026, 11, 22, tzinfo=UTC),
        ),
        _unit(
            internal_code="B-201",
            status="AVAILABLE",
            created_at=datetime(2026, 11, 20, tzinfo=UTC),
        ),
        _unit(
            internal_code="A-101",
            status="AVAILABLE",
            created_at=datetime(2026, 11, 20, tzinfo=UTC),
        ),
    ]

    # Act
    result = build_revenue_map(units=units, booked_values={}, today=date(2026, 11, 23))

    # Assert
    assert [(row.internal_code, row.age_days) for row in result.rows] == [
        ("A-101", 3),
        ("B-201", 3),
        ("C-301", 1),
    ]


def test_average_and_oldest_age_are_computed_from_all_units() -> None:
    # Arrange
    units = [
        _unit(
            internal_code="A-101",
            status="AVAILABLE",
            created_at=datetime(2026, 11, 13, tzinfo=UTC),
        ),
        _unit(
            internal_code="A-102",
            status="AVAILABLE",
            created_at=datetime(2026, 11, 20, tzinfo=UTC),
        ),
    ]

    # Act
    result = build_revenue_map(units=units, booked_values={}, today=date(2026, 11, 23))

    # Assert
    assert result.avg_unit_age_days == 6.5
    assert result.oldest_unit_age_days == 10
