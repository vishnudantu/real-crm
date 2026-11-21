"""Unit tests for per-tenant feature resolution and operator overrides."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.modules.operator import features
from app.modules.operator.feature_models import TenantFeature
from app.modules.operator.feature_service import (
    reset_feature,
    set_feature,
    tenant_feature_matrix,
)
from app.modules.operator.models import OperatorUser
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant


def _operator(session: Session) -> OperatorUser:
    row = OperatorUser(
        email=f"op-{uuid4().hex[:8]}@propflow.example",
        full_name="Owner",
        password_hash="not-used",
        role="OWNER",
    )
    session.add(row)
    session.flush()
    return row


class TestResolutionOrder:
    def test_defaults_when_no_plan_or_override(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            resolved = features.resolve_features(session, tenant_id=tenant.id, plan_features={})
            assert resolved["core_leads"] is True
            assert resolved["omnichannel_inbox"] is False
            assert resolved["calling"] is False
            assert resolved["web_widget"] is True

    def test_plan_enables_opt_in_feature(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            resolved = features.resolve_features(
                session, tenant_id=tenant.id, plan_features={"calling": True}
            )
            assert resolved["calling"] is True

    def test_plan_can_disable_default_on_feature(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            resolved = features.resolve_features(
                session, tenant_id=tenant.id, plan_features={"web_widget": False}
            )
            assert resolved["web_widget"] is False

    def test_override_beats_plan(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            set_feature(
                session, operator=operator, tenant_id=tenant.id,
                feature="calling", enabled=True, reason="Upgrade",
            )
            resolved = features.resolve_features(
                session, tenant_id=tenant.id, plan_features={"calling": False}
            )
            assert resolved["calling"] is True


class TestOperatorActions:
    def test_enable_disable_and_reset(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()

            set_feature(session, operator=operator, tenant_id=tenant.id, feature="calling", enabled=True)
            assert features.tenant_feature_state(session, tenant_id=tenant.id, key="calling")

            set_feature(session, operator=operator, tenant_id=tenant.id, feature="calling", enabled=False)
            assert not features.tenant_feature_state(session, tenant_id=tenant.id, key="calling")

            reset_feature(session, operator=operator, tenant_id=tenant.id, feature="calling")
            assert session.query(TenantFeature).filter_by(tenant_id=tenant.id).count() == 0

    def test_unknown_feature_rejected(self, test_session_factory: sessionmaker[Session]) -> None:
        from fastapi import HTTPException
        import pytest

        with test_session_factory() as session:
            operator = _operator(session)
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            with pytest.raises(HTTPException) as exc_info:
                set_feature(session, operator=operator, tenant_id=tenant.id, feature="teleportation", enabled=True)
            assert exc_info.value.status_code == 400

    def test_override_records_audit_and_reason(self, test_session_factory: sessionmaker[Session]) -> None:
        from sqlalchemy import select

        from app.modules.operator.models import OperatorAuditLog

        with test_session_factory() as session:
            operator = _operator(session)
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            set_feature(
                session, operator=operator, tenant_id=tenant.id,
                feature="omnichannel_inbox", enabled=True, reason="Pilot customer",
            )
            log = session.scalar(
                select(OperatorAuditLog).where(OperatorAuditLog.action == "FEATURE_ENABLED")
            )
            assert log is not None
            assert log.details["reason"] == "Pilot customer"

    def test_matrix_reports_source(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            operator = _operator(session)
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co")
            session.add(tenant)
            session.flush()
            set_feature(session, operator=operator, tenant_id=tenant.id, feature="calling", enabled=True)
            matrix = {row["feature"]: row for row in tenant_feature_matrix(session, tenant_id=tenant.id)}
            assert matrix["calling"]["source"] == "TENANT_OVERRIDE"
            assert matrix["calling"]["enabled"] is True
            assert matrix["core_leads"]["source"] == "CATALOG_DEFAULT"
            assert matrix["omnichannel_inbox"]["enabled"] is False


class TestTenantFeatureStateWithPlan:
    def test_plan_from_database_is_applied(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            plan = Plan(
                code=f"pro-{uuid4().hex[:6]}", name="Pro", price_paise=49900,
                features={"omnichannel_inbox": True, "channel_whatsapp": True},
            )
            session.add(plan)
            session.flush()  # assign plan.id before referencing it on the tenant
            tenant = Tenant(slug=f"flag-{uuid4().hex[:8]}", name="Flag Co", plan_id=plan.id)
            session.add(tenant)
            session.flush()
            assert features.tenant_feature_state(session, tenant_id=tenant.id, key="omnichannel_inbox")
            assert features.tenant_feature_state(session, tenant_id=tenant.id, key="channel_whatsapp")
            assert not features.tenant_feature_state(session, tenant_id=tenant.id, key="calling")
