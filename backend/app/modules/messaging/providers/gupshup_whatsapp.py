"""Gupshup WhatsApp provider using its authenticated message endpoint."""

from __future__ import annotations

import httpx

from app.modules.messaging.providers.base import ProviderConfigurationError


class GupshupWhatsAppProvider:
    def __init__(self, settings) -> None:
        self.settings = settings

    def send(self, *, to: str, body: str, context: dict) -> str:
        settings = self.settings
        if not settings.gupshup_api_key or not settings.gupshup_app_name or not settings.gupshup_source_number:
            raise ProviderConfigurationError(
                "GUPSHUP_API_KEY, GUPSHUP_APP_NAME and GUPSHUP_SOURCE_NUMBER are required."
            )
        response = httpx.post(
            "https://api.gupshup.io/wa/api/v1/msg",
            headers={"apikey": settings.gupshup_api_key.get_secret_value()},
            data={
                "channel": "whatsapp",
                "source": settings.gupshup_source_number,
                "destination": to,
                "src.name": settings.gupshup_app_name,
                "message": body,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("messageId") or payload.get("message_id") or payload)
