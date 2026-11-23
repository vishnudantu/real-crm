"""Module-count pricing from plan bundles and per-tenant feature overrides."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.modules.operator import features, pricing
from app.modules.operator.feature_models import TenantFeature
from app.modules.operator.models import OperatorUser
from app.modules.operator.security import create_operator_token
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant


def _tenant(session: Session, *, plan: Plan | None = None) -> Tenant:
    row = Tenant(slug=f"pricing-{uuid4().hex[:8]}", name="Pricing Co")
    if plan is not None:
        row.plan_id = plan.id
    session.add(row)
    session.flush()
    return row


def _plan(session: Session, *, price_paise: int = 49900, feature_map: dict | None = None) -> Plan:
    row = Plan(
        code=f"pricing-{uuid4().hex[:8]}",
        name="Pricing plan",
        price_paise=price_paise,
        features=feature_map or {},
    )
    session.add(row)
    session.flush()
    return row


def _override(session: Session, *, tenant: Tenant, feature: str, enabled: bool) -> TenantFeature:
    row = TenantFeature(tenant_id=tenant.id, feature=feature, enabled=enabled)
    session.add(row)
    session.flush()
    return row


def _operator(session: Session) -> OperatorUser:
    row = OperatorUser(
        email=f"pricing-{uuid4().hex[:8]}@propflow.example",
        full_name="Pricing Operator",
        password_hash="not-used",
        role="OWNER",
    )
    session.add(row)
    session.flush()
    return row


class TestModulePricing:
    def test_default_core_modules_are_free(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant = _tenant(session)

            result = pricing.compute_tenant_module_total(session, tenant.id)

            assert "core_leads" in result["enabled"]
            assert "core_visits" in result["enabled"]
            assert features.module_price("core_leads") == 0
            assert features.module_price("core_visits") == 0
            assert result["module_count"] == len(result["enabled"])
            assert result["monthly_paise"] == sum(
                features.module_price(key) for key in result["enabled"]
            )
            assert result["currency"] == "INR"

    def test_tenant_toggles_change_module_total(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant = _tenant(session)
            before = pricing.compute_tenant_module_total(session, tenant.id)
            calling_price = features.module_price("calling")
            assert calling_price > 0

            override = _override(session, tenant=tenant, feature="calling", enabled=True)
            enabled = pricing.compute_tenant_module_total(session, tenant.id)
            assert "calling" in enabled["enabled"]
            assert enabled["module_count"] == before["module_count"] + 1
            assert enabled["monthly_paise"] == before["monthly_paise"] + calling_price

            override.enabled = False
            session.flush()
            disabled = pricing.compute_tenant_module_total(session, tenant.id)
            assert disabled == before

    def test_plan_base_plus_only_unbundled_addons(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            bundled = {
                spec.key: True for spec in features.FEATURE_CATALOG if spec.default_enabled
            }
            bundled["calling"] = True
            plan = _plan(session, price_paise=125000, feature_map=bundled)
            tenant = _tenant(session, plan=plan)
            _override(session, tenant=tenant, feature="calling", enabled=True)
            _override(session, tenant=tenant, feature="post_sales", enabled=True)

            result = pricing.compute_tenant_monthly_pricing(session, tenant.id)

            assert result["plan_base_paise"] == 125000
            assert result["addon_paise"] == features.module_price("post_sales")
            assert result["effective_monthly_paise"] == (
                125000 + features.module_price("post_sales")
            )
            modules = {row["feature"]: row for row in result["modules"]}
            assert modules["calling"]["bundled_in_plan"] is True
            assert modules["post_sales"]["bundled_in_plan"] is False
            assert modules["post_sales"]["monthly_paise"] > 0


class TestPricingRoute:
    def test_returns_breakdown(
        self, client, override_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            plan = _plan(session, price_paise=75000, feature_map={"calling": True})
            tenant = _tenant(session, plan=plan)
            _override(session, tenant=tenant, feature="calling", enabled=True)
            _override(session, tenant=tenant, feature="post_sales", enabled=True)
            session.commit()
            tenant_id = tenant.id
            token = create_operator_token(operator, settings=test_settings)

        response = client.get(
            f"/api/v1/operator/tenants/{tenant_id}/pricing",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["plan_base_paise"] == 75000
        assert body["module_count"] == len(body["enabled"])
        assert body["monthly_paise"] == sum(
            row["monthly_paise"] for row in body["modules"]
        )
        assert body["addon_paise"] == sum(
            row["monthly_paise"]
            for row in body["modules"]
            if not row["bundled_in_plan"]
        )
        assert body["effective_monthly_paise"] == 75000 + body["addon_paise"]
        modules = {row["feature"]: row for row in body["modules"]}
        assert modules["calling"]["bundled_in_plan"] is True
        assert modules["post_sales"]["monthly_paise"] > 0

    def test_unknown_tenant_returns_404(
        self, client, override_db, test_session_factory, test_settings
    ) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            session.commit()
            token = create_operator_token(operator, settings=test_settings)

        response = client.get(
            f"/api/v1/operator/tenants/{uuid4()}/pricing",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
