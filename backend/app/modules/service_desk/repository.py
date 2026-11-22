"""Tenant-scoped ticket persistence and TCK number allocation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.modules.service_desk.models import Ticket, TicketComment

TICKET_PREFIX = "TCK"


def lock_ticket_allocation(session: Session, *, tenant_id: UUID) -> None:
    """Serialize number allocation within a tenant on PostgreSQL."""

    if session.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(f"service_desk:{tenant_id}".encode(), digest_size=8).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(digest, "big", signed=True)},
    )


def highest_ticket_sequence(session: Session, *, tenant_id: UUID) -> int:
    """Return MAX numeric suffix across the tenant's tickets, never a count."""

    numbers = session.scalars(
        select(Ticket.ticket_number).where(Ticket.tenant_id == tenant_id)
    ).all()
    highest = 0
    for number in numbers:
        _, _, digits = (number or "").rpartition("-")
        if digits.isdigit():
            highest = max(highest, int(digits))
    return highest


def next_ticket_number(session: Session, *, tenant_id: UUID) -> str:
    sequence = highest_ticket_sequence(session, tenant_id=tenant_id) + 1
    return f"{TICKET_PREFIX}-{sequence:06d}"


def get_ticket(session: Session, ticket_id: UUID, *, tenant_id: UUID) -> Ticket | None:
    return session.scalar(
        select(Ticket)
        .options(selectinload(Ticket.comments))
        .where(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id)
    )


def comments_for_ticket(
    session: Session, *, ticket_id: UUID, tenant_id: UUID
) -> list[TicketComment]:
    return list(
        session.scalars(
            select(TicketComment)
            .where(
                TicketComment.ticket_id == ticket_id,
                TicketComment.tenant_id == tenant_id,
            )
            .order_by(TicketComment.created_at, TicketComment.id)
        ).all()
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
