"""Environment validation and outbound HTTP for ad-provider connection flows.

Only administrator-invoked test endpoints call provider health checks. These
functions never return provider credentials or put them in a redirect URL.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings

META_PROVIDER = "meta_lead_ads"
GOOGLE_PROVIDER = "google_ads"
META_PURPOSE = "meta_lead_ads_connect"
GOOGLE_PURPOSE = "google_ads_connect"
GRAPH_BASE_URL = "https://graph.facebook.com/v21.0"
META_OAUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_API_VERSION = "v20"
HTTP_TIMEOUT_SECONDS = 20.0

META_ENV_FIELDS = {
    "META_OAUTH_CLIENT_ID": "meta_oauth_client_id",
    "META_OAUTH_CLIENT_SECRET": "meta_oauth_client_secret",
    "OAUTH_REDIRECT_BASE_URL": "oauth_redirect_base_url",
}
GOOGLE_ENV_FIELDS = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "google_ads_developer_token",
    "GOOGLE_ADS_CLIENT_ID": "google_ads_client_id",
    "GOOGLE_ADS_CLIENT_SECRET": "google_ads_client_secret",
    "OAUTH_REDIRECT_BASE_URL": "oauth_redirect_base_url",
}


def _secret(settings: Settings, field: str) -> str:
    value = getattr(settings, field, None)
    return (value.get_secret_value() if hasattr(value, "get_secret_value") else value or "").strip()


def missing_oauth_settings(settings: Settings, provider: str) -> list[str]:
    fields = META_ENV_FIELDS if provider == META_PROVIDER else GOOGLE_ENV_FIELDS
    return [name for name, field in fields.items() if not _secret(settings, field)]


def provider_configuration(settings: Settings, provider: str) -> dict[str, Any]:
    missing = missing_oauth_settings(settings, provider)
    google = provider == GOOGLE_PROVIDER
    return {
        "provider": provider,
        "mode": "oauth" if not missing else "manual",
        "configured": not missing,
        "missing": missing,
        "instructions_url": (
            "https://developers.google.com/google-ads/api/docs/get-started/dev-token"
            if google
            else "https://developers.facebook.com/apps/"
        ),
    }


def oauth_redirect_uri(settings: Settings, provider: str) -> str:
    slug = "meta" if provider == META_PROVIDER else "google"
    return f"{_secret(settings, 'oauth_redirect_base_url').rstrip('/')}/api/v1/integrations/connect/{slug}/callback"


def meta_authorization_url(settings: Settings, state: str) -> str:
    return META_OAUTH_URL + "?" + urlencode({
        "client_id": _secret(settings, "meta_oauth_client_id"),
        "redirect_uri": oauth_redirect_uri(settings, META_PROVIDER),
        "state": state,
        "scope": "pages_manage_leads,ads_read",
        "response_type": "code",
    })


def google_authorization_url(settings: Settings, state: str) -> str:
    return GOOGLE_OAUTH_URL + "?" + urlencode({
        "client_id": _secret(settings, "google_ads_client_id"),
        "redirect_uri": oauth_redirect_uri(settings, GOOGLE_PROVIDER),
        "state": state,
        "scope": "https://www.googleapis.com/auth/adwords",
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    })


def provider_error_message(response: httpx.Response, provider: str) -> str:
    """Expose useful provider diagnostics without including response secrets."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("status") or "")
        elif isinstance(error, str):
            detail = error
        detail = detail or str(body.get("error_description") or "")
    label = "Meta" if provider == META_PROVIDER else "Google"
    safe_detail = re.sub(r"(?i)(access_token=)[^\s&'\"]+", r"\1[redacted]", detail)
    return f"{label} could not complete the request ({response.status_code}). {safe_detail or 'Please try again.'}"[:1000]


def _request(method: str, url: str, *, provider: str, **kwargs) -> dict[str, Any]:
    try:
        response = httpx.request(method, url, timeout=HTTP_TIMEOUT_SECONDS, **kwargs)
    except httpx.TimeoutException as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The provider timed out. Please try again.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The provider could not be reached. Check the server network and try again.") from exc
    if response.is_error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, provider_error_message(response, provider))
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The provider returned an unreadable response.") from exc
    if not isinstance(body, dict):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The provider returned an unexpected response.")
    return body


