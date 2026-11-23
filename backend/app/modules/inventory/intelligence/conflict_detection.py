"""Pure checks for contradictory unit holds and transaction states."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UnitConflict:
    """An inconsistent relationship between a unit, holds, and its sale state."""

    unit_id: Any
    code: str
    kind: str
    detail: str


def detect_unit_conflicts(
    *,
    units: Sequence,
    active_holds: Sequence,
    sold_unit_ids: set[str],
    booked_unit_ids: set[str],
) -> list[UnitConflict]:
    """Find active-hold conflicts without querying or modifying domain state."""
    codes = {str(unit.id): unit.internal_code for unit in units}
    hold_counts = Counter(str(hold.unit_id) for hold in active_holds)
    sold_ids = {str(unit_id) for unit_id in sold_unit_ids}
    booked_ids = {str(unit_id) for unit_id in booked_unit_ids} - sold_ids
    conflicts = []

    for unit_id, count in hold_counts.items():
        code = codes.get(unit_id, unit_id)
        if unit_id not in codes:
            conflicts.append(
                UnitConflict(
                    unit_id, code, "HOLD_WITHOUT_UNIT",
                    f"Active hold references unknown unit {unit_id}",
                )
            )
        if count > 1:
            conflicts.append(
                UnitConflict(
                    unit_id, code, "MULTIPLE_ACTIVE_HOLDS",
                    f"Unit has {count} active holds",
                )
            )
        if unit_id in sold_ids:
            conflicts.append(
                UnitConflict(
                    unit_id, code, "SOLD_WITH_ACTIVE_HOLD",
                    f"Sold unit has {count} active hold(s)",
                )
            )
        elif unit_id in booked_ids:
            conflicts.append(
                UnitConflict(
                    unit_id, code, "BOOKED_WITH_ACTIVE_HOLD",
                    f"Booked unit has {count} active hold(s)",
                )
            )

    return sorted(conflicts, key=lambda item: (item.kind, item.code))
