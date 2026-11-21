"""MSG91 SMS provider (configuration supplied via environment settings)."""

from __future__ import annotations

import httpx

from app.modules.messaging.providers.base import ProviderConfigurationError


class MSG91SMSProvider:
    def __init__(self, settings) -> None:
        self.settings = settings

    def send(self, *, to: str, body: str, context: dict) -> str:
        auth_key = self.settings.msg91_auth_key
        sender_id = self.settings.msg91_sender_id
        if not auth_key or not sender_id:
            raise ProviderConfigurationError("MSG91_AUTH_KEY and MSG91_SENDER_ID are required.")
        response = httpx.post(
            "https://control.msg91.com/api/v5/flow/",
            headers={"authkey": auth_key.get_secret_value(), "Content-Type": "application/json"},
            json={
                "sender": sender_id,
                "template_id": context.get("provider_template_name"),
                "short_url": "0",
                "recipients": [{"mobiles": to, "message": body}],
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("request_id") or payload.get("message") or payload)
