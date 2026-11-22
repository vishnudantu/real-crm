"""Tenant isolation, membership, unread and pagination for internal team chat."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.tenancy.models import Tenant
from app.modules.teamchat.models import TeamMessage
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


@pytest.fixture()
def second_tenant(test_session_factory: sessionmaker[Session]) -> Tenant:
    with test_session_factory() as session:
        tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other Realty")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        return tenant


@pytest.fixture()
def staff_headers(client: TestClient) -> Callable[[User], dict[str, str]]:
    def headers(user: User) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers


def _create_channel(
    client: TestClient, headers: dict[str, str], name: str = "leasing", members: list[UUID] | None = None
) -> dict:
    response = client.post(
        "/api/v1/teamchat/channels",
        headers=headers,
        json={"name": name, "topic": "Leasing staff", "member_ids": [str(value) for value in members or []]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _send(client: TestClient, headers: dict[str, str], channel_id: str, body: str, mentions: list[str] | None = None):
    return client.post(
        f"/api/v1/teamchat/channels/{channel_id}/messages",
        headers=headers, json={"body": body, "mentions": mentions or []},
    )


def test_staff_channel_flow_unread_read_join_and_direct_messages(
    client: TestClient, override_db: None, user_factory: Callable[..., User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, full_name="Admin One")
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, full_name="Sales Two")
    other = user_factory(role=RoleName.SALES_EXECUTIVE, full_name="Other Staff")
    admin_headers, sales_headers, other_headers = map(staff_headers, (admin, sales, other))
    channel = _create_channel(client, admin_headers, members=[sales.id])
    assert channel["member_count"] == 2
    assert {member["user"]["role"] for member in channel["members"]} == {"ADMIN", "SALES_EXECUTIVE"}
    assert other_headers

    sent = _send(client, admin_headers, channel["id"], "  Hello @Sales Two  ", [str(sales.id)])
    assert sent.status_code == 201, sent.text
    assert sent.json()["body"] == "Hello @Sales Two"
    assert sent.json()["author"]["full_name"] == "Admin One"
    assert sent.json()["mentions"] == [str(sales.id)]

    response = client.get("/api/v1/teamchat/unread", headers=sales_headers)
    assert response.status_code == 200
    assert response.json() == {"total": 1, "by_channel": {channel["id"]: 1}}
    assert client.get("/api/v1/teamchat/unread", headers=admin_headers).json()["total"] == 0
    channels = client.get("/api/v1/teamchat/channels", headers=sales_headers).json()
    assert channels["items"][0]["unread_count"] == 1

    read = client.post(f"/api/v1/teamchat/channels/{channel['id']}/read", headers=sales_headers)
    assert read.status_code == 200, read.text
    assert read.json()["last_read_at"]
    assert client.get("/api/v1/teamchat/unread", headers=sales_headers).json()["total"] == 0
    _send(client, admin_headers, channel["id"], "Another update")
    assert client.get("/api/v1/teamchat/unread", headers=sales_headers).json()["total"] == 1

    left = client.post(f"/api/v1/teamchat/channels/{channel['id']}/leave", headers=other_headers)
    assert left.status_code == 403
    joined = client.post(f"/api/v1/teamchat/channels/{channel['id']}/join", headers=other_headers)
    assert joined.status_code == 200, joined.text
    assert joined.json()["member_count"] == 3
    assert _send(client, other_headers, channel["id"], "Joined").status_code == 201
    assert client.post(f"/api/v1/teamchat/channels/{channel['id']}/leave", headers=other_headers).status_code == 204
    assert _send(client, other_headers, channel["id"], "No longer a member").status_code == 403

    direct = client.post("/api/v1/teamchat/direct", headers=admin_headers, json={"user_id": str(sales.id)})
    assert direct.status_code == 201, direct.text
    assert direct.json()["kind"] == "DIRECT"
    assert direct.json()["member_count"] == 2
    assert _send(client, sales_headers, direct.json()["id"], "Direct reply").status_code == 201
    duplicate = client.post("/api/v1/teamchat/direct", headers=sales_headers, json={"user_id": str(admin.id)})
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == direct.json()["id"]


def test_cross_tenant_access_members_mentions_and_buyers_are_rejected(
    client: TestClient, override_db: None, user_factory: Callable[..., User],
    second_tenant: Tenant, staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    outsider = user_factory(role=RoleName.ADMIN, tenant=second_tenant)
    buyer = user_factory(role=RoleName.BUYER)
    admin_headers, sales_headers, outsider_headers, buyer_headers = map(
        staff_headers, (admin, sales, outsider, buyer)
    )
    channel = _create_channel(client, admin_headers, members=[sales.id])
    for method, path in (
        ("get", f"/api/v1/teamchat/channels/{channel['id']}/messages"),
        ("post", f"/api/v1/teamchat/channels/{channel['id']}/read"),
        ("post", f"/api/v1/teamchat/channels/{channel['id']}/join"),
    ):
        response = getattr(client, method)(path, headers=outsider_headers)
        assert response.status_code == 404, response.text
    assert _send(client, outsider_headers, channel["id"], "Intrusion").status_code == 404
    assert _send(client, admin_headers, channel["id"], "Bad mention", [str(outsider.id)]).status_code == 400
    assert _send(client, admin_headers, channel["id"], "Buyer mention", [str(buyer.id)]).status_code == 400
    assert client.get("/api/v1/teamchat/channels", headers=buyer_headers).status_code == 403
    assert client.post("/api/v1/teamchat/channels", headers=buyer_headers, json={"name": "nope"}).status_code == 403


def test_non_member_send_validation_channel_name_and_staff_search(
    client: TestClient, override_db: None, user_factory: Callable[..., User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, full_name="Anita Admin")
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, full_name="Ravi Sales")
    user_factory(role=RoleName.BUYER, full_name="Buyer Hidden")
    admin_headers = staff_headers(admin)
    sales_headers = staff_headers(sales)
    channel = _create_channel(client, sales_headers, name="private-sales")
    assert _send(client, admin_headers, channel["id"], "Forbidden").status_code == 403
    duplicate = client.post(
        "/api/v1/teamchat/channels", headers=admin_headers, json={"name": "private-sales"}
    )
    assert duplicate.status_code == 409
    assert _send(client, sales_headers, channel["id"], " ").status_code == 422
    assert _send(client, sales_headers, channel["id"], "a" * 4001).status_code == 422
    assert _send(client, sales_headers, channel["id"], "a" * 4000).status_code == 201
    members = client.get("/api/v1/teamchat/members?search=admin", headers=sales_headers)
    assert members.status_code == 200, members.text
    assert [item["full_name"] for item in members.json()] == ["Anita Admin"]
    assert all(item["role"] != "BUYER" for item in client.get("/api/v1/teamchat/members", headers=sales_headers).json())


def test_message_cursor_pagination_is_newest_first_and_stable(
    client: TestClient, override_db: None, user_factory: Callable[..., User],
    staff_headers: Callable[[User], dict[str, str]], test_session_factory: sessionmaker[Session],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = staff_headers(admin)
    channel = _create_channel(client, headers)
    for index in range(5):
        assert _send(client, headers, channel["id"], f"message-{index}").status_code == 201
    first = client.get(f"/api/v1/teamchat/channels/{channel['id']}/messages?limit=2", headers=headers)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert [message["body"] for message in payload["items"]] == ["message-4", "message-3"]
    assert payload["next_before"]
    second = client.get(
        f"/api/v1/teamchat/channels/{channel['id']}/messages?limit=2&before={payload['next_before']}",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert [message["body"] for message in second.json()["items"]] == ["message-2", "message-1"]
    third = client.get(
        f"/api/v1/teamchat/channels/{channel['id']}/messages?limit=2&before={second.json()['next_before']}",
        headers=headers,
    )
    assert [message["body"] for message in third.json()["items"]] == ["message-0"]
    assert third.json()["next_before"] is None

    with test_session_factory() as session:
        message = session.query(TeamMessage).filter_by(body="message-2").one()
        session.delete(message)
        session.commit()
    assert client.get(
        f"/api/v1/teamchat/channels/{channel['id']}/messages?before=not-a-cursor", headers=headers
    ).status_code == 422
