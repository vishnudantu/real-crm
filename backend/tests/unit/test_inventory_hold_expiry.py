"""Unit tests for active-hold expiry risk heuristics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.inventory.intelligence.hold_expiry import assess_hold_expiry


_NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _hold(
    hold_id: str,
    *,
    hours_remaining: float,
    state: str = "ACTIVE",
    extension_count: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=hold_id,
        unit_id=f"unit-{hold_id}",
        state=state,
        expires_at=_NOW + timedelta(hours=hours_remaining),
        extension_count=extension_count,
    )


def test_non_active_holds_are_ignored() -> None:
    # Arrange
    holds = [
        _hold("active", hours_remaining=12),
        *[
            _hold(state.lower(), hours_remaining=1, state=state)
            for state in ("EXPIRED", "CONVERTED", "RELEASED", "CANCELLED")
        ],
    ]

    # Act
    result = assess_hold_expiry(holds=holds, now=_NOW)

    # Assert
    assert [risk.hold_id for risk in result] == ["active"]


@pytest.mark.parametrize("hours_remaining", [-2, 0, 6])
def test_holds_expired_or_due_within_six_hours_are_high_risk(
    hours_remaining: float,
) -> None:
    # Arrange
    hold = _hold("urgent", hours_remaining=hours_remaining)

    # Act
    result = assess_hold_expiry(holds=[hold], now=_NOW)

    # Assert
    assert result[0].risk == "HIGH"
    assert result[0].hours_remaining == pytest.approx(hours_remaining)


def test_holds_due_within_twenty_four_hours_are_medium_risk() -> None:
    # Arrange
    hold = _hold("today", hours_remaining=24)

    # Act
    result = assess_hold_expiry(holds=[hold], now=_NOW)

    # Assert
    assert result[0].risk == "MEDIUM"


def test_holds_beyond_twenty_four_hours_are_low_risk() -> None:
    # Arrange
    hold = _hold("later", hours_remaining=48)

    # Act
    result = assess_hold_expiry(holds=[hold], now=_NOW)

    # Assert
    assert result[0].risk == "LOW"
    assert result[0].extension_count == 0


@pytest.mark.parametrize(
    "hours_remaining,expected_risk",
    [(48, "MEDIUM"), (12, "HIGH"), (6, "HIGH"), (-1, "HIGH")],
)
def test_no_extensions_left_bumps_risk_and_caps_at_high(
    hours_remaining: float,
    expected_risk: str,
) -> None:
    # Arrange
    hold = _hold("extended", hours_remaining=hours_remaining, extension_count=2)

    # Act
    result = assess_hold_expiry(holds=[hold], now=_NOW)

    # Assert
    assert result[0].risk == expected_risk


def test_risks_are_sorted_with_most_urgent_hold_first() -> None:
    # Arrange
    holds = [
        _hold("later", hours_remaining=48),
        _hold("expired", hours_remaining=-1),
        _hold("soon", hours_remaining=3),
    ]

    # Act
    result = assess_hold_expiry(holds=holds, now=_NOW)

    # Assert
    assert [risk.hold_id for risk in result] == ["expired", "soon", "later"]
    assert result[0].expires_at == _NOW - timedelta(hours=1)
    assert result[0].unit_id == "unit-expired"
