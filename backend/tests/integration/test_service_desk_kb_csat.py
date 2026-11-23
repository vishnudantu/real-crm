"""Integration tests for the service-desk knowledge base and CSAT slice.

Covers: staff KB authoring (draft/create/update/publish + search), the
buyer help center (tenant + PUBLISHED scoping, 404s that never disclose
drafts or other tenants), CSAT (survey opened on close, buyer-owned rating,
stats rollups) and agent suggestions. Buyer identity follows the
/buyer-docs/mine rules: the Contact is resolved server-side and every miss
answers 404, never 403.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.customers.models import (
    Contact,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    VerificationState,
)
from app.modules.service_desk.models import (
    KbArticle,
    KbArticleStatus,
    Ticket,
    TicketSatisfaction,
    TicketStatus,
)
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName

ADMIN_BASE = "/api/v1/service-desk"
KB = f"{ADMIN_BASE}/kb/articles"
HELP = f"{ADMIN_BASE}/help/articles"
TICKETS = f"{ADMIN_BASE}/tickets"
BUYER = f"{ADMIN_BASE}/mine/tickets"


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, email=f"sales-{uuid4().hex[:6]}@ex.com")
    return {
        "factory": test_session_factory,
        "tenant_id": admin.tenant_id,
        "admin_headers": auth_headers(admin.email),
        "sales_headers": auth_headers(sales.email),
        "admin_email": admin.email,
        "user_factory": user_factory,
        "auth_headers": auth_headers,
    }


def _contact_for(session: Session, *, tenant_id: UUID, email: str, name: str = "Portal Buyer") -> Contact:
    contact = Contact(
        tenant_id=tenant_id,
        canonical_key=f"uuid:{uuid4()}",
        display_name=name,
        status=ContactStatus.ACTIVE.value,
    )
    session.add(contact)
    session.flush()
    session.add(
        ContactMethod(
            tenant_id=tenant_id,
            contact_id=contact.id,
            kind=ContactMethodKind.EMAIL.value,
            value=email,
            normalized_value=email.lower(),
            verification_state=VerificationState.UNVERIFIED.value,
            provenance={},
            is_primary=True,
        )
    )
    session.commit()
    session.refresh(contact)
    return contact


def _buyer_env(env: dict) -> dict:
    """One buyer account + resolved contact, already authenticated."""
    email = f"csat-buyer-{uuid4().hex[:8]}@example.com"
    buyer = env["user_factory"](role=RoleName.BUYER, email=email)
    headers = env["auth_headers"](buyer.email)
    with env["factory"]() as session:
        contact = _contact_for(session, tenant_id=buyer.tenant_id, email=email)
    return {"headers": headers, "buyer": buyer, "contact_id": contact.id}


def _create_ticket(client: TestClient, headers: dict, subject: str, **overrides) -> dict:
    payload = {"subject": subject, "description": "Details", **overrides}
    response = client.post(TICKETS, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_article(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {
        "title": "How to track your loan status",
        "body_markdown": "The bank shares updates every Monday.",
        "category": "Loans",
        **overrides,
    }
    response = client.post(KB, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _close(client: TestClient, headers: dict, ticket_id: str) -> None:
    resolved = client.patch(
        f"{TICKETS}/{ticket_id}/status", json={"status": "RESOLVED"}, headers=headers
    )
    assert resolved.status_code == 200, resolved.text
    closed = client.patch(
        f"{TICKETS}/{ticket_id}/status", json={"status": "CLOSED"}, headers=headers
    )
    assert closed.status_code == 200, closed.text


class TestKbAuthoring:
    def test_create_defaults_to_draft_with_derived_slug(self, client: TestClient, env) -> None:
        article = _create_article(client, env["admin_headers"])
        assert article["status"] == "DRAFT"
        assert article["slug"] == "how-to-track-your-loan-status"
        assert article["published_at"] is None

    def test_explicit_slug_kept_and_collisions_suffixed(self, client: TestClient, env) -> None:
        first = _create_article(client, env["admin_headers"], slug="loan-help")
        second = _create_article(client, env["admin_headers"], slug="loan-help")
        assert first["slug"] == "loan-help"
        assert second["slug"] == "loan-help-2"

    def test_invalid_slug_shape_422(self, client: TestClient, env) -> None:
        response = client.post(
            KB,
            json={"title": "X", "body_markdown": "Y", "category": "Z", "slug": "Bad Slug!"},
            headers=env["admin_headers"],
        )
        assert response.status_code == 422

    def test_update_keeps_slug_and_edits_fields(self, client: TestClient, env) -> None:
        article = _create_article(client, env["admin_headers"])
        response = client.patch(
            f"{KB}/{article['id']}",
            json={"title": "Updated title", "category": "Finance"},
            headers=env["admin_headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["title"] == "Updated title"
        assert body["category"] == "Finance"
        assert body["slug"] == article["slug"]

    def test_publish_sets_status_and_timestamp_and_is_idempotent(
        self, client: TestClient, env
    ) -> None:
        article = _create_article(client, env["admin_headers"])
        published = client.post(f"{KB}/{article['id']}/publish", headers=env["admin_headers"])
        assert published.status_code == 200, published.text
        first = published.json()
        assert first["status"] == "PUBLISHED"
        assert first["published_at"] is not None
        again = client.post(f"{KB}/{article['id']}/publish", headers=env["admin_headers"]).json()
        assert again["published_at"] == first["published_at"]

    def test_unknown_article_update_publish_404(self, client: TestClient, env) -> None:
        ghost = str(uuid4())
        assert client.patch(
            f"{KB}/{ghost}", json={"title": "x"}, headers=env["admin_headers"]
        ).status_code == 404
        assert client.post(f"{KB}/{ghost}/publish", headers=env["admin_headers"]).status_code == 404

    def test_staff_list_filters_status_category_and_search(
        self, client: TestClient, env
    ) -> None:
        draft = _create_article(client, env["admin_headers"], title="Refund policy draft")
        published = _create_article(client, env["admin_headers"], title="Possession letter steps")
        client.post(f"{KB}/{published['id']}/publish", headers=env["admin_headers"])

        by_status = client.get(
            f"{KB}?status=PUBLISHED", headers=env["admin_headers"]
        ).json()
        assert [a["id"] for a in by_status["items"]] == [published["id"]]

        by_category = client.get(
            f"{KB}?category=Loans&search=possession", headers=env["admin_headers"]
        ).json()
        assert [a["id"] for a in by_category["items"]] == [published["id"]]

        drafts_only = client.get(
            f"{KB}?status=DRAFT", headers=env["admin_headers"]
        ).json()
        assert [a["id"] for a in drafts_only["items"]] == [draft["id"]]

    def test_search_is_case_insensitive_and_over_body(self, client: TestClient, env) -> None:
        _create_article(client, env["admin_headers"], title="Site visits", body_markdown="Bring your PASSPORT at the gate.")
        hits = client.get(f"{KB}?search=passport", headers=env["admin_headers"]).json()
        assert hits["total"] == 1

    def test_search_escapes_like_wildcards(self, client: TestClient, env) -> None:
        _create_article(client, env["admin_headers"], title="Half off 50% deal")
        literal = client.get(f"{KB}?search=50%25", headers=env["admin_headers"]).json()
        assert literal["total"] == 1
        # A raw % as a wildcard would match anything; it must match literally.
        other = client.get(f"{KB}?search=%25", headers=env["admin_headers"]).json()
        assert other["total"] == 1

    def test_buyer_cannot_author(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        response = client.post(
            KB,
            json={"title": "sneaky", "body_markdown": "x", "category": "y"},
            headers=portal["headers"],
        )
        assert response.status_code == 403


class TestHelpCenter:
    def test_buyer_sees_only_published_and_searches(self, client: TestClient, env) -> None:
        draft = _create_article(client, env["admin_headers"], title="Internal draft plan")
        published = _create_article(client, env["admin_headers"], title="Payment gateway guide")
        client.post(f"{KB}/{published['id']}/publish", headers=env["admin_headers"])

        portal = _buyer_env(env)
        listing = client.get(HELP, headers=portal["headers"]).json()
        assert [a["id"] for a in listing["items"]] == [published["id"]]

        read_published = client.get(f"{HELP}/{published['id']}", headers=portal["headers"])
        assert read_published.status_code == 200

        # Drafts answer 404 like missing articles — existence never disclosed.
        assert client.get(f"{HELP}/{draft['id']}", headers=portal["headers"]).status_code == 404
        assert client.get(f"{HELP}/{uuid4()}", headers=portal["headers"]).status_code == 404

        searched = client.get(f"{HELP}?search=gateway", headers=portal["headers"]).json()
        assert searched["total"] == 1
        missed = client.get(f"{HELP}?search=internal", headers=portal["headers"]).json()
        assert missed["total"] == 0

    def test_cross_tenant_help_reads_404(self, client: TestClient, env) -> None:
        article = _create_article(client, env["admin_headers"])
        client.post(f"{KB}/{article['id']}/publish", headers=env["admin_headers"])

        other_tenant = Tenant(slug=f"kbother-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other = env["user_factory"](
                role=RoleName.ADMIN, tenant=other_tenant,
                email=f"kb-other-admin-{uuid4().hex[:6]}@ex.com",
            )
        other_headers = env["auth_headers"](other.email)
        assert client.get(f"{HELP}/{article['id']}", headers=other_headers).status_code == 404
        listing = client.get(HELP, headers=other_headers).json()
        assert listing["total"] == 0

    def test_staff_can_read_help_center(self, client: TestClient, env) -> None:
        article = _create_article(client, env["admin_headers"])
        client.post(f"{KB}/{article['id']}/publish", headers=env["admin_headers"])
        response = client.get(f"{HELP}/{article['id']}", headers=env["sales_headers"])
        assert response.status_code == 200


class TestCsatCloseAndRating:
    def test_closing_opens_one_survey(self, client: TestClient, env) -> None:
        ticket = _create_ticket(client, env["admin_headers"], subject="Leaking pipe")
        _close(client, env["admin_headers"], ticket["id"])
        detail = client.get(f"{TICKETS}/{ticket['id']}", headers=env["admin_headers"]).json()
        assert detail["status"] == "CLOSED"
        assert detail["closed_at"] is not None
        assert detail["satisfaction"] is not None
        assert detail["satisfaction"]["rating"] is None
        with env["factory"]() as session:
            rows = session.query(TicketSatisfaction).filter_by(ticket_id=UUID(ticket["id"])).all()
            assert len(rows) == 1

    def test_buyer_rates_own_closed_ticket_then_revises(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Payment issue", contact_id=str(portal["contact_id"])
        )
        _close(client, env["admin_headers"], ticket["id"])

        submitted = client.put(
            f"{BUYER}/{ticket['id']}/satisfaction",
            json={"rating": 4, "feedback": "Fixed quickly"},
            headers=portal["headers"],
        )
        assert submitted.status_code == 200, submitted.text
        body = submitted.json()
        assert body["rating"] == 4
        assert body["feedback"] == "Fixed quickly"
        assert body["responded_at"] is not None

        revised = client.put(
            f"{BUYER}/{ticket['id']}/satisfaction",
            json={"rating": 5, "feedback": ""},
            headers=portal["headers"],
        ).json()
        assert revised["rating"] == 5
        assert revised["feedback"] is None
        read = client.get(f"{BUYER}/{ticket['id']}/satisfaction", headers=portal["headers"]).json()
        assert read["rating"] == 5
        with env["factory"]() as session:
            rows = session.query(TicketSatisfaction).filter_by(ticket_id=UUID(ticket["id"])).all()
            assert len(rows) == 1  # revise-in-place, never stacks

    def test_rating_requires_closed_ticket_409(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Open question", contact_id=str(portal["contact_id"])
        )
        response = client.put(
            f"{BUYER}/{ticket['id']}/satisfaction",
            json={"rating": 5},
            headers=portal["headers"],
        )
        assert response.status_code == 409

    def test_legacy_closed_ticket_without_survey_still_accepts_rating(
        self, client: TestClient, env
    ) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Old close", contact_id=str(portal["contact_id"])
        )
        with env["factory"]() as session:
            row = session.get(Ticket, UUID(ticket["id"]))
            row.status = TicketStatus.CLOSED.value
            session.commit()
        response = client.put(
            f"{BUYER}/{ticket['id']}/satisfaction", json={"rating": 3}, headers=portal["headers"]
        )
        assert response.status_code == 200, response.text
        assert response.json()["rating"] == 3

    def test_buyer_cannot_rate_foreign_or_unlinked_ticket_404(
        self, client: TestClient, env
    ) -> None:
        portal = _buyer_env(env)
        other_contact = None
        with env["factory"]() as session:
            other_contact = _contact_for(
                session, tenant_id=env["tenant_id"],
                email=f"other-owner-{uuid4().hex[:8]}@ex.com", name="Other Owner",
            )
        unlinked = _create_ticket(client, env["admin_headers"], "No contact at all")
        foreign = _create_ticket(
            client, env["admin_headers"], "Other buyer", contact_id=str(other_contact.id)
        )
        for ticket_id in (unlinked["id"], foreign["id"]):
            _close(client, env["admin_headers"], ticket_id)
            response = client.put(
                f"{BUYER}/{ticket_id}/satisfaction",
                json={"rating": 1},
                headers=portal["headers"],
            )
            assert response.status_code == 404
            assert client.get(
                f"{BUYER}/{ticket_id}/satisfaction", headers=portal["headers"]
            ).status_code == 404

    def test_buyer_without_contact_resolves_to_404(self, client: TestClient, env) -> None:
        orphan_email = f"orphan-{uuid4().hex[:8]}@example.com"
        buyer = env["user_factory"](role=RoleName.BUYER, email=orphan_email)
        headers = env["auth_headers"](buyer.email)
        ticket = _create_ticket(client, env["admin_headers"], "No contact link")
        _close(client, env["admin_headers"], ticket["id"])
        # Unresolvable identity answers 404 on every /mine surface — including
        # the queue — exactly like /buyer-docs/mine, so no partial data leaks.
        assert client.get(BUYER, headers=headers).status_code == 404
        assert client.put(
            f"{BUYER}/{ticket['id']}/satisfaction", json={"rating": 5}, headers=headers
        ).status_code == 404
        assert client.get(f"{BUYER}/{ticket['id']}", headers=headers).status_code == 404

    def test_cross_tenant_buyer_rating_404(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Mine", contact_id=str(portal["contact_id"])
        )
        _close(client, env["admin_headers"], ticket["id"])
        other_tenant = Tenant(slug=f"csatother-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            email = f"other-buyer-{uuid4().hex[:8]}@ex.com"
            other = env["user_factory"](role=RoleName.BUYER, tenant=other_tenant, email=email)
            _contact_for(session, tenant_id=other_tenant.id, email=email)
        other_headers = env["auth_headers"](other.email)
        assert client.put(
            f"{BUYER}/{ticket['id']}/satisfaction", json={"rating": 5}, headers=other_headers
        ).status_code == 404

    def test_rating_bounds_422(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Bounded", contact_id=str(portal["contact_id"])
        )
        _close(client, env["admin_headers"], ticket["id"])
        for rating in (0, 6):
            response = client.put(
                f"{BUYER}/{ticket['id']}/satisfaction",
                json={"rating": rating},
                headers=portal["headers"],
            )
            assert response.status_code == 422

    def test_read_satisfaction_404_when_no_survey(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Still open", contact_id=str(portal["contact_id"])
        )
        assert client.get(
            f"{BUYER}/{ticket['id']}/satisfaction", headers=portal["headers"]
        ).status_code == 404


class TestBuyerTicketSurface:
    def test_mine_lists_only_own_tickets_with_public_comments(
        self, client: TestClient, env
    ) -> None:
        portal = _buyer_env(env)
        mine = _create_ticket(
            client, env["admin_headers"], "My leak", contact_id=str(portal["contact_id"])
        )
        _create_ticket(client, env["admin_headers"], "Their leak")
        client.post(
            f"{TICKETS}/{mine['id']}/comments",
            json={"body": "Here is your update", "is_internal": False},
            headers=env["admin_headers"],
        )
        client.post(
            f"{TICKETS}/{mine['id']}/comments",
            json={"body": "Secret vendor info", "is_internal": True},
            headers=env["admin_headers"],
        )

        listing = client.get(BUYER, headers=portal["headers"]).json()
        assert listing["total"] == 1 and listing["items"][0]["id"] == mine["id"]

        detail = client.get(f"{BUYER}/{mine['id']}", headers=portal["headers"]).json()
        assert [c["body"] for c in detail["comments"]] == ["Here is your update"]
        assert detail["satisfaction"] is None

    def test_mine_detail_cross_tenant_404(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        ticket = _create_ticket(
            client, env["admin_headers"], "Home", contact_id=str(portal["contact_id"])
        )
        other_tenant = Tenant(slug=f"mineother-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            email = f"other-buyer2-{uuid4().hex[:8]}@ex.com"
            other = env["user_factory"](role=RoleName.BUYER, tenant=other_tenant, email=email)
            _contact_for(session, tenant_id=other_tenant.id, email=email)
        other_headers = env["auth_headers"](other.email)
        assert client.get(f"{BUYER}/{ticket['id']}", headers=other_headers).status_code == 404


class TestCsatStats:
    def _seed_rated_closes(self, client: TestClient, env, portal, ratings) -> None:
        for index, rating in enumerate(ratings):
            ticket = _create_ticket(
                client, env["admin_headers"], f"Closed {index}",
                contact_id=str(portal["contact_id"]),
            )
            _close(client, env["admin_headers"], ticket["id"])
            response = client.put(
                f"{BUYER}/{ticket['id']}/satisfaction",
                json={"rating": rating, "feedback": f"note {index}"},
                headers=portal["headers"],
            )
            assert response.status_code == 200, response.text

    def test_stats_rollup(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        self._seed_rated_closes(client, env, portal, [5, 4, 2])
        open_ticket = _create_ticket(client, env["admin_headers"], "Still open")

        stats = client.get(f"{ADMIN_BASE}/stats/csat?period=30d", headers=env["admin_headers"])
        assert stats.status_code == 200, stats.text
        body = stats.json()
        assert body["surveys"] == 3 and body["rated"] == 3
        assert body["average_rating"] == pytest.approx(3.67)
        assert body["response_rate"] == pytest.approx(1.0)
        assert body["rating_histogram"] == {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1}
        assert body["unresolved_tickets"] == 1
        period = body["periods"][-1]
        assert period["surveys"] == 3 and period["average_rating"] == pytest.approx(3.67)
        month = datetime.now(UTC).strftime("%Y-%m")
        trend = {point["period"]: point for point in body["ticket_trends"]}[month]
        assert trend["opened"] == 4 and trend["closed"] == 3
        assert open_ticket["id"]

    def test_stats_include_unanswered_surveys_in_denominator(
        self, client: TestClient, env
    ) -> None:
        portal = _buyer_env(env)
        self._seed_rated_closes(client, env, portal, [4])
        unanswered = _create_ticket(
            client, env["admin_headers"], "No rating yet", contact_id=str(portal["contact_id"])
        )
        _close(client, env["admin_headers"], unanswered["id"])
        body = client.get(
            f"{ADMIN_BASE}/stats/csat?period=30d", headers=env["admin_headers"]
        ).json()
        assert body["surveys"] == 2 and body["rated"] == 1
        assert body["response_rate"] == pytest.approx(0.5)
        assert body["average_rating"] == pytest.approx(4.0)

    def test_stats_empty_state(self, client: TestClient, env) -> None:
        body = client.get(
            f"{ADMIN_BASE}/stats/csat", headers=env["admin_headers"]
        ).json()
        assert body["surveys"] == 0 and body["rated"] == 0
        assert body["average_rating"] is None and body["response_rate"] is None
        assert body["periods"] == [] and body["ticket_trends"] == []

    def test_stats_invalid_period_400(self, client: TestClient, env) -> None:
        response = client.get(
            f"{ADMIN_BASE}/stats/csat?period=7d", headers=env["admin_headers"]
        )
        assert response.status_code == 400

    def test_stats_are_tenant_scoped(self, client: TestClient, env) -> None:
        portal = _buyer_env(env)
        self._seed_rated_closes(client, env, portal, [5])
        other_tenant = Tenant(slug=f"statother-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other = env["user_factory"](
                role=RoleName.ADMIN, tenant=other_tenant,
                email=f"stats-other-{uuid4().hex[:6]}@ex.com",
            )
        other_headers = env["auth_headers"](other.email)
        body = client.get(
            f"{ADMIN_BASE}/stats/csat?period=30d", headers=other_headers
        ).json()
        assert body["surveys"] == 0 and body["unresolved_tickets"] == 0


class TestAgentSuggestions:
    def test_top_three_published_only_ranked_by_title_match(self, client: TestClient, env) -> None:
        ticket = _create_ticket(client, env["admin_headers"], "Payment gateway keeps failing")
        # Scores: 4 (payment+gateway in title), 2 (payment in title), 1 (payment once in body).
        top = _create_article(client, env["admin_headers"], title="Payment gateway errors")
        middle = _create_article(client, env["admin_headers"], title="Payment receipt download")
        low = _create_article(
            client, env["admin_headers"], title="Loan money talk",
            body_markdown="The payment team answers tickets daily.",
        )
        draft = _create_article(client, env["admin_headers"], title="Payment gateway internal")
        for article in (top, middle, low):
            client.post(f"{KB}/{article['id']}/publish", headers=env["admin_headers"])

        response = client.get(f"{TICKETS}/{ticket['id']}/suggestions", headers=env["sales_headers"])
        assert response.status_code == 200, response.text
        suggestions = response.json()
        assert [s["article_id"] for s in suggestions] == [top["id"], middle["id"], low["id"]]
        assert draft["id"] not in [s["article_id"] for s in suggestions]
        assert [s["score"] for s in suggestions] == [4, 2, 1]

    def test_no_matching_articles_returns_empty_list(self, client: TestClient, env) -> None:
        ticket = _create_ticket(client, env["admin_headers"], "Zebra migration schedule")
        response = client.get(
            f"{TICKETS}/{ticket['id']}/suggestions", headers=env["admin_headers"]
        )
        assert response.status_code == 200 and response.json() == []

    def test_suggestions_on_foreign_ticket_404(self, client: TestClient, env) -> None:
        other_tenant = Tenant(slug=f"sugother-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other = env["user_factory"](
                role=RoleName.ADMIN, tenant=other_tenant,
                email=f"sug-other-{uuid4().hex[:6]}@ex.com",
            )
        ticket = _create_ticket(client, env["admin_headers"], "Anything at all")
        response = client.get(
            f"{TICKETS}/{ticket['id']}/suggestions",
            headers=env["auth_headers"](other.email),
        )
        assert response.status_code == 404
