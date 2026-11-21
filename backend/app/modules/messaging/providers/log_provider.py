"""Development provider that records outbound messages without external calls."""

from __future__ import annotations

import logging
from uuid import uuid4

logger = logging.getLogger("propflow.messaging.log_provider")


class LogProvider:
    def send(self, *, to: str, body: str, context: dict) -> str:
        message_id = f"log-{uuid4()}"
        logger.info(
            "Outbound message id=%s channel=%s to=%s body=%s",
            message_id,
            context.get("channel", "unknown"),
            to,
            body,
        )
        return message_id
