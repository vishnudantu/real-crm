"""Integration tests for the deal-desk vertical slice.

Covers:

- Discount matrix: default seed (2% / 5% / blocked-above-5%), admin/manager
  edits, ladder validation, role gates.
- Band enforcement at quote creation and at request time (a tightened matrix
  blocks a quote that was legal when written).
- End-to-end DEAL_DISCOUNT flow: quote -> discount-request (approval created,
  unit flagged PENDING) -> decide APPROVED (unit discount written through the
  existing approvals dispatch path) / REJECTED (flag only) / CANCEL (revert,
  quote re-raisable).
- Cost sheet CRUD: project-generic + unit-specific scopes, uniqueness, patch.
- Cross-tenant reads are 404s; buyers get no access.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.deal_desk.models import DiscountQuote
from app.modules.inventory.models import DiscountStatus, PropertyUnit
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.project_support import create_project

GROSS = 10_000_000  # Rs 1,00,000.00 in paise


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    manager = user_factory(role=RoleName.MANAGER)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    return {
        "factory": test_session_factory,
        "admin": admin,
        "manager": manager,
        "sales": sales,
        "admin_headers": auth_headers(admin.email),
        "manager_headers": auth_headers(manager.email),
        "sales_headers": auth_headers(sales.email),
    }


def _active_project(client: TestClient, env: dict) -> dict:
    project = create_project(client, env["admin_headers"])
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": "ACTIVE"},
        headers=env["admin_headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


def _unit(client: TestClient, env: dict, *, project: dict | None = None) -> dict:
    project = project or _active_project(client, env)
    created = client.post(
        "/api/v1/inventory/units",
        headers=env["admin_headers"],
        json={
            "project_id": project["id"],
            "internal_code": f"DD-{uuid4().hex[:6].upper()}",
            "configuration": "3 BHK",
            "status": "AVAILABLE",
        },
    )
    assert created.status_code == 201, created.text
    return {"project": project, "unit": created.json()}


def _quote(
    client: TestClient, env: dict, unit_id: str, percent: str,
    *, headers: dict | None = None, gross: int = GROSS,
) -> dict:
    response = client.post(
        "/api/v1/deal-desk/quotes",
        json={
            "unit_id": unit_id,
            "gross_price_paise": gross,
            "discount_percent": percent,
        },
        headers=headers or env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def _raise_discount(client: TestClient, env: dict, quote_id: str, reason: str | None = None) -> "tuple[int, dict]":
    body = {"reason": reason} if reason is not None else {}
    response = client.post(
        f"/api/v1/deal-desk/quotes/{quote_id}/discount-request",
        json=body,
        headers=env["sales_headers"],
    )
    return response.status_code, response.json()


def _decide(client: TestClient, env: dict, request_id: str, decision: str, headers: dict | None = None):
    return client.post(
        f"/api/v1/approvals/requests/{request_id}/decision",
        json={"decision": decision, "note": "Deal desk review."},
        headers=headers or env["admin_headers"],
    )


def _unit_state(factory, unit_id: str) -> tuple[str, int | None]:
    with factory() as session:
        unit = session.get(PropertyUnit, UUID(unit_id))
        return unit.discount_status, unit.approved_discount_paise


def _quote_status(factory, quote_id: str) -> str:
    with factory() as session:
        return session.get(DiscountQuote, UUID(quote_id)).status


DEFAULT_LADDER = [
    {"max_discount_percent": "2.00", "reason_required": False, "blocked": False,
     "description": "Band 1 — one admin approval."},
    {"max_discount_percent": "5.00", "reason_required": True, "blocked": False,
     "description": "Band 2 — admin approval with reason."},
    {"reason_required": True, "blocked": True,
     "description": "Above 5% — blocked."},
]


# ---------------------------------------------------------------------------
# Discount matrix
# ---------------------------------------------------------------------------


def test_default_matrix_seeded_on_first_read(client: TestClient, env: dict) -> None:
    response = client.get(
        "/api/v1/deal-desk/discount-matrix", headers=env["admin_headers"]
    )
    assert response.status_code == 200, response.text
    bands = response.json()["bands"]
    assert [band["band_number"] for band in bands] == [1, 2, 3]
    assert Decimal(str(bands[0]["max_discount_percent"])) == Decimal("2")
    assert bands[0]["reason_required"] is False and bands[0]["blocked"] is False
    assert Decimal(str(bands[1]["max_discount_percent"])) == Decimal("5")
    assert bands[1]["reason_required"] is True and bands[1]["blocked"] is False
    assert bands[2]["max_discount_percent"] is None and bands[2]["blocked"] is True


def test_manager_can_edit_matrix(client: TestClient, env: dict) -> None:
    tightened = [
        {"max_discount_percent": "1.00", "reason_required": False, "blocked": False},
        {"reason_required": True, "blocked": True},
    ]
    response = client.put(
        "/api/v1/deal-desk/discount-matrix",
        json={"bands": tightened},
        headers=env["manager_headers"],
    )
    assert response.status_code == 200, response.text
    bands = response.json()["bands"]
    assert [band["band_number"] for band in bands] == [1, 2]
    assert Decimal(str(bands[0]["max_discount_percent"])) == Decimal("1")

    again = client.get("/api/v1/deal-desk/discount-matrix", headers=env["admin_headers"])
    assert len(again.json()["bands"]) == 2


def test_matrix_ladder_validation_rejects_bad_ladders(
    client: TestClient, env: dict
) -> None:
    bad = [
        # descending thresholds
        [ {"max_discount_percent": "5.00"}, {"max_discount_percent": "2.00"}, {"blocked": True} ],
        # no blocked ceiling
        [ {"max_discount_percent": "2.00"}, {"max_discount_percent": "5.00"} ],
        # a middle band blocked
        [ {"max_discount_percent": "2.00", "blocked": True}, {"max_discount_percent": "5.00"}, {"blocked": True} ],
    ]
    for ladder in bad:
        response = client.put(
            "/api/v1/deal-desk/discount-matrix",
            json={"bands": ladder},
            headers=env["admin_headers"],
        )
        assert response.status_code == 422, (ladder, response.text)


def test_matrix_edit_requires_manage_permission(client: TestClient, env: dict) -> None:
    response = client.put(
        "/api/v1/deal-desk/discount-matrix",
        json={"bands": DEFAULT_LADDER},
        headers=env["sales_headers"],
    )
    assert response.status_code == 403, response.text


def test_buyer_cannot_read_matrix(client: TestClient, env: dict, user_factory, auth_headers) -> None:
    buyer = user_factory(role=RoleName.BUYER)
    response = client.get(
        "/api/v1/deal-desk/discount-matrix", headers=auth_headers(buyer.email)
    )
    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Cost sheet CRUD
# ---------------------------------------------------------------------------


def _cost_sheet(client: TestClient, env: dict, project_id: str, *, unit_id: str | None = None, headers: dict | None = None, **overrides) -> dict:
    components = {"land": 4_000_000, "construction": 3_500_000, "amenities": 500_000, "margin": 2_000_000}
    components.update(overrides)
    body: dict = {
        "project_id": project_id,
        "components": components,
        "note": "Quarterly costing",
    }
    if unit_id is not None:
        body["unit_id"] = unit_id
    response = client.post(
        "/api/v1/deal-desk/cost-sheets",
        json=body,
        headers=headers or env["admin_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cost_sheet_crud_generic_and_unit_specific(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    project_id = created["project"]["id"]
    unit_id = created["unit"]["id"]

    generic = _cost_sheet(client, env, project_id)
    assert generic["unit_id"] is None
    assert generic["total_paise"] == 10_000_000
    assert generic["cost_breakdown_json"]["margin"] == 2_000_000

    specific = _cost_sheet(client, env, project_id, unit_id=unit_id)
    assert specific["unit_id"] == unit_id
    assert specific["total_paise"] == 10_000_000

    # One generic sheet per project, one specific sheet per unit.
    duplicate = client.post(
        "/api/v1/deal-desk/cost-sheets",
        json={"project_id": project_id,
              "components": {"land": 1, "construction": 1, "amenities": 1, "margin": 1}},
        headers=env["admin_headers"],
    )
    assert duplicate.status_code == 409, duplicate.text
    duplicate_unit = client.post(
        "/api/v1/deal-desk/cost-sheets",
        json={"project_id": project_id, "unit_id": unit_id,
              "components": {"land": 1, "construction": 1, "amenities": 1, "margin": 1}},
        headers=env["admin_headers"],
    )
    assert duplicate_unit.status_code == 409, duplicate_unit.text

    patched = client.patch(
        f"/api/v1/deal-desk/cost-sheets/{specific['id']}",
        json={"components": {"land": 5_000_000, "construction": 3_000_000,
                             "amenities": 400_000, "margin": 1_600_000}},
        headers=env["manager_headers"],
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["total_paise"] == 10_000_000
    assert patched.json()["land_paise"] == 5_000_000

    fetched = client.get(
        f"/api/v1/deal-desk/cost-sheets/{generic['id']}", headers=env["sales_headers"]
    )
    assert fetched.status_code == 200, fetched.text

    listing = client.get(
        f"/api/v1/deal-desk/cost-sheets?project_id={project_id}",
        headers=env["sales_headers"],
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 2


def test_cost_sheet_rejects_negative_components(client: TestClient, env: dict) -> None:
    project = _active_project(client, env)
    response = client.post(
        "/api/v1/deal-desk/cost-sheets",
        json={"project_id": project["id"],
              "components": {"land": -1, "construction": 1, "amenities": 1, "margin": 1}},
        headers=env["admin_headers"],
    )
    assert response.status_code == 422, response.text


def test_cost_sheet_unit_from_other_project_is_404(client: TestClient, env: dict) -> None:
    first = _unit(client, env)
    other_project = _active_project(client, env)
    response = client.post(
        "/api/v1/deal-desk/cost-sheets",
        json={"project_id": other_project["id"], "unit_id": first["unit"]["id"],
              "components": {"land": 1, "construction": 1, "amenities": 1, "margin": 1}},
        headers=env["admin_headers"],
    )
    assert response.status_code == 404, response.text


def test_cost_sheet_cross_tenant_read_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    project = _active_project(client, env)
    sheet = _cost_sheet(client, env, project["id"])

    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"dd-{uuid4().hex[:8]}", name="Other Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    response = client.get(
        f"/api/v1/deal-desk/cost-sheets/{sheet['id']}",
        headers=auth_headers(other_admin.email),
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Quote band enforcement
# ---------------------------------------------------------------------------


def test_quote_within_two_percent_is_band_one(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "1.50")
    assert quote["band_number"] == 1
    assert quote["discount_paise"] == 150_000
    assert quote["net_price_paise"] == GROSS - 150_000


def test_quote_at_exact_band_boundaries(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    at_two = _quote(client, env, created["unit"]["id"], "2.00")
    assert at_two["band_number"] == 1
    just_over = _quote(client, env, created["unit"]["id"], "2.01")
    assert just_over["band_number"] == 2
    at_five = _quote(client, env, created["unit"]["id"], "5.00")
    assert at_five["band_number"] == 2


def test_quote_above_policy_limit_blocked_at_creation(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    response = client.post(
        "/api/v1/deal-desk/quotes",
        json={"unit_id": created["unit"]["id"], "gross_price_paise": GROSS,
              "discount_percent": "5.50"},
        headers=env["sales_headers"],
    )
    assert response.status_code == 400, response.text
    detail = response.json()["error"]["message"].lower()
    assert "blocked" in detail and "5" in detail

    # Nothing was persisted for the blocked quote.
    listing = client.get(
        f"/api/v1/deal-desk/quotes?unit_id={created['unit']['id']}",
        headers=env["sales_headers"],
    )
    assert listing.json()["total"] == 0


def test_quote_cross_tenant_unit_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"ddq-{uuid4().hex[:8]}", name="Quote Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    with env["factory"]() as session:
        project = Project(
            tenant_id=other_tenant.id, name="Foreign Towers", slug=f"ddp-{uuid4().hex[:6]}",
            location="Pune", status="ACTIVE", created_by=other_admin.id,
        )
        session.add(project)
        session.flush()
        unit = PropertyUnit(
            tenant_id=other_tenant.id, project_id=project.id,
            internal_code="DD-FOREIGN-1", status="AVAILABLE",
        )
        session.add(unit)
        session.commit()
        session.refresh(unit)
        foreign_unit_id = str(unit.id)

    response = client.post(
        "/api/v1/deal-desk/quotes",
        json={"unit_id": foreign_unit_id, "gross_price_paise": GROSS,
              "discount_percent": "2.00"},
        headers=env["sales_headers"],
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# DEAL_DISCOUNT approval flow end-to-end
# ---------------------------------------------------------------------------


def test_band_one_discount_approve_writes_unit_discount_atomically(
    client: TestClient, env: dict
) -> None:
    created = _unit(client, env)
    unit_id = created["unit"]["id"]
    quote = _quote(client, env, unit_id, "2.00")
    assert _unit_state(env["factory"], unit_id)[0] == DiscountStatus.NONE.value

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 201, body
    assert body["band_number"] == 1
    assert body["amount_paise"] == 200_000
    assert body["net_price_paise"] == GROSS - 200_000
    # Band 1 does not need a reason; the request still carries one.
    assert body["status"] == "PENDING"

    # The unit flag moves with the request; amount still unwritten.
    assert _unit_state(env["factory"], unit_id) == (DiscountStatus.PENDING.value, None)

    listing = client.get(
        "/api/v1/approvals/requests?request_type=DEAL_DISCOUNT",
        headers=env["admin_headers"],
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    approval = listing.json()["items"][0]
    assert approval["id"] == body["approval_request_id"]
    assert approval["request_type"] == "DEAL_DISCOUNT"
    assert approval["reference_type"] == "deal_quote"
    assert approval["reference_id"] == quote["id"]

    decided = _decide(client, env, body["approval_request_id"], "APPROVED")
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "APPROVED"

    assert _unit_state(env["factory"], unit_id) == (
        DiscountStatus.APPROVED.value, 200_000
    )

    # Final price: net of the quote is the consideration; the approved discount
    # is what leaves the gross price.
    refetched = client.get(
        f"/api/v1/deal-desk/quotes/{quote['id']}", headers=env["admin_headers"]
    )
    assert refetched.json()["net_price_paise"] == GROSS - 200_000
    assert refetched.json()["status"] == "REQUESTED"


def test_band_two_requires_reason_at_request_time(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "4.00")
    assert quote["band_number"] == 2

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 400, body
    assert "reason" in body["error"]["message"].lower()
    assert _unit_state(env["factory"], created["unit"]["id"])[0] == DiscountStatus.NONE.value

    status_code, body = _raise_discount(
        client, env, quote["id"], reason="Repeat customer, festive closure push."
    )
    assert status_code == 201, body

    decided = _decide(client, env, body["approval_request_id"], "APPROVED")
    assert decided.status_code == 200, decided.text
    assert _unit_state(env["factory"], created["unit"]["id"]) == (
        DiscountStatus.APPROVED.value, 400_000
    )


def test_matrix_tightening_blocks_a_previously_legal_quote(
    client: TestClient, env: dict
) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "2.00")

    response = client.put(
        "/api/v1/deal-desk/discount-matrix",
        json={"bands": [
            {"max_discount_percent": "1.00", "reason_required": False, "blocked": False},
            {"reason_required": True, "blocked": True},
        ]},
        headers=env["admin_headers"],
    )
    assert response.status_code == 200, response.text

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 400, body
    assert "blocked" in body["error"]["message"].lower()
    assert _unit_state(env["factory"], created["unit"]["id"])[0] == DiscountStatus.NONE.value


def test_rejection_sets_flag_but_never_amount(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "1.00")
    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 201, body

    decided = _decide(client, env, body["approval_request_id"], "REJECTED")
    assert decided.status_code == 200, decided.text
    assert _unit_state(env["factory"], created["unit"]["id"]) == (
        DiscountStatus.REJECTED.value, None
    )


def test_cancellation_reverts_flag_and_allows_re_raise(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "2.00")
    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 201, body

    cancelled = client.post(
        f"/api/v1/approvals/requests/{body['approval_request_id']}/cancel",
        headers=env["sales_headers"],
    )
    assert cancelled.status_code == 200, cancelled.text
    assert _unit_state(env["factory"], created["unit"]["id"])[0] == DiscountStatus.NONE.value
    assert _quote_status(env["factory"], quote["id"]) == "QUOTED"

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 201, body


def test_second_request_on_open_quote_conflicts(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "2.00")
    status_code, _ = _raise_discount(client, env, quote["id"])
    assert status_code == 201

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 409, body


def test_zero_percent_quote_has_nothing_to_approve(client: TestClient, env: dict) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "0")
    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 400, body


def test_legacy_discount_pending_unit_blocks_deal_desk_request(
    client: TestClient, env: dict
) -> None:
    created = _unit(client, env)
    unit_id = created["unit"]["id"]
    quote = _quote(client, env, unit_id, "1.00")

    legacy = client.post(
        f"/api/v1/inventory/units/{unit_id}/discount-request",
        json={"amount_paise": 100_000, "reason": "Legacy flow first."},
        headers=env["sales_headers"],
    )
    assert legacy.status_code == 201, legacy.text

    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 409, body


def test_sales_cannot_decide_and_cross_tenant_decide_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "2.00")
    status_code, body = _raise_discount(client, env, quote["id"])
    assert status_code == 201, body

    denied = _decide(
        client, env, body["approval_request_id"], "APPROVED", headers=env["sales_headers"]
    )
    assert denied.status_code == 403, denied.text

    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"ddd-{uuid4().hex[:8]}", name="Decide Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    stolen = _decide(
        client, env, body["approval_request_id"], "APPROVED",
        headers=auth_headers(other_admin.email),
    )
    assert stolen.status_code == 404, stolen.text
    assert _unit_state(env["factory"], created["unit"]["id"])[0] == DiscountStatus.PENDING.value


def test_quote_cross_tenant_read_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    created = _unit(client, env)
    quote = _quote(client, env, created["unit"]["id"], "2.00")

    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"ddr-{uuid4().hex[:8]}", name="Peek Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    response = client.get(
        f"/api/v1/deal-desk/quotes/{quote['id']}",
        headers=auth_headers(other_admin.email),
    )
    assert response.status_code == 404, response.text

    raise_attempt = client.post(
        f"/api/v1/deal-desk/quotes/{quote['id']}/discount-request",
        json={},
        headers=auth_headers(other_admin.email),
    )
    assert raise_attempt.status_code == 404, raise_attempt.text
