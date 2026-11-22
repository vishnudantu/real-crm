"""Guided Meta Lead Ads and Google Ads connection endpoints for administrators.

Trust model: ``/start`` requires an authenticated admin (``AdminUser``) and
mints a 10-minute signed state JWT bound to that admin, tenant and purpose.
The provider then redirects the *browser* to ``/callback`` — a navigation
request that cannot carry a bearer header — so the callback authenticates
through that state JWT, verifies the referenced account is still an active
administrator of the same tenant, exchanges the code server-side over TLS,
and hands the SPA only an opaque selection ticket (the pending connection
id). Access tokens never appear in a URL; they are stored encrypted.
"""

from __future__ import annotations

import re
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
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
from app.modules.integrations.oauth_state import (
    OAuthStateClaims,
    OAuthStateError,
    create_oauth_state,
    decode_oauth_state,
)
from app.modules.integrations.provider_clients import (
    GOOGLE_PROVIDER,
    GOOGLE_PURPOSE,
    META_PROVIDER,
    META_PURPOSE,
    exchange_google_code,
    exchange_meta_code,
    google_authorization_url,
    meta_authorization_url,
    missing_oauth_settings,
    provider_configuration,
    test_google_connection,
    test_meta_token,
)
from app.modules.integrations.schemas import (
    ConnectUrlResponse,
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
from app.modules.users import repository as users_repository
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/integrations/connect", tags=["integrations"])

_CREDENTIAL_ECHO = re.compile(
    r"(?i)(access_token|client_secret|refresh_token|code)=([^&\s'\"]{4})[^&\s'\"]*"
)

_UNCONFIGURED_CODES = {
    META_PROVIDER: "META_OAUTH_NOT_CONFIGURED",
    GOOGLE_PROVIDER: "GOOGLE_OAUTH_NOT_CONFIGURED",
}


def _safe_provider_message(text: str) -> str:
    """Keep provider diagnostics readable without echoing OAuth secrets."""
    return _CREDENTIAL_ECHO.sub(lambda m: f"{m.group(1)}={m.group(2)}***", text)[:500]


def _not_configured_response(provider: str, settings: Settings) -> JSONResponse:
    """Exact honest fallback: 409 with the missing env names, never a fake flow."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": _UNCONFIGURED_CODES[provider],
            "missing": missing_oauth_settings(settings, provider),
        },
    )


def _frontend_error_redirect(settings: Settings, message: str) -> RedirectResponse:
    destination = (
        f"{settings.frontend_base_url.rstrip('/')}/admin/integrations?"
        + urlencode({"error": _safe_provider_message(message)})
    )
    return RedirectResponse(destination, status_code=status.HTTP_302_FOUND)


def _callback_actor(db: Session, claims: OAuthStateClaims) -> User:
    """Resolve the administrator the verified state was issued to."""
    actor = users_repository.get_user_by_id(db, claims.admin_user_id)
    if (
        actor is None
        or actor.tenant_id != claims.tenant_id
        or not actor.is_active
        or actor.role.name != RoleName.ADMIN.value
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "The administrator who started this connection can no longer complete it. Start again.",
        )
    return actor


def _authorization_redirect(
    provider: str, actor: User, settings: Settings
) -> RedirectResponse | JSONResponse:
    missing = missing_oauth_settings(settings, provider)
    if missing:
        return _not_configured_response(provider, settings)
    purpose = META_PURPOSE if provider == META_PROVIDER else GOOGLE_PURPOSE
    state = create_oauth_state(
        tenant_id=actor.tenant_id,
        admin_user_id=actor.id,
        purpose=purpose,
        settings=settings,
    )
    url = (
        meta_authorization_url(settings, state)
        if provider == META_PROVIDER
        else google_authorization_url(settings, state)
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/providers", response_model=list[ProviderConfigurationResponse])
def get_provider_configuration(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Describe real OAuth availability, including the exact missing env names."""
    return [provider_configuration(settings, provider) for provider in (META_PROVIDER, GOOGLE_PROVIDER)]


@router.get("/meta/connect-url", response_model=ConnectUrlResponse)
def meta_connect_url(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """JSON form of /meta/start so the SPA can trigger the browser redirect."""
    missing = missing_oauth_settings(settings, META_PROVIDER)
    if missing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Meta OAuth is not configured. Missing: {', '.join(missing)}",
        )
    state = create_oauth_state(
        tenant_id=actor.tenant_id,
        admin_user_id=actor.id,
        purpose=META_PURPOSE,
        settings=settings,
    )
    return {"url": meta_authorization_url(settings, state)}


@router.get("/meta/start")
def start_meta(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    return _authorization_redirect(META_PROVIDER, actor, settings)


@router.get("/meta/callback")
def meta_callback(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1)] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
):
    """Exchange the code server-side and redirect with only an opaque ticket."""
    if error or not code or not state:
        detail = error_description or error or "Meta did not return an authorization code."
        return _frontend_error_redirect(settings, f"Meta authorization was not completed: {detail}")
    try:
        claims = decode_oauth_state(state, purpose=META_PURPOSE, settings=settings)
    except OAuthStateError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    actor = _callback_actor(db, claims)
    try:
        credentials = exchange_meta_code(code, settings)
    except HTTPException as exc:
        return _frontend_error_redirect(settings, str(exc.detail))
    connection = create_pending_connection(
        db, actor=actor, provider=META_PROVIDER, credentials=credentials
    )
    destination = (
        f"{settings.frontend_base_url.rstrip('/')}/admin/integrations/meta/select?"
        + urlencode({"ticket": str(connection.id)})
    )
    return RedirectResponse(destination, status_code=status.HTTP_302_FOUND)


@router.get("/meta/pages", response_model=MetaPagesResponse)
def get_meta_pages(
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    connection_id: UUID,
):
    """The Page list from the encrypted pending ticket, tenant-checked."""
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
    """Validate stored credentials with one Graph call, only on admin request."""
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


@router.get("/google/connect-url", response_model=ConnectUrlResponse)
def google_connect_url(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    missing = missing_oauth_settings(settings, GOOGLE_PROVIDER)
    if missing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Google OAuth is not configured. Missing: {', '.join(missing)}",
        )
    state = create_oauth_state(
        tenant_id=actor.tenant_id,
        admin_user_id=actor.id,
        purpose=GOOGLE_PURPOSE,
        settings=settings,
    )
    return {"url": google_authorization_url(settings, state)}


@router.get("/google/start")
def start_google(
    actor: AdminUser,
    settings: Annotated[Settings, Depends(get_settings)],
):
    return _authorization_redirect(GOOGLE_PROVIDER, actor, settings)


@router.get("/google/callback")
def google_callback(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query(min_length=1)] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
):
    if error or not code or not state:
        detail = error_description or error or "Google did not return an authorization code."
        return _frontend_error_redirect(settings, f"Google authorization was not completed: {detail}")
    try:
        claims = decode_oauth_state(state, purpose=GOOGLE_PURPOSE, settings=settings)
    except OAuthStateError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    actor = _callback_actor(db, claims)
    try:
        credentials = exchange_google_code(code, settings)
    except HTTPException as exc:
        return _frontend_error_redirect(settings, str(exc.detail))
    connection = create_pending_connection(
        db, actor=actor, provider=GOOGLE_PROVIDER, credentials=credentials
    )
    destination = (
        f"{settings.frontend_base_url.rstrip('/')}/admin/integrations/google/select?"
        + urlencode({"ticket": str(connection.id)})
    )
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
    """Offline-conversion credentials when PropFlow has no shared OAuth app yet."""
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
