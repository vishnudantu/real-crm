"""Executive cockpit: read-only cross-module aggregation for tenant leadership."""

from app.modules.executive.service import cockpit
from app.modules.executive.schemas import BriefingResponse, CockpitResponse

__all__ = ["BriefingResponse", "CockpitResponse", "cockpit"]
