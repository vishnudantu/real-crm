"""CORS scope tests: widget is cross-origin, the rest of the API is not.

A dedicated app instance is used with an overridden DB dependency so these
checks exercise middleware only and never touch a real database.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.modules.tenancy.models import Tenant


@pytest.fixture()
def cors_app(
    isolated_app: FastAPI,
    test_session_factory: sessionmaker[Session],
) -> FastAPI:
    def _get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    isolated_app.dependency_overrides[get_db] = _get_db
    return isolated_app


class TestWidgetCors:
    def test_widget_preflight_allows_any_origin(self, cors_app: FastAPI) -> None:
        with TestClient(cors_app) as client:
            response = client.options(
                "/api/v1/widget/some-tenant/session",
                headers={
                    "Origin": "https://builder-site.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Authorization, Content-Type",
                },
            )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "POST" in response.headers["access-control-allow-methods"]
        assert "Authorization" in response.headers["access-control-allow-headers"]

    def test_widget_actual_response_carries_wildcard(
        self, cors_app: FastAPI, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as db:
            db.add(Tenant(slug="widget-cors-site", name="CORS Site"))
            db.commit()
        with TestClient(cors_app) as client:
            response = client.get(
                "/api/v1/widget/widget-cors-site/embed.js",
                headers={"Origin": "https://builder-site.example"},
            )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"

    def test_non_widget_endpoints_keep_restricted_cors(self, cors_app: FastAPI) -> None:
        with TestClient(cors_app) as client:
            response = client.get(
                "/api/v1/health",
                headers={"Origin": "https://builder-site.example"},
            )
        # The general CORS policy must not be widened by the widget override.
        assert response.headers.get("access-control-allow-origin") in (None, "http://testserver")
        assert response.headers.get("access-control-allow-origin") != "*"

    def test_widget_does_not_allow_credentials(
        self, cors_app: FastAPI, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as db:
            db.add(Tenant(slug="widget-cors-site", name="CORS Site"))
            db.commit()
        with TestClient(cors_app) as client:
            response = client.get(
                "/api/v1/widget/widget-cors-site/embed.js",
                headers={"Origin": "https://builder-site.example"},
            )
        # Cross-origin credential sharing must never be enabled for widgets.
        assert response.headers.get("access-control-allow-credentials") != "true"
