"""Structural checks for the dependency-free, deterministic PDF writer."""

from __future__ import annotations

import re

import pytest

from app.modules.documents.pdf import (
    ascii_text,
    build_pdf,
    escape_pdf_text,
    format_money,
    indian_grouping,
)


def validate_pdf(pdf: bytes) -> None:
    """Validate the structural PDF pieces without requiring a third-party reader."""

    assert pdf.startswith(b"%PDF-1.4\n")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in pdf
    assert b"/Type /Pages" in pdf
    assert b"/BaseFont /Helvetica" in pdf

    match = re.search(rb"startxref\n(\d+)\n%%EOF\s*$", pdf)
    assert match is not None
    xref_offset = int(match.group(1))
    assert pdf[xref_offset:xref_offset + 4] == b"xref"
    header = pdf[xref_offset:].splitlines()
    count = int(header[1].split()[1])
    assert count > 1
    assert header[2] == b"0000000000 65535 f "
    for object_id, raw_entry in enumerate(header[3:3 + count - 1], start=1):
        entry = re.fullmatch(rb"(\d{10}) 00000 n ", raw_entry)
        assert entry is not None
        offset = int(entry.group(1))
        assert pdf[offset:].startswith(f"{object_id} 0 obj\n".encode())

    # Only the required PDF binary marker is non-ASCII; all content is literal ASCII.
    assert pdf.split(b"\n", 2)[1] == b"%\xe2\xe3\xcf\xd3"
    assert all(byte < 128 for byte in pdf.split(b"\n", 2)[2])


def test_pdf_is_valid_and_deterministic() -> None:
    body = "Customer: Example Buyer\nAmount: Rs. 12,34,567.89\n" + "\n".join(
        f"Ledger line {index} with padding content" for index in range(100)
    )
    first = build_pdf("DOC-DEMAND-000001", body)
    second = build_pdf("DOC-DEMAND-000001", body)
    assert first == second
    assert b"/Count 3" in first  # 100 wrapped lines break across three pages
    validate_pdf(first)


def test_pdf_escapes_parentheses_and_backslashes() -> None:
    assert escape_pdf_text("Amount (net) \\ path") == b"Amount \\(net\\) \\\\ path"
    pdf = build_pdf("Escaping", "Text (with) \\ symbols")
    validate_pdf(pdf)
    assert b"Text \\(with\\) \\\\ symbols" in pdf


def test_unicode_is_converted_to_printable_ascii() -> None:
    assert ascii_text("Rs. ₹ ‘quote’ — café") == "Rs. Rs. 'quote' - cafe"
    pdf = build_pdf("Unicode ₹", " café — £")
    validate_pdf(pdf)
    assert "café".encode() not in pdf
    assert "₹".encode() not in pdf


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (999, "999"),
        (1000, "1,000"),
        (100000, "1,00,000"),
        (12345678, "1,23,45,678"),
    ],
)
def test_indian_digit_grouping(value: int, expected: str) -> None:
    assert indian_grouping(value) == expected


def test_money_formatting_uses_integer_paise() -> None:
    assert format_money(123456789) == "Rs. 12,34,567.89"
    assert format_money(-105) == "-Rs. 1.05"
