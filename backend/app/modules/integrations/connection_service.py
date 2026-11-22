"""Durable pending selections and finalized ad-provider connections."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.integrations.exceptions import (
    IntegrationConfigurationError,
    IntegrationConnectionConflictError,
    IntegrationConnectionNotFoundError,
)
from app.modules.integrations.models import IntegrationConnection, utcnow
from app.modules.integrations.provider_clients import GOOGLE_PROVIDER, META_PROVIDER
from app.modules.integrations.schemas import (
    GoogleManualConnectionRequest,
    MetaFinalizeResponse,
)
from app.modules.integrations.service import get_credentials
from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.security import encrypt_credentials, hash_verify_token
from app.modules.projects.exceptions import ProjectNotFoundError
from app.modules.projects.repository import get_project_by_id
from app.modules.users.models import User

PENDING_SELECTION = "PENDING_SELECTION"
ACTIVE_CONNECTION = "ACTIVE"
PENDING_LIFETIME = timedelta(minutes=30)


def get_owned_connection(
    session: Session, *, connection_id: UUID, tenant_id: UUID
) -> IntegrationConnection:
    """Resolve a connection inside its tenant; never expose another tenant's data."""
    connection = session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.tenant_id == tenant_id,
        )
    )
    if connection is None:
        raise IntegrationConnectionNotFoundError()
    return connection


def _encrypt(credentials: dict, tenant_id: UUID) -> str:
    try:
        return encrypt_credentials(credentials, tenant_id=tenant_id)
    except ChannelConfigurationError as exc:
        raise IntegrationConfigurationError(str(exc)) from exc


def create_pending_connection(
    session: Session, *, actor: User, provider: str, credentials: dict
) -> IntegrationConnection:
    """Keep provider tokens encrypted while the user chooses an account and project."""
    connection = IntegrationConnection(
        tenant_id=actor.tenant_id,
        provider=provider,
        external_account_id=f"pending-{uuid4().hex}",
        project_id=None,
        credentials_ciphertext=_encrypt(credentials, actor.tenant_id),
        connection_status=PENDING_SELECTION,
        pending_expires_at=utcnow() + PENDING_LIFETIME,
        is_active=False,
    )
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def _pending(
    session: Session, *, connection_id: UUID, actor: User, provider: str
) -> IntegrationConnection:
    connection = get_owned_connection(
        session, connection_id=connection_id, tenant_id=actor.tenant_id
    )
    expires_at = connection.pending_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        connection.provider != provider
        or connection.connection_status != PENDING_SELECTION
        or expires_at is None
        or expires_at <= datetime.now(UTC)
    ):
        raise IntegrationConfigurationError(
            "This connection session is invalid or has expired. Start the connection again."
        )
    return connection


def list_meta_pages(
    session: Session, *, connection_id: UUID, actor: User
) -> list[dict[str, str]]:
    connection = _pending(
        session, connection_id=connection_id, actor=actor, provider=META_PROVIDER
    )
    credentials = get_credentials(connection)
    pages = credentials.get("pages")
    if not isinstance(pages, list):
        raise IntegrationConfigurationError("The saved Page list is invalid. Start again.")
    return [
        {"id": str(page["id"]), "name": str(page.get("name") or page["id"])}
        for page in pages
        if isinstance(page, dict) and page.get("id")
    ]


def _project(session: Session, *, project_id: UUID, tenant_id: UUID) -> None:
    if get_project_by_id(session, project_id, tenant_id=tenant_id) is None:
        raise ProjectNotFoundError()


def _target_connection(
    session: Session, *, external_account_id: str
) -> IntegrationConnection | None:
    return session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.external_account_id == external_account_id
        )
    )


def _activate_connection(
    connection: IntegrationConnection,
    *,
    project_id: UUID,
    external_account_id: str,
    ciphertext: str,
) -> None:
    connection.external_account_id = external_account_id
    connection.project_id = project_id
    connection.credentials_ciphertext = ciphertext
    connection.connection_status = ACTIVE_CONNECTION
    connection.pending_expires_at = None
    connection.is_active = True
    connection.last_success_at = None
    connection.last_error = None
    connection.last_error_at = None
    connection.updated_at = utcnow()


