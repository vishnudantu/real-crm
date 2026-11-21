"""Unit tests for India-centric validation and currency helpers."""

from __future__ import annotations

import pytest

from app.core.india import (
    format_inr,
    normalize_indian_phone,
    parse_inr_amount,
    validate_gstin,
    validate_rera_number,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("PRM/KA/RERA/1251/308/PR/200122/003188", True),
        ("P02400003892", True),
        ("RC/REP/HARERA/GGM/641/373/2022/108", False),  # legacy, no /RERA/ marker
        ("P52100012345", True),  # short P-format used by some states
        ("not-a-rera", False),
        ("PRM/KA/XERA/1251/308", False),  # marker not /RERA/
        (None, False),
    ],
)
def test_validate_rera_number(value, expected) -> None:
    assert validate_rera_number(value) is expected


def test_validate_gstin() -> None:
    assert validate_gstin("27AAECE6486H1ZQ") is True
    assert validate_gstin("27AAE6486H1ZQ") is False
    assert validate_gstin(None) is False


@pytest.mark.parametrize(
    "value,expected",
    [
        ("98765 43210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("12345", "12345"),  # too short to normalize; passthrough
        (None, None),
    ],
)
def test_normalize_indian_phone(value, expected) -> None:
    assert normalize_indian_phone(value) == expected


@pytest.mark.parametrize(
    "value,expected_paise",
    [
        ("₹85 lakh", 85 * 100_000 * 100),
        ("1.38 Cr", 1_380_000_000),
        ("95,00,000", 95 * 100_000 * 100),
        ("INR 12 crore", 12 * 10_000_000 * 100),
        ("", None),
        ("free", None),
    ],
)
def test_parse_inr_amount(value, expected_paise) -> None:
    assert parse_inr_amount(value) == expected_paise


def test_format_inr_indian_grouping() -> None:
    assert format_inr(100_000 * 100) == "₹1,00,000.00"
    assert format_inr(1_38_00_000 * 100 + 50) == "₹1,38,00,000.50"
    assert format_inr(5_00) == "₹5.00"
