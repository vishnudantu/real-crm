"""Administrator-guided Meta Lead Ads and Google Ads connection endpoints."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.integrations.connection_service import (
    ACTIVE_CONNECTION,
    connect_google_manually,
    connection_status,
    create_pending_connection,
    finalize_google,
    finalize_meta,
    get_owned_connection,
    list_meta_pages,
    mark_test_error,
    mark_test_success,
    revoke_connection,
)
from app.modules.integrations.oauth_state import OAuthStateError, create_oauth_state, decode_oauth_state
from app.modules.integrations.provider_clients import (
    GOOGLE_PROVIDER,
    GOOGLE_PURPOSE,
    META_PROVIDER,
    META_PURPOSE,
    exchange_google_code,
    exchange_meta_code,
    google_authorization_url,
    meta_authorization_url,
    provider_configuration,
    require_oauth_configuration,
    test_google_connection,
    test_meta_token,
)
from app.modules.integrations.schemas import (
    ConnectionStatusResponse,
    ConnectionTestResponse,
    GoogleFinalizeRequest,
    GoogleManualConnectionRequest,
    IntegrationConnectionResponse,
    MetaFinalizeRequest,
    MetaFinalizeResponse,
    MetaPagesResponse,
    ProviderConfigurationResponse,
)
from app.modules.integrations.service import get_credentials

router = APIRouter(prefix="/integrations/connect", tags=["integrations"])


def _oauth_error(exc: OAuthStateError) -> None:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/providers", response_model=list[ProviderConfigurationResponse])
def get_provider_configuration(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Describe real OAuth availability, including exact missing environment names."""
    return [provider_configuration(settings, provider) for provider in (META_PROVIDER, GOOGLE_PROVIDER)]


@router.get("/meta/start", status_code=status.HTTP_302_FOUND)
def start_meta(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    require_oauth_configuration(settings, META_PROVIDER)
    state = create_oauth_state(
        tenant_id=actor.tenant_id,
        admin_user_id=actor.id,
        purpose=META_PURPOSE,
        settings=settings,
    )
    return RedirectResponse(meta_authorization_url(settings, state), status_code=status.HTTP_302_FOUND)


@router.get("/meta/callback", status_code=status.HTTP_302_FOUND)
def meta_callback(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1)] = None,
    state: Annotated[str, Query(min_length=1)] = "",
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
):
    """Exchange the code server-side and return only an opaque selection ticket."""
    if error or not code:
        detail = error_description or error or "Meta did not return an authorization code."
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Meta authorization was not completed: {detail} Start again.")
    try:
        decode_oauth_state(
            state,
            tenant_id=actor.tenant_id,
            admin_user_id=actor.id,
            purpose=META_PURPOSE,
            settings=settings,
        )
    except OAuthStateError as exc:
        _oauth_error(exc)
    credentials = exchange_meta_code(code, settings)
    connection = create_pending_connection(
        db, actor=actor, provider=META_PROVIDER, credentials=credentials
    )
    destination = f"{settings.frontend_base_url.rstrip('/')}/admin/integrations/meta/select?" + urlencode({"ticket": str(connection.id)})
    return RedirectResponse(destination, status_code=status.HTTP_302_FOUND)


@router.get("/meta/pages", response_model=MetaPagesResponse)
def get_meta_pages(
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    connection_id: UUID,
):
    return {
        "connection_id": connection_id,
        "pages": list_meta_pages(db, connection_id=connection_id, actor=actor),
    }


