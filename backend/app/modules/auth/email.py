"""Password-reset email delivery with a safe development fallback."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode, urljoin

from app.core.config import Settings

logger = logging.getLogger(__name__)


def deliver_password_reset(
    *,
    settings: Settings,
    recipient_email: str,
    token: str,
    frontend_base_url,
) -> None:
    """Send a reset link; log it only in development/testing when SMTP is unset."""

    base = settings.frontend_base_url or str(frontend_base_url)
    link = urljoin(base, "forgot-password") + "?" + urlencode({"token": token})
    subject = f"Reset your {settings.app_name} password"
    body = (
        "A password reset was requested for your account.\n\n"
        f"Use this single-use link within {settings.password_reset_token_expire_minutes} minutes:\n"
        f"{link}\n\n"
        "If you did not request a reset, ignore this message."
    )
    if not settings.smtp_host:
        if settings.environment == "production":
            raise RuntimeError("SMTP must be configured to deliver password resets.")
        logger.info("Development password reset for %s: %s", recipient_email, link)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = recipient_email
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(
                settings.smtp_user,
                settings.smtp_password.get_secret_value() if settings.smtp_password else "",
            )
        server.send_message(message)
