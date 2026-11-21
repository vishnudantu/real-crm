"""LiveKit calling adapter: participant tokens and Egress recordings.

Rooms are created implicitly on first participant join. The browser client
joins ``ws_url`` using the issued participant JWT; recordings run through
LiveKit Egress to the tenant's configured storage destination.
"""

from __future__ import annotations

import logging

from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.providers.base import CallProvider
from app.modules.omnichannel.security import make_livekit_access_token

logger = logging.getLogger(__name__)


def _required(credentials: dict, *keys: str) -> None:
    if any(not credentials.get(key) for key in keys):
        raise ChannelConfigurationError(
            "LiveKit requires api_key and api_secret in the channel credentials."
        )


class LiveKitCallProvider:
    """Adapter over a tenant's own LiveKit server (self-hosted or Cloud)."""

    def create_room(self, *, room_name: str, credentials: dict, config: dict) -> dict:
        _required(credentials, "api_key", "api_secret")
        # LiveKit creates the room on first join; returning the name keeps the
        # service idempotent without a mandatory server round-trip.
        return {"name": room_name}

    def issue_participant_token(
        self, *, room_name: str, identity: str, display_name: str, credentials: dict, config: dict
    ) -> str:
        _required(credentials, "api_key", "api_secret")
        ttl = int(config.get("token_ttl_seconds") or 3600)
        return make_livekit_access_token(
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
            room=room_name,
            identity=identity,
            name=display_name,
            ttl_seconds=ttl,
        )

    async def start_recording(self, *, room_name: str, credentials: dict, config: dict) -> str:
        """Start a room-composite Egress recording; returns the egress id."""

        _required(credentials, "api_key", "api_secret")
        try:
            from livekit import api as livekit_api  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ChannelConfigurationError(
                "Install the 'livekit-api' package to start Egress recordings."
            ) from exc
        ws_url = config.get("ws_url")
        if not ws_url:
            raise ChannelConfigurationError("LiveKit requires a ws_url in the channel config.")
        http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
        output_path = str(config.get("recording_filepath") or f"recordings/{room_name}.ogg")
        lk = livekit_api.LiveKitAPI(
            url=http_url,
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
        )
        try:
            request = livekit_api.RoomCompositeEgressRequest(
                room_name=room_name,
                audio_only=bool(config.get("audio_only", True)),
                file_outputs=[livekit_api.EncodedFileOutput(filepath=output_path)],
            )
            info = await lk.egress.start_room_composite_egress(request)
            return str(info.egress_id)
        finally:
            await lk.aclose()

    async def stop_recording(self, *, egress_id: str, credentials: dict, config: dict) -> dict:
        _required(credentials, "api_key", "api_secret")
        try:
            from livekit import api as livekit_api  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ChannelConfigurationError(
                "Install the 'livekit-api' package to stop Egress recordings."
            ) from exc
        ws_url = config.get("ws_url")
        if not ws_url:
            raise ChannelConfigurationError("LiveKit requires a ws_url in the channel config.")
        http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
        lk = livekit_api.LiveKitAPI(
            url=http_url,
            api_key=credentials["api_key"],
            api_secret=credentials["api_secret"],
        )
        try:
            await lk.egress.stop_egress(livekit_api.StopEgressRequest(egress_id=egress_id))
        finally:
            await lk.aclose()
        return {"egress_id": egress_id, "status": "STOP_REQUESTED"}

    def connection_info(self, *, credentials: dict, config: dict) -> dict:
        ws_url = config.get("ws_url")
        if not ws_url:
            raise ChannelConfigurationError("LiveKit requires a ws_url in the channel config.")
        return {"mode": "livekit", "url": ws_url}
