"""Meta Graph API adapters for WhatsApp Cloud, Instagram DMs, and Messenger."""

from __future__ import annotations

import logging

import httpx

from app.modules.omnichannel.exceptions import ChannelMessageSendError
from app.modules.omnichannel.providers.base import MessageProvider

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_VERSION = "v21.0"
REQUEST_TIMEOUT_SECONDS = 15.0


class MetaGraphMessageProvider:
    """Send messages via the tenant's own Meta Graph API credentials."""

    def __init__(self, *, graph_version: str = DEFAULT_GRAPH_VERSION) -> None:
        self.graph_version = graph_version

    def _endpoint(self, path: str, config: dict) -> str:
        base = str(config.get("graph_base_url") or "https://graph.facebook.com").rstrip("/")
        version = str(config.get("graph_version") or self.graph_version).strip("/")
        return f"{base}/{version}/{path.lstrip('/')}"

    def _post(self, *, path: str, token: str, payload: dict, config: dict) -> dict:
        try:
            response = httpx.post(
                self._endpoint(path, config),
                json=payload,
                params={"access_token": token},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Meta Graph API send failed for path %s: %s", path, type(exc).__name__)
            raise ChannelMessageSendError("The messaging provider rejected the outbound message.") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise ChannelMessageSendError("The messaging provider returned an invalid response.") from exc

    def send_text(self, *, recipient: str, text: str, credentials: dict, config: dict) -> str:
        raise NotImplementedError


class WhatsAppCloudProvider(MetaGraphMessageProvider):
    """WhatsApp Cloud API (official Meta-hosted WhatsApp Business)."""

    def send_text(self, *, recipient: str, text: str, credentials: dict, config: dict) -> str:
        token = credentials.get("access_token")
        phone_number_id = config.get("phone_number_id")
        if not token or not phone_number_id:
            raise ChannelMessageSendError(
                "WhatsApp requires an access token and a phone_number_id."
            )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        data = self._post(path=f"{phone_number_id}/messages", token=token, payload=payload, config=config)
        messages = data.get("messages") or []
        return str(messages[0].get("id")) if messages and messages[0].get("id") else ""


class MessengerProvider(MetaGraphMessageProvider):
    """Facebook Messenger Send API using a Page access token."""

    def send_text(self, *, recipient: str, text: str, credentials: dict, config: dict) -> str:
        token = credentials.get("access_token")
        if not token:
            raise ChannelMessageSendError("Messenger requires a Page access token.")
        payload = {
            "recipient": {"id": recipient},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        }
        page_id = config.get("page_id") or "me"
        data = self._post(path=f"{page_id}/messages", token=token, payload=payload, config=config)
        return str(data.get("message_id") or "")


class InstagramProvider(MessengerProvider):
    """Instagram DM Send API; uses the same Graph messages endpoint shape."""


# NOTE: Meta's 24-hour customer-service window applies to WhatsApp, Messenger,
# and Instagram free-form replies; outside it, approved templates are required.
# Template send support belongs in the outbound template phase.
