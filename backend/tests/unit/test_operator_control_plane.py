"""Tests for the operator tenant control-plane (config/usage/health/impersonation/features)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import decode_access_token, hash_password
from app.modules.operator import control_plane
from app.modules.operator.models import OperatorAuditLog, OperatorPermission, OperatorUser
from app.modules.operator.schemas import TenantConfigPatchRequest
from app.modules.operator.security import create_operator_token
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _operator(session: Session, *, role: str = "OWNER") -> OperatorUser:
    row = OperatorUser(
        email=f"op-{uuid4().hex[:8]}@propflow.example",
        full_name="Owner",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
    )
    session.add(row)
    session.flush()
    return row


def _tenant(session: Session, *, plan: Plan | None = None, status_value: str = TenantStatus.ACTIVE.value) -> Tenant:
    row = Tenant(
        slug=f"t-{uuid4().hex[:8]}",
        name="Acme Realty",
        brand_name="Acme",
        status=status_value,
        plan_id=plan.id if plan else None,
    )
    session.add(row)
    session.flush()
    return row


def _plan(session: Session) -> Plan:
    row = Plan(
        code=f"pro-{uuid4().hex[:6]}",
        name="Pro",
        price_paise=49900,
        max_users=5,
        leads_per_month=100,
        whatsapp_msgs_per_month=200,
    )
    session.add(row)
    session.flush()
    return row


def _admin_user(session: Session, *, tenant: Tenant, role_name: RoleName = RoleName.ADMIN) -> User:
    from app.modules.users import repository as users_repo

    role = users_repo.get_role_by_name(session, role_name)
    if role is None:
        from app.modules.users.service import seed_roles
        seed_roles(session)
        role = users_repo.get_role_by_name(session, role_name)
    user = User(
        tenant_id=tenant.id,
        full_name="Tenant Admin",
        email=f"admin-{uuid4().hex[:6]}@acme.example",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


# ---------------------------------------------------------------------------
# Config patch validation
# ---------------------------------------------------------------------------


class TestConfigPatchValidation:
    def test_valid_timezone(self) -> None:
        payload = TenantConfigPatchRequest(timezone="Asia/Kolkata")
        assert payload.timezone == "Asia/Kolkata"

    def test_invalid_timezone_rejected(self) -> None:
        with pytest.raises(Exception):
            TenantConfigPatchRequest(timezone="not a timezone!!")

    def test_currency_rupee_rejected(self) -> None:
        with pytest.raises(Exception):
            TenantConfigPatchRequest(currency="RUPEE")

    def test_currency_normalized(self) -> None:
        payload = TenantConfigPatchRequest(currency="usd")
        assert payload.currency == "USD"


class TestConfigPatchAudit:
    def test_changed_fields_only_and_theme_capped(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            tenant.theme_json = {"color": "red"}
            session.flush()

            payload = TenantConfigPatchRequest(
                brand_name="NewBrand",
                theme_json={"font": "Inter", "big": "x" * 500},
            )
            control_plane.update_tenant_config(
                session, operator=operator, tenant_id=tenant.id, payload=payload
            )

            log = session.scalar(
                select(OperatorAuditLog).where(OperatorAuditLog.action == "TENANT_CONFIG_UPDATED")
            )
            assert log is not None
            changed = log.details["changed_fields"]
            assert "brand_name" in changed
            assert changed["brand_name"]["after"] == "NewBrand"
            assert "timezone" not in changed
            # theme deep-merged one level, unknown keys kept
            assert tenant.theme_json["color"] == "red"
            assert tenant.theme_json["font"] == "Inter"
            # theme blob capped in audit detail
            theme_after = changed["theme_json"]["after"]
            assert theme_after.get("_truncated") is True


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class TestUsage:
    def test_period_fields_and_lifetime(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        from app.modules.leads.models import Lead
        from app.modules.projects.models import Project

        with test_session_factory() as session:
            plan = _plan(session)
            tenant = _tenant(session, plan=plan)
            admin = _admin_user(session, tenant=tenant)
            project = Project(
                tenant_id=tenant.id,
                name="Skyline",
                slug=f"sky-{uuid4().hex[:6]}",
                location="Pune",
                created_by=admin.id,
            )
            session.add(project)
            session.flush()
            lead = Lead(
                tenant_id=tenant.id,
                full_name="Buyer One",
                email="b1@x.example",
                project_id=project.id,
                source="WEBSITE",
                status="NEW",
                created_at=datetime.now(UTC),
            )
            session.add(lead)
            session.flush()

            result = control_plane.tenant_usage(session, tenant_id=tenant.id, days=30)
            meters = result["meters"]
            assert meters["leads"]["period_source"] == "ROLLING_30D"
            assert meters["leads"]["limit"] == 100
            assert meters["leads"]["used"] >= 1
            assert meters["messages"]["limit"] == 200
            assert meters["users"]["limit"] == 5
            assert "period_start" in meters["leads"]
            assert result["leads_total"] == 1
            assert len(result["series"]) == 30
            assert all({"date", "leads", "messages_sent"} <= set(p) for p in result["series"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_suspended_tenant_is_red(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant = _tenant(session, status_value=TenantStatus.SUSPENDED.value)
            result = control_plane.tenant_health(session, tenant_id=tenant.id)
            checks = {c["name"]: c for c in result["checks"]}
            assert checks["tenant_active"]["state"] == "red"
            assert result["overall"] == "red"

    def test_active_tenant_active_check_green(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant = _tenant(session)
            result = control_plane.tenant_health(session, tenant_id=tenant.id)
            checks = {c["name"]: c for c in result["checks"]}
            assert checks["tenant_active"]["state"] == "green"
            expected = {
                "tenant_active", "plan_current", "widget_enabled",
                "channels_configured", "ai_configured", "recent_activity",
            }
            assert set(checks) == expected


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------


class TestImpersonation:
    def test_refuses_non_active_tenant(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session, status_value=TenantStatus.SUSPENDED.value)
            with pytest.raises(HTTPException) as exc:
                control_plane.impersonate_tenant(session, operator=operator, tenant_id=tenant.id)
            assert exc.value.status_code == 409

    def test_success_returns_normal_tenant_token(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            admin = _admin_user(session, tenant=tenant)
            result = control_plane.impersonate_tenant(session, operator=operator, tenant_id=tenant.id)
            assert result["expires_in"] == 900
            assert result["user"]["role"] == RoleName.ADMIN.value
            claims = decode_access_token(result["access_token"])
            assert claims.subject == admin.id
            assert claims.tenant_id == tenant.id
            log = session.scalar(
                select(OperatorAuditLog).where(OperatorAuditLog.action == "IMPERSONATION_STARTED")
            )
            assert log is not None
            assert log.details["slug"] == tenant.slug
            assert log.details["target_user_id"] == str(admin.id)


# ---------------------------------------------------------------------------
# Bulk features
# ---------------------------------------------------------------------------


class TestBulkFeatures:
    def test_unknown_key_rejected(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            with pytest.raises(HTTPException) as exc:
                control_plane.bulk_set_features(
                    session, operator=operator, tenant_id=tenant.id,
                    features_map={"calling": True, "teleportation": True},
                )
            assert exc.value.status_code == 400
            assert "teleportation" in exc.value.detail["unknown"]

    def test_bulk_apply_returns_matrix(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            matrix = control_plane.bulk_set_features(
                session, operator=operator, tenant_id=tenant.id,
                features_map={"calling": True, "connectors": True},
            )
            by_key = {row["feature"]: row for row in matrix}
            assert by_key["calling"]["enabled"] is True
            assert by_key["connectors"]["enabled"] is True


# ---------------------------------------------------------------------------
# Route-level (TestClient) tests: impersonate, bulk features, config patch, audit filters
# ---------------------------------------------------------------------------


def _operator_headers(operator: OperatorUser, settings) -> dict[str, str]:
    token = create_operator_token(operator, settings=settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client_with_db(client, override_db):
    return client


class TestRoutes:
    def test_impersonate_route(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            _admin_user(session, tenant=tenant)
            session.commit()
            headers = _operator_headers(operator, test_settings)
            tid = tenant.id

        resp = client_with_db.post(
            f"/api/v1/operator/tenants/{tid}/impersonate", headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["expires_in"] == 900
        assert body["user"]["role"] == RoleName.ADMIN.value
        claims = decode_access_token(body["access_token"], settings=test_settings)
        assert claims.tenant_id == tid

    def test_impersonate_route_forbidden_for_support(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            support = _operator(session, role="SUPPORT")
            tenant = _tenant(session)
            _admin_user(session, tenant=tenant)
            session.commit()
            headers = _operator_headers(support, test_settings)
            tid = tenant.id
        resp = client_with_db.post(
            f"/api/v1/operator/tenants/{tid}/impersonate", headers=headers
        )
        assert resp.status_code == 403

    def test_bulk_features_route(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            session.commit()
            headers = _operator_headers(operator, test_settings)
            tid = tenant.id
        resp = client_with_db.put(
            f"/api/v1/operator/tenants/{tid}/features",
            headers=headers,
            json={"features": {"calling": True, "connectors": True}},
        )
        assert resp.status_code == 200, resp.text
        by_key = {row["feature"]: row for row in resp.json()}
        assert by_key["calling"]["enabled"] is True
        assert by_key["connectors"]["enabled"] is True

    def test_config_patch_route_audit_shape(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            session.commit()
            headers = _operator_headers(operator, test_settings)
            tid = tenant.id
            slug = tenant.slug
        resp = client_with_db.patch(
            f"/api/v1/operator/tenants/{tid}/config",
            headers=headers,
            json={"brand_name": "Rebrand", "timezone": "Asia/Kolkata", "currency": "INR"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["branding"]["brand_name"] == "Rebrand"

        audit_resp = client_with_db.get(
            "/api/v1/operator/audit-logs",
            headers=headers,
            params={"action": "TENANT_CONFIG_UPDATED", "tenant_slug": slug},
        )
        assert audit_resp.status_code == 200, audit_resp.text
        logs = audit_resp.json()
        assert len(logs) >= 1
        changed = logs[0]["details"]["changed_fields"]
        assert changed["brand_name"]["after"] == "Rebrand"

    def test_config_patch_route_rejects_bad_currency(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = _tenant(session)
            session.commit()
            headers = _operator_headers(operator, test_settings)
            tid = tenant.id
        resp = client_with_db.patch(
            f"/api/v1/operator/tenants/{tid}/config",
            headers=headers,
            json={"currency": "RUPEE"},
        )
        assert resp.status_code == 422

    def test_audit_filter_action(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            _tenant(session)
            session.commit()
            headers = _operator_headers(operator, test_settings)
        # seed a couple of audit rows
        with test_session_factory() as session:
            from app.modules.operator.service import audit
            op = session.scalar(select(OperatorUser))
            audit(session, operator=op, action="TENANT_PROVISIONED",
                  resource_type="TENANT", resource_id="t-1", details={"slug": "alpha"})
            audit(session, operator=op, action="FEATURE_ENABLED",
                  resource_type="TENANT_FEATURE", resource_id="beta:calling", details={})
            session.commit()
        resp = client_with_db.get(
            "/api/v1/operator/audit-logs",
            headers=headers,
            params={"action": "TENANT_PROVISIONED"},
        )
        assert resp.status_code == 200, resp.text
        logs = resp.json()
        assert all(log["action"] == "TENANT_PROVISIONED" for log in logs)
        assert len(logs) >= 1

    def test_audit_filter_tenant_slug_via_details(
        self, client_with_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            session.commit()
            headers = _operator_headers(operator, test_settings)
        with test_session_factory() as session:
            from app.modules.operator.service import audit
            op = session.scalar(select(OperatorUser))
            audit(session, operator=op, action="TENANT_PROVISIONED",
                  resource_type="TENANT", resource_id="xyz", details={"slug": "alpha-co"})
            session.commit()
        resp = client_with_db.get(
            "/api/v1/operator/audit-logs",
            headers=headers,
            params={"tenant_slug": "alpha-co"},
        )
        assert resp.status_code == 200, resp.text
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["details"]["slug"] == "alpha-co"
