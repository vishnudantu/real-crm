"""India-centric helpers: RERA/GSTIN validation, INR parsing, phone normalization."""

from __future__ import annotations

import re

# Real Estate (Regulation and Development) Act registration numbers. States
# publish different shapes; the reliable markers are a compound form that
# contains "/RERA/" (e.g. PRM/KA/RERA/1251/308/PR/200122/003188 or the legacy
# RC/REP/HARERA/GGM/641/373/2022/108) and the short P-number form used by some
# states (e.g. P02400003892).
_RERA_COMPOUND = re.compile(r"^[A-Z0-9]+(?:/[A-Z0-9]+)+$", re.I)
_RERA_MARKER = "/RERA/"
_RERA_SHORT = re.compile(r"^P\d{9,12}$")

_GSTIN = re.compile(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$"
)

_LAKH_CRORE = re.compile(
    r"(₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lac|l|thousand|k)?",
    re.I,
)


def validate_rera_number(value: str | None) -> bool:
    """Accept compound RERA numbers (containing /RERA/) and short P-formats."""

    if not value:
        return False
    cleaned = value.strip().upper()
    if _RERA_MARKER in cleaned and _RERA_COMPOUND.match(cleaned):
        return True
    return bool(_RERA_SHORT.match(cleaned))


def validate_gstin(value: str | None) -> bool:
    """Validate an Indian GSTIN (15-character Goods & Services Tax ID)."""

    if not value:
        return False
    return bool(_GSTIN.match(value.strip().upper()))


def normalize_indian_phone(value: str | None) -> str | None:
    """Normalize to +91XXXXXXXXXX for 10-digit Indian mobiles; pass through others."""

    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10 and digits.startswith(("6", "7", "8", "9")):
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return value.strip()


def parse_inr_amount(value: str | None) -> int | None:
    """Parse Indian currency strings ('85 lakh', '1.38 Cr', '₹95,00,000') into paise."""

    if not value:
        return None
    match = _LAKH_CRORE.search(value)
    if match is None:
        return None
    number, unit = match.group(2), (match.group(3) or "").lower()
    try:
        amount = float(number.replace(",", ""))
    except ValueError:
        return None
    multipliers = {
        "crore": 10_000_000,
        "cr": 10_000_000,
        "lakh": 100_000,
        "lac": 100_000,
        "l": 100_000,
        "thousand": 1_000,
        "k": 1_000,
        "": 1,
    }
    # Bare comma-formatted numbers like '95,00,000' already parse correctly.
    if not unit and "," in number and len(number.replace(",", "")) <= 9:
        pass
    rupees = amount * multipliers.get(unit, 1)
    return int(round(rupees * 100))


def format_inr(paise: int) -> str:
    """Format paise using the Indian digit-grouping convention (₹1,00,000.00)."""

    rupees = paise / 100
    whole = int(rupees)
    frac = round((rupees - whole) * 100)
    digits = str(whole)
    if len(digits) <= 3:
        grouped = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        chunks: list[str] = []
        while len(rest) > 2:
            chunks.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            chunks.insert(0, rest)
        grouped = ",".join(chunks) + "," + last3
    return f"₹{grouped}.{frac:02d}"
