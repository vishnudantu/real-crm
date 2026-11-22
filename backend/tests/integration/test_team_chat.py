"""Swarm-specific teamchat behaviors on the canonical schema.

Covers the behaviors introduced by the parallel team-chat work that the
canonical module adopted: private channels (join 403), author-only message
editing (with edited_at), and the /team-chat alias prefix. The canonical
test_teamchat.py covers membership, unread cursors, mentions, DMs, and
pagination.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


@pytest.fixture()
def staff_headers(client: TestClient) -> Callable[[User], dict[str, str]]:
    def headers(user: User) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers


def _make_staff(test_session_factory, user_factory, email_prefix: str, role=RoleName.ADMIN):
    user = user_factory(role=role, email=f"{email_prefix}-{uuid4().hex[:6]}@tc.example")
    return user


def _create_channel(client, headers, *, name=None, is_private=False, members=None) -> dict:
    response = client.post(
        "/api/v1/teamchat/channels",
        headers=headers,
        json={
            "name": name or f"private-{uuid4().hex[:6]}",
            "topic": "Swarm behavior tests",
            "is_private": is_private,
            "member_ids": [str(getattr(member, "id", member)) for member in members or []],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_private_channel_hides_from_non_members_and_blocks_join(
    client: TestClient, override_db: None, test_session_factory, user_factory, staff_headers
) -> None:
    admin = _make_staff(test_session_factory, user_factory, "admin")
    sales = _make_staff(test_session_factory, user_factory, "sales", RoleName.SALES_EXECUTIVE)
    outsider = _make_staff(test_session_factory, user_factory, "out", RoleName.SALES_EXECUTIVE)
    admin_headers = staff_headers(admin)
    sales_headers = staff_headers(sales)
    outsider_headers = staff_headers(outsider)

    channel = _create_channel(client, admin_headers, is_private=True, members=[sales])

    # Listed for a member, hidden from a non-member.
    admin_names = {c["name"] for c in client.get("/api/v1/teamchat/channels", headers=admin_headers).json()["items"]}
    out_names = {c["name"] for c in client.get("/api/v1/teamchat/channels", headers=outsider_headers).json()["items"]}
    assert channel["name"] in admin_names
    assert channel["name"] not in out_names

    # Private join is forbidden even for staff.
    assert client.post(f"/api/v1/teamchat/channels/{channel['id']}/join", headers=outsider_headers).status_code == 403
    # Member reads fine; non-member read/post are 404 (hidden) or 403.
    assert client.get(f"/api/v1/teamchat/channels/{channel['id']}/messages", headers=sales_headers).status_code == 200
    assert client.get(f"/api/v1/teamchat/channels/{channel['id']}/messages", headers=outsider_headers).status_code in (403, 404)

    # is_private is exposed on the response.
    assert channel["is_private"] is True


def test_public_channel_join_then_leave(
    client: TestClient, override_db: None, test_session_factory, user_factory, staff_headers
) -> None:
    admin = _make_staff(test_session_factory, user_factory, "admin2")
    sales = _make_staff(test_session_factory, user_factory, "sales2", RoleName.SALES_EXECUTIVE)
    admin_headers = staff_headers(admin)
    sales_headers = staff_headers(sales)

    channel = _create_channel(client, admin_headers, is_private=False)
    joined = client.post(f"/api/v1/teamchat/channels/{channel['id']}/join", headers=sales_headers)
    assert joined.status_code == 200
    left = client.post(f"/api/v1/teamchat/channels/{channel['id']}/leave", headers=sales_headers)
    assert left.status_code == 204
    # After leaving, posting is rejected.
    denied = client.post(
        f"/api/v1/teamchat/channels/{channel['id']}/messages",
        headers=sales_headers, json={"body": "hello again"},
    )
    assert denied.status_code == 403


def test_author_only_edit_sets_edited_at(
    client: TestClient, override_db: None, test_session_factory, user_factory, staff_headers
) -> None:
    admin = _make_staff(test_session_factory, user_factory, "admin3")
    sales = _make_staff(test_session_factory, user_factory, "sales3", RoleName.SALES_EXECUTIVE)
    admin_headers = staff_headers(admin)
    sales_headers = staff_headers(sales)

    channel = _create_channel(client, admin_headers, members=[sales])
    sent = _post_message(client, admin_headers, channel["id"], "original text")
    message_id = sent["id"]

    # A non-author member cannot edit.
    forbidden = client.patch(
        f"/api/v1/teamchat/messages/{message_id}",
        headers=sales_headers, json={"body": "hijacked"},
    )
    assert forbidden.status_code == 403

    # The author edits; edited_at is stamped.
    edited = client.patch(
        f"/api/v1/teamchat/messages/{message_id}",
        headers=admin_headers, json={"body": "corrected text"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "corrected text"
    assert edited.json()["edited_at"] is not None

    # The channel-scoped alias path works too.
    edited2 = client.patch(
        f"/api/v1/teamchat/channels/{channel['id']}/messages/{message_id}",
        headers=admin_headers, json={"body": "corrected twice"},
    )
    assert edited2.status_code == 200 and edited2.json()["body"] == "corrected twice"

    # Empty body is rejected.
    empty = client.patch(
        f"/api/v1/teamchat/messages/{message_id}", headers=admin_headers, json={"body": "  "}
    )
    assert empty.status_code in (403, 422)


def _post_message(client, headers, channel_id: str, body: str) -> dict:
    response = client.post(
        f"/api/v1/teamchat/channels/{channel_id}/messages",
        headers=headers, json={"body": body},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_team_chat_alias_prefix_serves_same_handlers(
    client: TestClient, override_db: None, test_session_factory, user_factory, staff_headers
) -> None:
    admin = _make_staff(test_session_factory, user_factory, "admin4")
    admin_headers = staff_headers(admin)

    # Create via the hyphenated alias; read back via the canonical prefix.
    created = client.post(
        "/api/v1/team-chat/channels",
        headers=admin_headers,
        json={"name": f"alias-{uuid4().hex[:6]}", "description": "alias topic", "is_private": False},
    )
    assert created.status_code == 201, created.text
    assert created.json()["topic"] == "alias topic"

    sent = client.post(
        f"/api/v1/team-chat/channels/{created.json()['id']}/messages",
        headers=admin_headers, json={"body": "via alias"},
    )
    assert sent.status_code == 201

    listed = client.get("/api/v1/teamchat/channels", headers=admin_headers).json()
    assert any(c["id"] == created.json()["id"] for c in listed["items"])


def test_teamchat_migration_is_idempotent_on_existing_tables(
    test_session_factory, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The d6e7f8a9b0c1 migration must not recreate pre-existing tables."""
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from pathlib import Path

    migration_path = (
        Path(__file__).parents[2]
        / "alembic" / "versions"
        / "2026_11_22_2200-d6e7f8a9b0c1_internal_staff_team_chat.py"
    )
    spec = importlib.util.spec_from_file_location("tc_migration_check", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False})
    connection = engine.connect()
    try:
        # Pre-existing canonical team_channels without is_private.
        connection.execute(sa.text(
            "CREATE TABLE team_channels (id CHAR(32) PRIMARY KEY, name VARCHAR(80) NOT NULL,"
            " topic VARCHAR(500), kind VARCHAR(16) NOT NULL DEFAULT 'CHANNEL',"
            " is_general BOOLEAN NOT NULL DEFAULT 0, created_by CHAR(32),"
            " created_at DATETIME NOT NULL, tenant_id CHAR(32) NOT NULL,"
            " CONSTRAINT uq_team UNIQUE (tenant_id, name))"
        ))
        connection.commit()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {c["name"] for c in sa.inspect(connection).get_columns("team_channels")}
        assert "is_private" in columns
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        columns = {c["name"] for c in sa.inspect(connection).get_columns("team_channels")}
        assert "is_private" not in columns
        # The table itself survives downgrade (history protection).
        assert "team_channels" in sa.inspect(connection).get_table_names()
    finally:
        connection.close()
        engine.dispose()
