"""Tenant collections reminder policy (system_settings key ``collections_reminder_policy``).

Shape (all fields optional; invalid values fall back field-by-field, like the
cancellation policy engine):

    {
      "offsets": [-7, 0, 7, 14],                  # days relative to due date
      "channels": ["WHATSAPP", "SMS", "EMAIL"],   # preference order
      "escalation_thresholds": {"warning": 30, "critical": 60, "severe": 90}
    }

Offsets are the reminder sequence: negative = before the due date, 0 = on the
due date, positive = after. Escalation thresholds are overdue ages in days at
which an account crosses into the next severity band.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.settings.repository import get_setting

POLICY_SETTING_KEY = "collections_reminder_policy"

DEFAULT_OFFSETS: tuple[int, ...] = (-7, 0, 7, 14)
DEFAULT_CHANNELS: tuple[str, ...] = ("WHATSAPP", "SMS", "EMAIL")
DEFAULT_ESCALATION_THRESHOLDS: dict[str, int] = {
    "warning": 30,
    "critical": 60,
    "severe": 90,
}
MAX_OFFSET_DAYS = 365
VALID_CHANNELS = frozenset({"WHATSAPP", "SMS", "EMAIL"})


def _valid_offsets(value: Any) -> list[int] | None:
    if not isinstance(value, list) or not value or len(value) > 24:
        return None
    offsets: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            return None
        if not -MAX_OFFSET_DAYS <= item <= MAX_OFFSET_DAYS:
            return None
        offsets.append(item)
    if len(set(offsets)) != len(offsets):
        return None
    return sorted(offsets)


def _valid_channels(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value or len(value) > 3:
        return None
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        channel = item.strip().upper()
        if channel not in VALID_CHANNELS or channel in normalized:
            return None
        normalized.append(channel)
    return normalized


def _valid_thresholds(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict) or not value:
        return None
    merged = dict(DEFAULT_ESCALATION_THRESHOLDS)
    for band, days in value.items():
        if (
            not isinstance(band, str)
            or band not in DEFAULT_ESCALATION_THRESHOLDS
            or isinstance(days, bool)
            or not isinstance(days, int)
            or not 1 <= days <= 3650
        ):
            return None
        merged[band] = days
    if not merged["warning"] < merged["critical"] < merged["severe"]:
        return None
    return merged


def validate_policy(value: Any) -> dict[str, Any]:
    """Validate a policy payload; return the normalized fields present.

    Raises ValueError naming the first invalid field so the API can return a
    precise 422. Partial payloads are allowed — absent fields keep defaults
    at resolve time.
    """

    if not isinstance(value, dict):
        raise ValueError("Policy must be a JSON object.")
    cleaned: dict[str, Any] = {}
    if "offsets" in value:
        offsets = _valid_offsets(value["offsets"])
        if offsets is None:
            raise ValueError("offsets must be a list of unique integers within +/-365 days.")
        cleaned["offsets"] = offsets
    if "channels" in value:
        channels = _valid_channels(value["channels"])
        if channels is None:
            raise ValueError("channels must be a non-empty list drawn from WHATSAPP, SMS, EMAIL.")
        cleaned["channels"] = channels
    if "escalation_thresholds" in value:
        thresholds = _valid_thresholds(value["escalation_thresholds"])
        if thresholds is None:
            raise ValueError(
                "escalation_thresholds must be increasing positive day counts "
                "for the warning, critical and severe bands."
            )
        cleaned["escalation_thresholds"] = thresholds
    return cleaned


def resolve_policy(session: Session, *, tenant_id) -> dict[str, Any]:
    """Merge the tenant's policy setting onto defaults, field-by-field.

    An unparseable value block returns pure defaults; one bad field never
    disables the rest of the policy.
    """

    policy: dict[str, Any] = {
        "offsets": list(DEFAULT_OFFSETS),
        "channels": list(DEFAULT_CHANNELS),
        "escalation_thresholds": dict(DEFAULT_ESCALATION_THRESHOLDS),
    }
    setting = get_setting(session, POLICY_SETTING_KEY, tenant_id=tenant_id)
    raw = setting.value if setting is not None and isinstance(setting.value, dict) else {}

    offsets = _valid_offsets(raw.get("offsets"))
    if offsets is not None:
        policy["offsets"] = offsets
    channels = _valid_channels(raw.get("channels"))
    if channels is not None:
        policy["channels"] = channels
    thresholds = _valid_thresholds(raw.get("escalation_thresholds"))
    if thresholds is not None:
        policy["escalation_thresholds"] = thresholds
    return policy
