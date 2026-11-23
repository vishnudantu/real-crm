"""Project-type-specific unit authoring rules (write-path only).

The check lives here as a pure function so the service can apply exactly the
same contract on create, bulk create and update without coupling the module to
Pydantic or SQLAlchemy objects. Existing rows are never revalidated: the
function is called only when an author submits new or edited fields.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Ground/basement block labels accepted as a villa/plot "floor". A villa may be
# authored with its ground level ("G", "GF") or basement ("B", "B1", ...), but
# never with a numbered storey, which belongs to apartment/commercial towers.
_BLOCK_FLOOR_PATTERN = re.compile(r"^(?:G|GF|GROUND|B(?:\d{0,2})?)$", re.IGNORECASE)


def _present(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def validate_unit_for_project_type(
    project_type: str | None, unit_fields: Mapping[str, Any]
) -> list[str]:
    """Return human-readable errors for a unit under the project's type.

    ``project_type=None`` and ``MIXED`` impose no per-type restrictions, so
    legacy projects and mixed developments keep their existing write behavior.
    A commercial unit may identify itself with a suite code in
    ``internal_code``; that reuse needs no dedicated error case here.
    """

    if project_type is None or project_type == "MIXED":
        return []

    tower = unit_fields.get("tower")
    floor = unit_fields.get("floor")
    plot_number = unit_fields.get("plot_number")
    errors: list[str] = []

    if project_type in ("APARTMENT", "COMMERCIAL"):
        if not _present(tower):
            errors.append(f"Tower is required for {project_type.lower()} units.")
        if not _present(floor):
            errors.append(f"Floor is required for {project_type.lower()} units.")
        if project_type == "APARTMENT" and _present(plot_number):
            errors.append("Plot number must be empty for apartment units.")
        return errors

    if project_type in ("VILLA", "PLOT"):
        if not _present(plot_number):
            errors.append(f"Plot number is required for {project_type.lower()} units.")
        if _present(tower):
            errors.append(f"Tower must be empty for {project_type.lower()} units.")
        if _present(floor) and not _BLOCK_FLOOR_PATTERN.fullmatch(str(floor).strip()):
            errors.append(
                "Floor must be empty or a ground/basement block such as G or B1 "
                f"for {project_type.lower()} units."
            )
        return errors

    # The column/enum restrict persisted values; tolerate future types rather
    # than rejecting rows if the enum is extended before this mapping is.
    return []
