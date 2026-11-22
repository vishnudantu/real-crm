"""Tenant-scoped persistence for canonical units, status events, and holds."""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.inventory.models import HoldState, PropertyUnit, UnitHold


def get_unit(session: Session, unit_id: UUID, *, tenant_id: UUID) -> PropertyUnit | None:
    return session.scalar(
        select(PropertyUnit).where(
            PropertyUnit.id == unit_id, PropertyUnit.tenant_id == tenant_id
        )
    )


def get_unit_by_code(
    session: Session, project_id: UUID, code: str, *, tenant_id: UUID
) -> PropertyUnit | None:
    return session.scalar(
        select(PropertyUnit).where(
            PropertyUnit.tenant_id == tenant_id,
            PropertyUnit.project_id == project_id,
            PropertyUnit.internal_code == code,
        )
    )


def list_units(
    session: Session,
    *,
    tenant_id: UUID,
    offset: int,
    limit: int,
    project_id: UUID | None = None,
    status: str | None = None,
) -> tuple[list[PropertyUnit], int]:
    conditions = [PropertyUnit.tenant_id == tenant_id]
    if project_id is not None:
        conditions.append(PropertyUnit.project_id == project_id)
    if status is not None:
        conditions.append(PropertyUnit.status == status)
    total = int(
        session.scalar(
            select(func.count()).select_from(PropertyUnit).where(*conditions)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(PropertyUnit)
            .where(*conditions)
            .order_by(PropertyUnit.project_id, PropertyUnit.internal_code, PropertyUnit.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total


def status_history(
    session: Session, unit_id: UUID, *, tenant_id: UUID
) -> list:
    from app.modules.inventory.models import UnitStatusEvent

    return list(
        session.scalars(
            select(UnitStatusEvent)
            .where(
                UnitStatusEvent.unit_id == unit_id,
                UnitStatusEvent.tenant_id == tenant_id,
            )
            .order_by(UnitStatusEvent.effective_at.asc(), UnitStatusEvent.id.asc())
        ).all()
    )


def get_hold(session: Session, hold_id: UUID, *, tenant_id: UUID) -> UnitHold | None:
    return session.scalar(
        select(UnitHold).where(UnitHold.id == hold_id, UnitHold.tenant_id == tenant_id)
    )


def active_hold_for_unit(
    session: Session, unit_id: UUID, *, tenant_id: UUID
) -> UnitHold | None:
    return session.scalar(
        select(UnitHold).where(
            UnitHold.tenant_id == tenant_id,
            UnitHold.unit_id == unit_id,
            UnitHold.state == HoldState.ACTIVE.value,
        )
    )


def expired_active_holds(session: Session, *, now: datetime) -> list[UnitHold]:
    """Every ACTIVE hold whose expiry has passed, across all tenants.

    Called by the (future) scheduler; tenant filtering happens per hold via
    its own tenant_id when events are written.
    """

    return list(
        session.scalars(
            select(UnitHold).where(
                UnitHold.state == HoldState.ACTIVE.value,
                UnitHold.expires_at <= now,
            )
        ).all()
    )


def availability_counts(
    session: Session, project_id: UUID, *, tenant_id: UUID
) -> dict[str, int]:
    rows = session.execute(
        select(PropertyUnit.status, func.count())
        .where(
            PropertyUnit.tenant_id == tenant_id,
            PropertyUnit.project_id == project_id,
        )
        .group_by(PropertyUnit.status)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def lock_unit_for_hold(session: Session, *, tenant_id: UUID, unit_id: UUID) -> None:
    """Serialize hold acquisition for one unit.

    PostgreSQL: transaction-scoped advisory lock keyed by (tenant, unit), the
    same pattern as postsales.lock_receipt_allocation — it serializes across
    connections and releases at commit/rollback. SQLite (isolated suite) has
    no advisory locks; the caller's in-process lock plus the shared StaticPool
    connection serializes it, and the partial unique index remains the
    database-level backstop on both backends.
    """

    if session.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(
        f"inventory-hold:{tenant_id}:{unit_id}".encode(), digest_size=8
    ).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(digest, "big", signed=True)},
    )
