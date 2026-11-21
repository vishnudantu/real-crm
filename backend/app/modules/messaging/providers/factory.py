"""Resolve outbound providers without leaking credentials into domain services."""

from __future__ import annotations

from app.modules.messaging.models import MessageChannel
from app.modules.messaging.providers.gupshup_whatsapp import GupshupWhatsAppProvider
from app.modules.messaging.providers.log_provider import LogProvider
from app.modules.messaging.providers.msg91_sms import MSG91SMSProvider
from app.modules.messaging.providers.smtp_email import SMTPEmailProvider


def provider_name(channel: str, settings) -> str:
    configured = settings.messaging_provider_default.strip().lower()
    if configured != "auto":
        return configured
    return {
        MessageChannel.WHATSAPP.value: "gupshup",
        MessageChannel.SMS.value: "msg91",
        MessageChannel.EMAIL.value: "smtp",
    }[channel]


def build_provider(name: str, settings):
    if name == "log":
        return LogProvider()
    if name == "smtp":
        return SMTPEmailProvider(settings)
    if name == "msg91":
        return MSG91SMSProvider(settings)
    if name == "gupshup":
        return GupshupWhatsAppProvider(settings)
    raise ValueError(f"Unsupported messaging provider: {name}")
