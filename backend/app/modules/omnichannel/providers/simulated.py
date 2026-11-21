"""Deterministic no-network providers for development and test environments."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.modules.omnichannel.providers.base import CallProvider, MessageProvider


class SimulatedMessageProvider:
    """Return a stable external id without contacting any external service."""

    def send_text(self, *, recipient: str, text: str, credentials: dict, config: dict) -> str:
        seed = f"{recipient}:{text}:{datetime.now(UTC).isoformat()}"
        return "sim-msg-" + hashlib.sha256(seed.encode()).hexdigest()[:24]


class SimulatedCallProvider:
    """Model a LiveKit-like call lifecycle with no telephony dependency.

    Used when a tenant selects the ``simulated`` provider: the webapp's call
    UI, state transitions, and recording artifacts are fully exercised without
    a running media server. Production tenants select ``livekit`` instead.
    """

    def create_room(self, *, room_name: str, credentials: dict, config: dict) -> dict:
        return {"sid": "sim-room-" + hashlib.sha256(room_name.encode()).hexdigest()[:16], "name": room_name}

    def issue_participant_token(
        self, *, room_name: str, identity: str, display_name: str, credentials: dict, config: dict
    ) -> str:
        seed = f"{room_name}:{identity}"
        return "sim-token-" + hashlib.sha256(seed.encode()).hexdigest()[:32]

    def start_recording(self, *, room_name: str, credentials: dict, config: dict) -> str:
        seed = f"{room_name}:recording"
        return "sim-egress-" + hashlib.sha256(seed.encode()).hexdigest()[:16]

    def stop_recording(self, *, egress_id: str, credentials: dict, config: dict) -> dict:
        return {"egress_id": egress_id, "status": "EGRESS_COMPLETE"}

    def connection_info(self, *, credentials: dict, config: dict) -> dict:
        return {"mode": "simulated", "url": None}