def exchange_meta_code(code: str, settings: Settings) -> dict[str, Any]:
    token = _request(
        "POST",
        f"{GRAPH_BASE_URL}/oauth/access_token",
        provider=META_PROVIDER,
        data={
            "client_id": _secret(settings, "meta_oauth_client_id"),
            "client_secret": _secret(settings, "meta_oauth_client_secret"),
            "redirect_uri": oauth_redirect_uri(settings, META_PROVIDER),
            "code": code,
        },
    )
    if not isinstance(token.get("access_token"), str) or not token["access_token"]:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Meta did not return an access token. Start again.")
    # Meta's documented long-lived exchange upgrades the short-lived code token.
    long_lived = _request(
        "GET",
        f"{GRAPH_BASE_URL}/oauth/access_token",
        provider=META_PROVIDER,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": _secret(settings, "meta_oauth_client_id"),
            "client_secret": _secret(settings, "meta_oauth_client_secret"),
            "fb_exchange_token": token["access_token"],
        },
    )
    access_token = long_lived.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Meta did not return a long-lived access token. Start again.")
    pages_response = _request(
        "GET",
        f"{GRAPH_BASE_URL}/me/accounts",
        provider=META_PROVIDER,
        params={"access_token": access_token, "fields": "id,name", "limit": 100},
    )
    pages = [
        {"id": str(page["id"]), "name": str(page.get("name") or page["id"])}
        for page in pages_response.get("data", [])
        if isinstance(page, dict) and page.get("id")
    ]
    if not pages:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No manageable Facebook Pages were returned. Grant Page access or use an account that administers a Page.",
        )
    return {
        "access_token": access_token,
        "app_secret": _secret(settings, "meta_oauth_client_secret"),
        "token_expires_in": long_lived.get("expires_in"),
        "pages": pages,
    }


def exchange_google_code(code: str, settings: Settings) -> dict[str, Any]:
    token = _request(
        "POST",
        GOOGLE_TOKEN_URL,
        provider=GOOGLE_PROVIDER,
        data={
            "client_id": _secret(settings, "google_ads_client_id"),
            "client_secret": _secret(settings, "google_ads_client_secret"),
            "redirect_uri": oauth_redirect_uri(settings, GOOGLE_PROVIDER),
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    if not isinstance(token.get("refresh_token"), str) or not token["refresh_token"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Google did not issue a refresh token. Revoke PropFlow in your Google account permissions and reconnect to grant offline access again.",
        )
    return {
        "developer_token": _secret(settings, "google_ads_developer_token"),
        "refresh_token": token["refresh_token"],
        "client_id": _secret(settings, "google_ads_client_id"),
        "client_secret": _secret(settings, "google_ads_client_secret"),
        "token_expires_in": token.get("expires_in"),
    }


def test_meta_token(page_id: str, credentials: dict[str, Any]) -> None:
    body = _request(
        "GET",
        f"{GRAPH_BASE_URL}/{page_id}",
        provider=META_PROVIDER,
        params={"access_token": credentials.get("access_token", ""), "fields": "id,name"},
    )
    if str(body.get("id")) != page_id:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Meta returned an unexpected Page. Reconnect this Page.")


def test_google_connection(credentials: dict[str, Any]) -> None:
    token = _request(
        "POST",
        GOOGLE_TOKEN_URL,
        provider=GOOGLE_PROVIDER,
        data={
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "refresh_token": credentials.get("refresh_token", ""),
            "grant_type": "refresh_token",
        },
    )
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google did not return an access token. Reconnect this account.")
    _request(
        "GET",
        f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}/customers:listAccessibleCustomers",
        provider=GOOGLE_PROVIDER,
        headers={
            "Authorization": f"Bearer {access_token}",
            "developer-token": str(credentials.get("developer_token", "")),
        },
    )
