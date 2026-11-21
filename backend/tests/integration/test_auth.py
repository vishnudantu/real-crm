"""Authentication registration, login, and token tests."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.modules.auth.security import create_access_token
from app.modules.users import repository
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD as VALID_PASSWORD
from tests.support import WRONG_PASSWORD

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def _registration_payload(
    email: str = "buyer@example.com",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "A Buyer",
        "email": email,
        "password": VALID_PASSWORD,
    }
    payload.update(overrides)
    return payload


def _login_payload(
    email: str,
    password: str = VALID_PASSWORD,
) -> dict[str, str]:
    return {"email": email, "password": password}


def test_buyer_registration_succeeds(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    response = client.post(
        REGISTER_URL,
        json=_registration_payload(email="Buyer@Example.com"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "buyer@example.com"
    assert body["role"]["name"] == RoleName.BUYER.value
    assert body["is_active"] is True
    assert body["is_verified"] is False
    assert "password" not in response.text
    assert VALID_PASSWORD not in response.text

    with test_session_factory() as session:
        user = repository.get_user_by_email(session, "buyer@example.com")
        assert user is not None
        assert user.password_hash != VALID_PASSWORD
        assert user.password_hash.startswith("$argon2id$")


def test_duplicate_email_registration_is_rejected(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
) -> None:
    first = client.post(
        REGISTER_URL,
        json=_registration_payload(email="duplicate@example.com"),
    )
    second = client.post(
        REGISTER_URL,
        json=_registration_payload(email="DUPLICATE@example.com"),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["message"] == (
        "An account with this email already exists."
    )


def test_invalid_email_registration_is_rejected(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
) -> None:
    response = client.post(
        REGISTER_URL,
        json=_registration_payload(email="not-an-email"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_weak_password_registration_is_rejected(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
) -> None:
    response = client.post(
        REGISTER_URL,
        json=_registration_payload(
            email="weak@example.com",
            password=secrets.token_hex(2),
        ),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_public_registration_cannot_select_a_role(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    response = client.post(
        REGISTER_URL,
        json=_registration_payload(
            email="escalation@example.com",
            role=RoleName.ADMIN.value,
        ),
    )

    assert response.status_code == 422
    with test_session_factory() as session:
        assert repository.get_user_by_email(session, "escalation@example.com") is None


def test_login_returns_access_token(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="login@example.com")

    response = client.post(LOGIN_URL, json=_login_payload(user.email))

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert body["access_token"]

    profile = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == user.email


def test_incorrect_password_and_unknown_email_have_identical_errors(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="wrong-password@example.com")

    wrong_password = client.post(
        LOGIN_URL,
        json=_login_payload(user.email, WRONG_PASSWORD),
    )
    unknown_email = client.post(
        LOGIN_URL,
        json=_login_payload("unknown@example.com"),
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"
    assert "unknown@example.com" not in wrong_password.text


def test_inactive_account_cannot_log_in(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="inactive@example.com", is_active=False)

    response = client.post(LOGIN_URL, json=_login_payload(user.email))

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_password_reset_requires_single_use_token_and_revokes_sessions(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
    caplog,
) -> None:
    import logging
    caplog.set_level(logging.INFO)
    user = user_factory(email="reset@example.com")
    login = client.post(LOGIN_URL, json=_login_payload(user.email)).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    insecure = client.post("/api/v1/auth/reset-password", json={
        "email": user.email, "password": VALID_PASSWORD,
        "confirm_password": VALID_PASSWORD,
    })
    assert insecure.status_code == 422
    request = client.post("/api/v1/auth/reset-password", json={"email": user.email})
    assert request.status_code == 200
    from urllib.parse import parse_qs, urlparse
    reset_logs = [record.message for record in caplog.records if "Development password reset" in record.message]
    assert reset_logs, [record.message for record in caplog.records]
    plain = parse_qs(urlparse(reset_logs[-1].split(": ", 1)[-1]).query)["token"][0]

    confirmed = client.post("/api/v1/auth/reset-password/confirm", json={
        "token": plain, "password": "New-Secure-123!", "confirm_password": "New-Secure-123!",
    })
    assert confirmed.status_code == 200, confirmed.text
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    replay = client.post("/api/v1/auth/reset-password/confirm", json={
        "token": plain, "password": "New-Secure-123!", "confirm_password": "New-Secure-123!",
    })
    assert replay.status_code == 400
    assert client.post(LOGIN_URL, json=_login_payload(user.email, "New-Secure-123!")).status_code == 200


def test_logout_revokes_current_access_token(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="logout@example.com")
    token = client.post(LOGIN_URL, json=_login_payload(user.email)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_refresh_rotates_and_rejects_old_token(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="refresh@example.com")
    token = client.post(LOGIN_URL, json=_login_payload(user.email)).json()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token["refresh_token"]})
    assert response.status_code == 200, response.text
    assert response.json()["refresh_token"]
    assert response.json()["refresh_token"] != token["refresh_token"]
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token["refresh_token"]})
    assert replay.status_code == 401


def hashlib_token(token: str) -> str:
    from app.modules.auth.security import token_lookup
    return token_lookup(token)


def test_expired_access_token_is_rejected(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory: Callable[..., User],
    test_settings: Settings,
) -> None:
    user = user_factory(email="expired@example.com")
    token = create_access_token(
        user_id=user.id,
        role_name=user.role.name,
        tenant_id=user.tenant_id,
        security_version=user.security_version,
        settings=test_settings,
        expires_delta=timedelta(seconds=-5),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == (
        "Invalid or expired access token."
    )


def test_invalid_access_token_is_rejected(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == (
        "Invalid or expired access token."
    )