@router.post("/meta/finalize", response_model=MetaFinalizeResponse)
def finalize_meta_connection(
    payload: MetaFinalizeRequest,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return finalize_meta(
        db,
        actor=actor,
        connection_id=payload.connection_id,
        page_id=payload.page_id,
        project_id=payload.project_id,
        verify_token=payload.verify_token,
        settings=settings,
    )


@router.get("/meta/status/{connection_id}", response_model=ConnectionStatusResponse)
def meta_status(
    connection_id: UUID,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    connection = get_owned_connection(db, connection_id=connection_id, tenant_id=actor.tenant_id)
    if connection.provider != META_PROVIDER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration connection not found.")
    return connection_status(connection)


@router.post("/meta/test", response_model=ConnectionTestResponse)
def test_meta_connection(
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    connection_id: Annotated[UUID, Query()],
):
    """Validate stored credentials only on an explicit administrator action."""
    connection = get_owned_connection(db, connection_id=connection_id, tenant_id=actor.tenant_id)
    if connection.provider != META_PROVIDER or connection.connection_status != ACTIVE_CONNECTION:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Finish the Meta connection before testing it.")
    try:
        test_meta_token(connection.external_account_id, get_credentials(connection))
    except HTTPException as exc:
        mark_test_error(db, connection, str(exc.detail))
        raise
    mark_test_success(db, connection)
    return {"ok": True, "message": "Meta authenticated this Page successfully."}


@router.get("/google/start", status_code=status.HTTP_302_FOUND)
def start_google(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    require_oauth_configuration(settings, GOOGLE_PROVIDER)
    state = create_oauth_state(
        tenant_id=actor.tenant_id,
        admin_user_id=actor.id,
        purpose=GOOGLE_PURPOSE,
        settings=settings,
    )
    return RedirectResponse(google_authorization_url(settings, state), status_code=status.HTTP_302_FOUND)


@router.get("/google/callback", status_code=status.HTTP_302_FOUND)
def google_callback(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1)] = None,
    state: Annotated[str, Query(min_length=1)] = "",
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
):
    if error or not code:
        detail = error_description or error or "Google did not return an authorization code."
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Google authorization was not completed: {detail} Start again.")
    try:
        decode_oauth_state(
            state,
            tenant_id=actor.tenant_id,
            admin_user_id=actor.id,
            purpose=GOOGLE_PURPOSE,
            settings=settings,
        )
    except OAuthStateError as exc:
        _oauth_error(exc)
    credentials = exchange_google_code(code, settings)
    connection = create_pending_connection(
        db, actor=actor, provider=GOOGLE_PROVIDER, credentials=credentials
    )
    destination = f"{settings.frontend_base_url.rstrip('/')}/admin/integrations/google/select?" + urlencode({"ticket": str(connection.id)})
    return RedirectResponse(destination, status_code=status.HTTP_302_FOUND)


@router.post("/google/finalize", response_model=IntegrationConnectionResponse)
def finalize_google_connection(
    payload: GoogleFinalizeRequest,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return finalize_google(
        db,
        actor=actor,
        connection_id=payload.connection_id,
        customer_id=payload.customer_id,
        project_id=payload.project_id,
    )


@router.post("/google/manual", response_model=IntegrationConnectionResponse)
def manual_google_connection(
    payload: GoogleManualConnectionRequest,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return connect_google_manually(db, actor=actor, payload=payload)


@router.get("/google/status/{connection_id}", response_model=ConnectionStatusResponse)
def google_status(
    connection_id: UUID,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    connection = get_owned_connection(db, connection_id=connection_id, tenant_id=actor.tenant_id)
    if connection.provider != GOOGLE_PROVIDER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration connection not found.")
    return connection_status(connection)


@router.post("/google/test", response_model=ConnectionTestResponse)
def test_google_ads_connection(
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    connection_id: Annotated[UUID, Query()],
):
    connection = get_owned_connection(db, connection_id=connection_id, tenant_id=actor.tenant_id)
    if connection.provider != GOOGLE_PROVIDER or connection.connection_status != ACTIVE_CONNECTION:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Finish the Google Ads connection before testing it.")
    try:
        test_google_connection(get_credentials(connection))
    except HTTPException as exc:
        mark_test_error(db, connection, str(exc.detail))
        raise
    mark_test_success(db, connection)
    return {"ok": True, "message": "Google Ads accepted the developer token and OAuth credentials."}


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_provider_connection(
    connection_id: UUID,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    revoke_connection(db, actor=actor, connection_id=connection_id)
