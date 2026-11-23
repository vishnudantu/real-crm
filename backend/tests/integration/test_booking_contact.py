"""Native contact link on site-visit bookings: additive ``bookings.contact_id``.

Verifies:
- POST /bookings accepts an optional same-tenant ``contact_id`` and exposes it
  in the booking response (create, detail, and list).
- Omitted ``contact_id`` stays null — legacy lead-only bookings unaffected.
- A cross-tenant ``contact_id`` is refused with 404 and books nothing.
- POST /bookings/schedule-custom passes ``contact_id`` through.
- The additive migration (rev d9b3e5c7a1f4) is idempotent and round-trips on
  isolated SQLite with the FK/index in place.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.modules.leads.models import LeadSource
from app.modules.projects.models import ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.booking_support import (
    create_booking,
    create_slot,
    get_booking,
    list_bookings,
)
from tests.lead_support import create_lead
from tests.project_support import create_project


def _future(hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def _create_contact(
    client: TestClient,
    headers: dict[str, str],
    *,
    display_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> str:
    """Create a tenant contact via the console endpoint; return its id."""

    payload: dict[str, Any] = {"display_name": display_name}
    if email is not None:
        payload["email"] = email
    if phone is not None:
        payload["phone"] = phone
    response = client.post(
        "/api/v1/customers/contacts", json=payload, headers=headers
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["contact"]["id"]


@pytest.fixture()
def admin_user(user_factory: Callable[..., User]) -> User:
    return user_factory(role=RoleName.ADMIN, email=f"admin-{uuid4().hex[:8]}@example.com")


@pytest.fixture()
def admin_headers(
    auth_headers: Callable[..., dict[str, str]], admin_user: User
) -> dict[str, str]:
    return auth_headers(admin_user.email)


@pytest.fixture()
def active_project(
    client: TestClient, admin_headers: dict[str, str]
) -> dict[str, Any]:
    project = create_project(
        client, admin_headers, name=f"Contact Project {uuid4().hex[:6]}"
    )
    client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": ProjectStatus.ACTIVE.value},
        headers=admin_headers,
    )
    return project


@pytest.fixture()
def buyer_lead(
    client: TestClient, active_project: dict[str, Any]
) -> dict[str, Any]:
    return create_lead(
        client,
        project_id=active_project["id"],
        full_name="Contact Booking Buyer",
        phone="+919811111111",
        source=LeadSource.WEBSITE.value,
        consent_to_contact=True,
    )


@pytest.fixture()
def slot(
    client: TestClient,
    admin_headers: dict[str, str],
    active_project: dict[str, Any],
) -> dict[str, Any]:
    start = _future(48)
    return create_slot(
        client,
        admin_headers,
        project_id=active_project["id"],
        start_time=start,
        end_time=start + timedelta(hours=1),
    )


def test_booking_create_accepts_and_exposes_same_tenant_contact_id(
    client: TestClient,
    admin_headers: dict[str, str],
    slot: dict[str, Any],
    buyer_lead: dict[str, Any],
) -> None:
    contact_id = _create_contact(
        client,
        admin_headers,
        display_name="Native Contact",
        email=f"native-{uuid4().hex[:8]}@example.com",
    )

    booking = create_booking(
        client,
        admin_headers,
        slot_id=slot["id"],
        lead_id=buyer_lead["id"],
        contact_id=contact_id,
    )
    assert booking["contact_id"] == contact_id
    assert booking["lead_id"] == buyer_lead["id"]  # lead_id is NOT removed

    detail = get_booking(client, admin_headers, booking["id"])
    assert detail["contact_id"] == contact_id

    listed = list_bookings(client, admin_headers, params={"lead_id": buyer_lead["id"]})
    assert listed["items"][0]["contact_id"] == contact_id


def test_booking_create_without_contact_id_stays_null(
    client: TestClient,
    admin_headers: dict[str, str],
    slot: dict[str, Any],
    buyer_lead: dict[str, Any],
) -> None:
    booking = create_booking(
        client, admin_headers, slot_id=slot["id"], lead_id=buyer_lead["id"]
    )
    assert booking["contact_id"] is None


def test_booking_create_rejects_cross_tenant_contact_id(
    client: TestClient,
    admin_headers: dict[str, str],
    slot: dict[str, Any],
    buyer_lead: dict[str, Any],
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    with test_session_factory() as session:
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(
        role=RoleName.ADMIN,
        email=f"other-admin-{uuid4().hex[:8]}@example.com",
        tenant=other_tenant,
    )
    other_headers = auth_headers(other_admin.email)
    foreign_contact_id = _create_contact(
        client,
        other_headers,
        display_name="Foreign Contact",
        email=f"foreign-{uuid4().hex[:8]}@example.com",
    )

    response = client.post(
        "/api/v1/bookings",
        json={
            "slot_id": slot["id"],
            "lead_id": buyer_lead["id"],
            "contact_id": foreign_contact_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 404, response.text

    listed = list_bookings(client, admin_headers, params={"lead_id": buyer_lead["id"]})
    assert listed["total"] == 0


def test_schedule_custom_passes_contact_through(
    client: TestClient,
    admin_headers: dict[str, str],
    active_project: dict[str, Any],
    buyer_lead: dict[str, Any],
) -> None:
    contact_id = _create_contact(
        client,
        admin_headers,
        display_name="Custom Schedule Contact",
        phone=f"+9198{uuid4().int % 100000000:08d}",
    )
    start = _future(72)
    response = client.post(
        "/api/v1/bookings/schedule-custom",
        json={
            "lead_id": buyer_lead["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=1)).isoformat(),
            "contact_id": contact_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["contact_id"] == contact_id


# --------------------------------------------------------------------------- #
# Migration evidence (isolated in-memory SQLite; the real DB is never touched)


def test_migration_upgrade_and_downgrade_on_isolated_sqlite() -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration_path = next(
        (Path(__file__).parents[2] / "alembic" / "versions").glob("*d9b3e5c7a1f4*")
    )
    spec = importlib.util.spec_from_file_location(
        "booking_contact_migration", migration_path
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "d9b3e5c7a1f4"
    assert migration.down_revision == "c3a7f1d9e2b5"

    engine = sa.create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        metadata = sa.MetaData()
        sa.Table(
            "tenants", metadata,
            sa.Column("id", sa.Uuid(), primary_key=True),
        )
        sa.Table(
            "contacts", metadata,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
        )
        bookings = sa.Table(
            "bookings", metadata,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("lead_id", sa.Uuid(), nullable=False),
            sa.Column("slot_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="CONFIRMED"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(engine)
        tenant_id, booking_id = uuid4(), uuid4()
        with engine.begin() as connection:
            connection.execute(
                sa.insert(bookings).values(
                    id=booking_id,
                    tenant_id=tenant_id,
                    lead_id=uuid4(),
                    slot_id=uuid4(),
                    status="CONFIRMED",
                    created_at=datetime(2026, 11, 23, tzinfo=UTC),
                )
            )

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            migration.op = Operations(context)

            migration.upgrade()
            migration.upgrade()  # idempotent: a second run must not fail

            inspector = sa.inspect(connection)
            columns = {col["name"] for col in inspector.get_columns("bookings")}
            assert "contact_id" in columns
            index_names = {ix["name"] for ix in inspector.get_indexes("bookings")}
            assert "ix_bookings_contact_id" in index_names
            foreign_keys = {
                fk["name"]: fk for fk in inspector.get_foreign_keys("bookings")
            }
            assert "fk_bookings_contact_id_contacts" in foreign_keys
            fk = foreign_keys["fk_bookings_contact_id_contacts"]
            assert fk["referred_table"] == "contacts"
            assert fk["options"].get("ondelete") == "SET NULL"

            # Pre-existing rows survive the batch copy with a null link.
            row = connection.execute(
                sa.text("SELECT contact_id FROM bookings WHERE id = :id"),
                {"id": booking_id.hex},
            ).one()
            assert row[0] is None

            migration.downgrade()
            inspector = sa.inspect(connection)
            columns = {col["name"] for col in inspector.get_columns("bookings")}
            assert "contact_id" not in columns
            index_names = {ix["name"] for ix in inspector.get_indexes("bookings")}
            assert "ix_bookings_contact_id" not in index_names
    finally:
        engine.dispose()
