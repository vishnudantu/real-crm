"""Integration tests for the generic approval request state machine."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    return {
        "factory": test_session_factory,
        "admin": admin,
        "sales": sales,
        "admin_headers": auth_headers(admin.email),
        "sales_headers": auth_headers(sales.email),
    }


def _create_request(client: TestClient, env: dict, *, request_type="SITE_VISIT_CAR") -> dict:
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": request_type,
            "reference_type": "booking",
            "reference_id": str(uuid4()),
            "reason": "Customer requested a chauffeured site visit.",
            "amount_paise": 250_000,
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_unwired_request(client: TestClient, env: dict) -> dict:
    """Create a request for an unwired pair (audit-only lifecycle)."""
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DEMAND_LETTER",
            "reference_type": "installment",
            "reference_id": str(uuid4()),
            "reason": "Generic lifecycle checks use an unwired pair.",
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def _decision(client: TestClient, env: dict, request_id: str, decision="APPROVED"):
    return client.post(
        f"/api/v1/approvals/requests/{request_id}/decision",
        json={"decision": decision, "note": "Reviewed by the manager."},
        headers=env["admin_headers"],
    )


def test_approver_must_be_active_admin_in_requester_tenant(
    client: TestClient, env: dict, user_factory
) -> None:
    other_tenant = Tenant(slug=f"ap-{uuid4().hex[:8]}", name="Approver Tenant")
    with env["factory"]() as session:
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    sales_approver = user_factory(role=RoleName.SALES_EXECUTIVE)

    for approver in (other_admin, sales_approver):
        response = client.post(
            "/api/v1/approvals/requests",
            json={
                "request_type": "DISCOUNT",
                "reference_type": "sale_booking",
                "reference_id": str(uuid4()),
                "reason": "The designated approver must be a tenant admin.",
                "approver_id": str(approver.id),
            },
            headers=env["sales_headers"],
        )
        assert response.status_code == 404


def test_staff_create_pending_request(client: TestClient, env: dict) -> None:
    reference_id = str(uuid4())
    approver_id = str(env["admin"].id)
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DISCOUNT",
            "reference_type": "sale_booking",
            "reference_id": reference_id,
            "reason": "A five percent discount requires approval.",
            "amount_paise": 500_000,
            "approver_id": approver_id,
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["requested_by_id"] == str(env["sales"].id)
    assert body["approver_id"] == approver_id
    assert body["reference_id"] == reference_id
    assert body["amount_paise"] == 500_000
    assert body["decided_at"] is None
    assert body["decision_note"] is None
    assert body["created_at"] and body["updated_at"]


def test_list_filters_by_status_type_and_tenant(client: TestClient, env: dict) -> None:
    car_id = _create_request(client, env)["id"]
    discount_id = _create_request(client, env, request_type="DISCOUNT")["id"]
    assert _decision(client, env, discount_id).status_code == 200

    response = client.get(
        "/api/v1/approvals/requests?status=PENDING&request_type=SITE_VISIT_CAR",
        headers=env["sales_headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [car_id]

    response = client.get("/api/v1/approvals/requests", headers=env["sales_headers"])
    assert {item["id"] for item in response.json()["items"]} == {car_id, discount_id}


@pytest.mark.parametrize("decision", ["APPROVED", "REJECTED"])
def test_admin_decision_sets_timestamp(client: TestClient, env: dict, decision: str) -> None:
    request_id = _create_unwired_request(client, env)["id"]
    response = _decision(client, env, request_id, decision=decision)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == decision
    assert body["approver_id"] == str(env["admin"].id)
    assert body["decision_note"] == "Reviewed by the manager."
    assert body["decided_at"] is not None


def test_requester_cannot_approve_their_own_request(client: TestClient, env: dict) -> None:
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DEMAND_LETTER",
            "reference_type": "installment",
            "reference_id": str(uuid4()),
            "reason": "Demand letter requires manager sign-off.",
        },
        headers=env["admin_headers"],
    )
    assert response.status_code == 201
    request_id = response.json()["id"]
    response = _decision(client, env, request_id)
    assert response.status_code == 409


def test_sales_executive_cannot_decide(client: TestClient, env: dict) -> None:
    request_id = _create_request(client, env)["id"]
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/decision",
        json={"decision": "APPROVED"},
        headers=env["sales_headers"],
    )
    assert response.status_code == 403


@pytest.mark.parametrize("terminal_decision", ["APPROVED", "REJECTED"])
def test_non_pending_request_cannot_be_decided(
    client: TestClient, env: dict, terminal_decision: str
) -> None:
    request_id = _create_unwired_request(client, env)["id"]
    assert _decision(client, env, request_id, decision=terminal_decision).status_code == 200
    response = _decision(client, env, request_id)
    assert response.status_code == 400


def test_requester_cancels_only_pending_request(client: TestClient, env: dict) -> None:
    request_id = _create_unwired_request(client, env)["id"]
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["sales_headers"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["decided_at"] is None
    repeated = client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["sales_headers"]
    )
    assert repeated.status_code == 400


def test_admin_can_cancel_and_other_requester_cannot(client: TestClient, env: dict, user_factory, auth_headers) -> None:
    request_id = _create_unwired_request(client, env)["id"]
    other_sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel",
        headers=auth_headers(other_sales.email),
    )
    assert response.status_code == 403
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["admin_headers"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.parametrize("method,path", [("post", "/requests"), ("get", "/requests")])
def test_buyer_cannot_request_or_list(
    client: TestClient, env: dict, user_factory, auth_headers, method: str, path: str
) -> None:
    buyer = user_factory(role=RoleName.BUYER)
    response = getattr(client, method)(
        f"/api/v1/approvals{path}",
        headers=auth_headers(buyer.email),
        **({"json": {
            "request_type": "SITE_VISIT_CAR",
            "reference_type": "booking",
            "reference_id": str(uuid4()),
            "reason": "A buyer cannot request staff approvals.",
        }} if method == "post" else {}),
    )
    assert response.status_code == 403


def test_cross_tenant_decision_and_cancel_return_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    other_headers = auth_headers(other_admin.email)
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DISCOUNT",
            "reference_type": "sale_booking",
            "reference_id": str(uuid4()),
            "reason": "An isolated tenant request.",
        },
        headers=other_headers,
    )
    assert response.status_code == 201
    request_id = response.json()["id"]

    response = _decision(client, env, request_id)
    assert response.status_code == 404
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["admin_headers"]
    )
    assert response.status_code == 404


def test_cancelled_request_cannot_be_decided(client: TestClient, env: dict) -> None:
    request_id = _create_unwired_request(client, env)["id"]
    assert client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["sales_headers"]
    ).status_code == 200
    response = _decision(client, env, request_id)
    assert response.status_code == 400


def test_own_terminal_request_reports_pending_error_before_self_approval(
    client: TestClient, env: dict
) -> None:
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DEMAND_LETTER",
            "reference_type": "installment",
            "reference_id": str(uuid4()),
            "reason": "Admin-created request reaches its terminal state first.",
        },
        headers=env["admin_headers"],
    )
    request_id = response.json()["id"]
    assert client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel", headers=env["admin_headers"]
    ).status_code == 200
    decided = _decision(client, env, request_id)
    assert decided.status_code == 400


def test_list_is_paged_and_reports_total(client: TestClient, env: dict) -> None:
    for _ in range(3):
        _create_request(client, env)
    page = client.get(
        "/api/v1/approvals/requests?limit=2&offset=0", headers=env["sales_headers"]
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 3
    assert body["limit"] == 2 and body["offset"] == 0
    assert len(body["items"]) == 2
    second = client.get(
        "/api/v1/approvals/requests?limit=2&offset=2", headers=env["sales_headers"]
    ).json()
    assert second["total"] == 3 and len(second["items"]) == 1
    assert {item["id"] for item in body["items"]} != {item["id"] for item in second["items"]}


def test_decision_rejects_cancelled_status_422(client: TestClient, env: dict) -> None:
    request_id = _create_request(client, env)["id"]
    response = client.post(
        f"/api/v1/approvals/requests/{request_id}/decision",
        json={"decision": "CANCELLED"},
        headers=env["admin_headers"],
    )
    assert response.status_code == 422


def test_service_rejects_non_admin_decision(env: dict) -> None:
    from fastapi import HTTPException
    from app.modules.approvals import service

    with env["factory"]() as session:
        sales = session.get(User, env["sales"].id)
        request = service.request_approval(
            session,
            actor=sales,
            request_type="DISCOUNT",
            reference_type="sale_booking",
            reference_id=uuid4(),
            reason="Sales staff cannot make their own decision.",
        )
        try:
            service.decide(
                session, actor=sales, request_id=request.id, decision="APPROVED"
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            pytest.fail("Non-admin service decision must be forbidden.")


def test_wired_decision_on_missing_entity_rejected_before_status_flip(env: dict) -> None:
    from app.modules.approvals import service
    from app.modules.approvals.exceptions import ApprovalReferenceMissingError
    from app.modules.approvals.models import ApprovalStatus

    with env["factory"]() as session:
        sales = session.get(User, env["sales"].id)
        admin = session.get(User, env["admin"].id)
        request = service.request_approval(
            session,
            actor=sales,
            request_type="SITE_VISIT_CAR",
            reference_type="booking",
            reference_id=uuid4(),
            reason="The booking no longer exists.",
        )
        assert request.id is not None
        try:
            service.decide(session, actor=admin, request_id=request.id, decision="APPROVED")
        except ApprovalReferenceMissingError:
            pass
        else:
            pytest.fail("A wired decision on a missing entity must raise 400.")
        session.rollback()
        # The request stays PENDING: nothing was decided, nothing was committed.
        reloaded = service.list_requests(
            session, tenant_id=sales.tenant_id, status="PENDING",
            request_type="SITE_VISIT_CAR",
        )
        assert [item.id for item in reloaded] == [request.id]
        assert reloaded[0].status == ApprovalStatus.PENDING.value


def test_migration_upgrade_and_downgrade_on_isolated_sqlite() -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    # Resolve only tenant/user tables needed for the migration's foreign keys.
    import app.modules.approvals.models  # noqa: F401

    migration_path = next(
        (Path(__file__).parents[2] / "alembic" / "versions").glob("*a2b3c4d5e6f7*")
    )
    spec = importlib.util.spec_from_file_location("approval_requests_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "a2b3c4d5e6f7"
    assert migration.down_revision == "f1a2b3c4d5e6"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.connect() as connection:
            for table_name in ("roles", "tenants", "users"):
                Base.metadata.tables[table_name].create(connection)
            context = MigrationContext.configure(connection)
            original_get_bind = Operations.get_bind
            Operations.get_bind = lambda self: connection
            try:
                with Operations.context(context):
                    migration.upgrade()
                    table_names = inspect(connection).get_table_names()
                    assert "approval_requests" in table_names
                    index_names = {
                        index["name"]
                        for index in inspect(connection).get_indexes("approval_requests")
                    }
                    assert index_names == {
                        "ix_approval_requests_reference_id",
                        "ix_approval_requests_tenant_id",
                        "ix_approval_requests_tenant_status",
                        "ix_approval_requests_tenant_request_type",
                        "ix_approval_requests_tenant_id_id",
                    }
                    migration.downgrade()
                    assert "approval_requests" not in inspect(connection).get_table_names()
            finally:
                Operations.get_bind = original_get_bind
    finally:
        engine.dispose()
