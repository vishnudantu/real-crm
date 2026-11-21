"""Channel and calling provider contracts."""

from __future__ import annotations

from typing import Protocol


class MessageProvider(Protocol):
    """Outbound channel adapter; credentials are tenant-specific plaintext."""

    def send_text(self, *, recipient: str, text: str, credentials: dict, config: dict) -> str: ...


class CallProvider(Protocol):
    """Calling adapter for browser rooms, participant tokens, and recordings."""

    def create_room(self, *, room_name: str, credentials: dict, config: dict) -> dict: ...

    def issue_participant_token(
        self, *, room_name: str, identity: str, display_name: str, credentials: dict, config: dict
    ) -> str: ...

    def start_recording(self, *, room_name: str, credentials: dict, config: dict) -> str: ...

    def stop_recording(self, *, egress_id: str, credentials: dict, config: dict) -> dict: ...

    def connection_info(self, *, credentials: dict, config: dict) -> dict: ...
