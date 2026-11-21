"""Connector configuration for lead-ingestion webhooks and portal mailboxes."""

from __future__ import annotations

from app.core.config import Settings


def meta_webhook_configured(settings: Settings) -> bool:
    return bool(settings.meta_app_secret and settings.meta_page_access_token)


def portal_imap_configured(settings: Settings) -> bool:
    return bool(settings.leads_imap_host and settings.leads_imap_user and settings.leads_imap_pass)