def finalize_meta(
    session: Session,
    *,
    actor: User,
    connection_id: UUID,
    page_id: str,
    project_id: UUID,
    verify_token: str | None,
    settings: Settings,
) -> MetaFinalizeResponse:
    pending = _pending(
        session, connection_id=connection_id, actor=actor, provider=META_PROVIDER
    )
    pages = list_meta_pages(session, connection_id=connection_id, actor=actor)
    if page_id not in {page["id"] for page in pages}:
        raise IntegrationConfigurationError("Choose a Page returned by the Meta authorization.")
    _project(session, project_id=project_id, tenant_id=actor.tenant_id)
    target = _target_connection(session, external_account_id=page_id)
    if target is not None and target.tenant_id != actor.tenant_id:
        raise IntegrationConnectionConflictError()
    plaintext = get_credentials(pending)
    credentials = {
        "access_token": plaintext["access_token"],
        "app_secret": plaintext["app_secret"],
        **({"token_expires_in": plaintext["token_expires_in"]} if plaintext.get("token_expires_in") is not None else {}),
    }
    plain_verify_token = verify_token or secrets.token_urlsafe(32)
    if target is not None:
        _activate_connection(
            target,
            project_id=project_id,
            external_account_id=page_id,
            ciphertext=_encrypt(credentials, actor.tenant_id),
        )
        target.webhook_verify_token_hash = hash_verify_token(plain_verify_token)
        session.delete(pending)
        connection = target
    else:
        _activate_connection(
            pending,
            project_id=project_id,
            external_account_id=page_id,
            ciphertext=_encrypt(credentials, actor.tenant_id),
        )
        pending.webhook_verify_token_hash = hash_verify_token(plain_verify_token)
        connection = pending
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IntegrationConnectionConflictError() from exc
    session.refresh(connection)
    base_url = (settings.oauth_redirect_base_url or "").rstrip("/")
    return MetaFinalizeResponse(
        connection=connection,
        webhook_url=f"{base_url}/api/v1/webhooks/meta",
        webhook_verify_token=plain_verify_token,
        subscription_checklist=[
            "In the Meta app dashboard, add the Webhooks product and subscribe the selected Page.",
            "Paste the callback URL and verify token shown here, then verify and save.",
            "Subscribe the Page to the leadgen field and send a test lead from Meta's Lead Ads testing tool.",
            "Keep this verify token somewhere safe now; PropFlow stores only its hash and cannot show it again.",
        ],
    )


def finalize_google(
    session: Session,
    *,
    actor: User,
    connection_id: UUID,
    customer_id: str,
    project_id: UUID,
) -> IntegrationConnection:
    pending = _pending(
        session, connection_id=connection_id, actor=actor, provider=GOOGLE_PROVIDER
    )
    _project(session, project_id=project_id, tenant_id=actor.tenant_id)
    target = _target_connection(session, external_account_id=customer_id)
    if target is not None and target.tenant_id != actor.tenant_id:
        raise IntegrationConnectionConflictError()
    plaintext = get_credentials(pending)
    credentials = {
        key: plaintext[key]
        for key in ("developer_token", "refresh_token", "client_id", "client_secret")
    }
    credentials["token_expires_in"] = plaintext.get("token_expires_in")
    if target is None:
        connection = pending
    else:
        connection = target
        session.delete(pending)
    _activate_connection(
        connection,
        project_id=project_id,
        external_account_id=customer_id,
        ciphertext=_encrypt(credentials, actor.tenant_id),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IntegrationConnectionConflictError() from exc
    session.refresh(connection)
    return connection


def connect_google_manually(
    session: Session, *, actor: User, payload: GoogleManualConnectionRequest
) -> IntegrationConnection:
    """Support offline-conversion credentials when PropFlow has no shared OAuth app."""
    _project(session, project_id=payload.project_id, tenant_id=actor.tenant_id)
    connection = _target_connection(session, external_account_id=payload.customer_id)
    if connection is not None and connection.tenant_id != actor.tenant_id:
        raise IntegrationConnectionConflictError()
    if connection is None:
        connection = IntegrationConnection(
            tenant_id=actor.tenant_id,
            provider=GOOGLE_PROVIDER,
            external_account_id=payload.customer_id,
            project_id=payload.project_id,
            credentials_ciphertext="",
        )
        session.add(connection)
    credentials = {
        "developer_token": payload.developer_token,
        "refresh_token": payload.refresh_token,
        "client_id": payload.client_id,
        "client_secret": payload.client_secret,
    }
    _activate_connection(
        connection,
        project_id=payload.project_id,
        external_account_id=payload.customer_id,
        ciphertext=_encrypt(credentials, actor.tenant_id),
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IntegrationConnectionConflictError() from exc
    session.refresh(connection)
    return connection


def connection_status(connection: IntegrationConnection) -> dict:
    configured = connection.connection_status == ACTIVE_CONNECTION and connection.is_active
    if connection.connection_status == PENDING_SELECTION:
        health = "pending"
        missing = ["Select an ad account and a project to finish connecting."]
    else:
        missing = []
        if not connection.is_active:
            missing.append("The connection is inactive. Reconnect it to restore access.")
        if connection.project_id is None:
            missing.append("Choose a project for lead or conversion attribution.")
        if connection.provider == META_PROVIDER and not connection.webhook_verify_token_hash:
            missing.append("A webhook verify token has not been configured.")
        if connection.last_success_at is None:
            missing.append("No successful provider test or lead delivery has been recorded yet.")
        health = (
            "error" if connection.last_error
            else "healthy" if connection.last_success_at
            else "unverified"
        )
    return {
        "connection_id": connection.id,
        "provider": connection.provider,
        "configured": configured,
        "health": health,
        "missing": missing,
        "last_success_at": connection.last_success_at,
        "last_error": connection.last_error,
    }


def mark_test_success(session: Session, connection: IntegrationConnection) -> None:
    connection.last_success_at = utcnow()
    connection.last_error = None
    connection.last_error_at = None
    session.commit()


def mark_test_error(session: Session, connection: IntegrationConnection, error: str) -> None:
    connection.last_error = error[:2000]
    connection.last_error_at = utcnow()
    session.commit()


def revoke_connection(session: Session, *, actor: User, connection_id: UUID) -> None:
    connection = get_owned_connection(
        session, connection_id=connection_id, tenant_id=actor.tenant_id
    )
    session.delete(connection)
    session.commit()
