"""Secure integration configuration, cross-tenant page resolution, and health."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.integrations.exceptions import (
    IntegrationConfigurationError,
    IntegrationConnectionConflictError,
    IntegrationConnectionNotFoundError,
)
from app.modules.integrations.models import IntegrationConnection, utcnow
from app.modules.integrations.schemas import MetaPageConnectionUpsert
from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials, hash_verify_token
from app.modules.projects.exceptions import ProjectNotFoundError
from app.modules.projects.repository import get_project_by_id
from app.modules.users.models import User

META_LEAD_ADS = "meta_lead_ads"


def upsert_meta_page(
    session: Session,
    *,
    actor: User,
    page_id: str,
    payload: MetaPageConnectionUpsert,
) -> IntegrationConnection:
    """Create or replace a page connection owned by the administrator's tenant."""

    if get_project_by_id(session, payload.project_id, tenant_id=actor.tenant_id) is None:
        raise ProjectNotFoundError()
    connection = get_connection_for_tenant(session, tenant_id=actor.tenant_id, page_id=page_id)
    if connection is None:
        connection = IntegrationConnection(
            tenant_id=actor.tenant_id,
            provider=META_LEAD_ADS,
            external_account_id=page_id,
            project_id=payload.project_id,
            credentials_ciphertext="",
        )
        session.add(connection)
    try:
        connection.credentials_ciphertext = encrypt_credentials(
            {"access_token": payload.access_token, "app_secret": payload.app_secret},
            tenant_id=actor.tenant_id,
        )
    except ChannelConfigurationError as exc:
        raise IntegrationConfigurationError(str(exc)) from exc
    connection.project_id = payload.project_id
    connection.is_active = payload.is_active
    connection.updated_at = utcnow()
    if payload.webhook_verify_token is not None:
        connection.webhook_verify_token_hash = hash_verify_token(payload.webhook_verify_token)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IntegrationConnectionConflictError() from exc
    session.refresh(connection)
    return connection


def list_connections(session: Session, *, tenant_id: UUID) -> list[IntegrationConnection]:
    """Return a tenant's connection health without decrypting any secrets."""

    return list(
        session.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.tenant_id == tenant_id)
            .order_by(IntegrationConnection.created_at, IntegrationConnection.id)
        ).all()
    )


def get_connection_for_tenant(
    session: Session, *, tenant_id: UUID, page_id: str
) -> IntegrationConnection | None:
    """Resolve one page only inside an explicitly authorized tenant."""

    return session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.tenant_id == tenant_id,
            IntegrationConnection.provider == META_LEAD_ADS,
            IntegrationConnection.external_account_id == page_id,
        )
    )


def resolve_meta_page(session: Session, *, page_id: str) -> IntegrationConnection | None:
    """Resolve a globally unique Meta page for its public webhook."""

    return session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == META_LEAD_ADS,
            IntegrationConnection.external_account_id == page_id,
        )
    )


def delete_meta_page(session: Session, *, actor: User, page_id: str) -> None:
    """Revoke a tenant-owned page connection and its stored secrets."""

    connection = get_connection_for_tenant(session, tenant_id=actor.tenant_id, page_id=page_id)
    if connection is None:
        raise IntegrationConnectionNotFoundError()
    session.delete(connection)
    session.commit()


def get_credentials(connection: IntegrationConnection) -> dict:
    """Decrypt a connection's secrets using its owning tenant as key context."""

    try:
        return decrypt_credentials(
            connection.credentials_ciphertext, tenant_id=connection.tenant_id
        )
    except ChannelConfigurationError as exc:
        raise IntegrationConfigurationError(str(exc)) from exc


def record_success(session: Session, connection: IntegrationConnection) -> None:
    """Mark a successfully authenticated provider delivery as healthy."""

    connection.last_success_at = utcnow()
    connection.last_error = None
    connection.last_error_at = None
    session.commit()


def record_error(session: Session, connection: IntegrationConnection, error: str) -> None:
    """Retain a bounded, operator-readable processing error for a connection."""

    connection.last_error = error[:2000]
    connection.last_error_at = utcnow()
    session.commit()
