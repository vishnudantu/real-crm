"""SMTP email provider using only the Python standard library."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from uuid import uuid4

from app.modules.messaging.providers.base import ProviderConfigurationError


class SMTPEmailProvider:
    def __init__(self, settings) -> None:
        self.settings = settings

    def send(self, *, to: str, body: str, context: dict) -> str:
        settings = self.settings
        if not settings.smtp_host:
            raise ProviderConfigurationError("SMTP_HOST is required for email delivery.")
        message = EmailMessage()
        message["Subject"] = context.get("subject") or f"Update from {settings.app_name}"
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = to
        message["Message-ID"] = f"<propflow-{uuid4()}@{settings.smtp_from_email.split('@')[-1]}>"
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                password = settings.smtp_password
                server.login(
                    settings.smtp_user,
                    password.get_secret_value() if password else "",
                )
            server.send_message(message)
        return message["Message-ID"]
