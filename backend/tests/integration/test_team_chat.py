"""Integration route tests for the internal staff-to-staff team chat."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User

API = "/api/v1/team-chat"


@pytest.fixture()
def staff_headers(auth_headers: Callable[..., dict[str, str]]) -> Callable[[User], dict[str, str]]:
    return lambda user: auth_headers(user.email)


@pytest.fixture()
def staff(client: TestClient, override_db: None, user_factory: Callable[..., User]):
    admin = user_factory(role=RoleName.ADMIN, full_name="Admin Staff")
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, full_name="Sales Staff")
    other = user_factory(role=RoleName.SALES_EXECUTIVE, full_name="Other Staff")
    return admin, sales, other


def _create(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "leasing",
    is_private: bool = False,
    members: list[str] | None = None,
) -> dict:
    response = client.post(
        f"{API}/channels",
        headers=headers,
        json={
            "name": name,
            "description": "Internal leasing discussion",
            "is_private": is_private,
            "member_ids": members or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _post(
    client: TestClient, headers: dict[str, str], channel_id: str, body: str
):
    return client.post(
        f"{API}/channels/{channel_id}/messages", headers=headers, json={"body": body}
    )


def test_create_channel_auto_joins_creator_and_lists_members(
    client: TestClient,
    staff: tuple[User, User, User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, _, _ = staff
    headers = staff_headers(admin)
    channel = _create(client, headers)

    assert channel["is_private"] is False
    assert channel["member_count"] == 1
    assert channel["members"][0]["user_id"] == str(admin.id)
    assert channel["members"][0]["role"] == "ADMIN"

    members = client.get(f"{API}/channels/{channel['id']}/members", headers=headers)
    assert members.status_code == 200, members.text
    assert [member["user_id"] for member in members.json()] == [str(admin.id)]


def test_non_member_read_post_and_members_return_403(
    client: TestClient,
    staff: tuple[User, User, User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, sales, _ = staff
    admin_headers, sales_headers = staff_headers(admin), staff_headers(sales)
    channel = _create(client, admin_headers)
    message = _post(client, admin_headers, channel["id"], "Members only")
    assert message.status_code == 201, message.text

    assert client.get(
        f"{API}/channels/{channel['id']}/messages", headers=sales_headers
    ).status_code == 403
    assert client.get(
        f"{API}/channels/{channel['id']}/members", headers=sales_headers
    ).status_code == 403
    assert _post(client, sales_headers, channel["id"], "Intrusion").status_code == 403
    assert client.patch(
        f"{API}/messages/{message.json()['id']}",
        headers=sales_headers,
        json={"body": "Intrusion"},
    ).status_code == 403


def test_public_join_leave_and_private_channels(
    client: TestClient,
    staff: tuple[User, User, User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, sales, other = staff
    admin_headers, sales_headers, other_headers = map(
        staff_headers, (admin, sales, other)
    )
    channel = _create(client, admin_headers)
    private = _create(client, admin_headers, name="leadership", is_private=True)

    listed = client.get(f"{API}/channels", headers=sales_headers)
    assert listed.status_code == 200, listed.text
    assert [item["name"] for item in listed.json()["items"]] == ["leasing"]
    assert listed.json()["total"] == 1

    joined = client.post(f"{API}/channels/{channel['id']}/join", headers=sales_headers)
    assert joined.status_code == 200, joined.text
    assert joined.json()["member_count"] == 2
    assert client.post(
        f"{API}/channels/{private['id']}/join", headers=sales_headers
    ).status_code == 403
    assert client.post(
        f"{API}/channels/{channel['id']}/leave", headers=other_headers
    ).status_code == 403

    assert client.post(
        f"{API}/channels/{channel['id']}/leave", headers=sales_headers
    ).status_code == 204
    assert _post(client, sales_headers, channel["id"], "After leaving").status_code == 403


def test_buyer_role_gets_403(
    client: TestClient,
    staff: tuple[User, User, User],
    user_factory: Callable[..., User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, _, _ = staff
    buyer = user_factory(role=RoleName.BUYER)
    buyer_headers = staff_headers(buyer)
    channel = _create(client, staff_headers(admin))

    assert client.get(f"{API}/channels", headers=buyer_headers).status_code == 403
    assert client.post(
        f"{API}/channels", headers=buyer_headers, json={"name": "buyer"}
    ).status_code == 403
    assert client.get(
        f"{API}/channels/{channel['id']}/messages", headers=buyer_headers
    ).status_code == 403
    assert _post(client, buyer_headers, channel["id"], "Not staff").status_code == 403


def test_cross_tenant_channel_and_message_access_returns_404(
    client: TestClient,
    staff: tuple[User, User, User],
    user_factory: Callable[..., User],
    staff_headers: Callable[[User], dict[str, str]],
    test_session_factory: sessionmaker[Session],
) -> None:
    admin, _, _ = staff
    with test_session_factory() as session:
        tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other Realty")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
    outsider = user_factory(role=RoleName.ADMIN, tenant=tenant)
    outsider_headers = staff_headers(outsider)
    channel = _create(client, staff_headers(admin))
    message = _post(client, staff_headers(admin), channel["id"], "Tenant secret")

    for method, path, body in (
        ("get", f"{API}/channels/{channel['id']}/messages", None),
        ("get", f"{API}/channels/{channel['id']}/members", None),
        ("post", f"{API}/channels/{channel['id']}/join", None),
        ("post", f"{API}/channels/{channel['id']}/leave", None),
        ("post", f"{API}/channels/{channel['id']}/messages", {"body": "Intrusion"}),
        ("patch", f"{API}/messages/{message.json()['id']}", {"body": "Intrusion"}),
    ):
        request = getattr(client, method)
        response = (
            request(path, headers=outsider_headers)
            if body is None
            else request(path, headers=outsider_headers, json=body)
        )
        assert response.status_code == 404, response.text


def test_message_pagination_is_newest_first(
    client: TestClient,
    staff: tuple[User, User, User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, _, _ = staff
    headers = staff_headers(admin)
    channel = _create(client, headers)
    for index in range(5):
        assert _post(client, headers, channel["id"], f"message-{index}").status_code == 201

    first = client.get(
        f"{API}/channels/{channel['id']}/messages?page=1&page_size=2", headers=headers
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["total"] == 5
    assert payload["pages"] == 3
    assert [message["body"] for message in payload["items"]] == [
        "message-4", "message-3"
    ]

    second = client.get(
        f"{API}/channels/{channel['id']}/messages?page=2&page_size=2", headers=headers
    )
    assert second.status_code == 200, second.text
    assert [message["body"] for message in second.json()["items"]] == [
        "message-2", "message-1"
    ]
    third = client.get(
        f"{API}/channels/{channel['id']}/messages?page=3&page_size=2", headers=headers
    )
    assert [message["body"] for message in third.json()["items"]] == ["message-0"]


def test_edit_sets_edited_at_and_only_sender_can_edit(
    client: TestClient,
    staff: tuple[User, User, User],
    staff_headers: Callable[[User], dict[str, str]],
) -> None:
    admin, sales, other = staff
    admin_headers, sales_headers, other_headers = map(
        staff_headers, (admin, sales, other)
    )
    channel = _create(client, admin_headers, members=[str(sales.id), str(other.id)])
    sent = _post(client, admin_headers, channel["id"], "Original")
    assert sent.status_code == 201, sent.text
    assert sent.json()["edited_at"] is None

    denied = client.patch(
        f"{API}/messages/{sent.json()['id']}",
        headers=sales_headers,
        json={"body": "Not yours"},
    )
    assert denied.status_code == 403, denied.text

    edited = client.patch(
        f"{API}/messages/{sent.json()['id']}",
        headers=admin_headers,
        json={"body": "Corrected"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "Corrected"
    assert edited.json()["edited_at"] is not None
    assert edited.json()["updated_at"] >= sent.json()["updated_at"]
