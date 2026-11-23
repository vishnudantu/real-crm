"""Tenant-scoped ticket persistence and TCK number allocation."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.modules.service_desk.models import (
    KbArticle,
    KbArticleStatus,
    Ticket,
    TicketComment,
    TicketSatisfaction,
)
from app.modules.service_desk.search import like_contains_pattern

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
        value, _, digits = (number or "").rpartition("-")
        if value == TICKET_PREFIX and digits.isdigit():
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


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Lowercase hyphen slug; empty results fall back to ``article``."""
    slug = _SLUG_NON_ALNUM.sub("-", unicodedata.normalize("NFKD", title)
                               .encode("ascii", "ignore").decode("ascii").lower()).strip("-")
    return slug[:60] or "article"


def unique_article_slug(session: Session, *, tenant_id: UUID, title: str,
                        base: str | None = None, exclude_id: UUID | None = None) -> str:
    """Tenant-unique slug for ``title`` (or a caller-supplied ``base``).

    Collisions gain ``-2``, ``-3``… suffixes; the search stays inside the
    tenant so slugs in other tenants never influence allocation.
    """
    root = (base or slugify(title))[:72].rstrip("-") or "article"
    candidate = root
    counter = 1
    while True:
        statement = select(KbArticle.id).where(
            KbArticle.tenant_id == tenant_id, KbArticle.slug == candidate
        )
        if exclude_id is not None:
            statement = statement.where(KbArticle.id != exclude_id)
        if session.scalar(statement.limit(1)) is None:
            return candidate
        counter += 1
        candidate = f"{root}-{counter}"


def get_article(session: Session, *, article_id: UUID, tenant_id: UUID) -> KbArticle | None:
    return session.scalar(
        select(KbArticle).where(KbArticle.id == article_id, KbArticle.tenant_id == tenant_id)
    )


def list_articles(
    session: Session,
    *,
    tenant_id: UUID,
    article_status: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[KbArticle], int]:
    conditions = [KbArticle.tenant_id == tenant_id]
    if article_status is not None:
        conditions.append(KbArticle.status == article_status)
    if category is not None:
        conditions.append(KbArticle.category == category)
    if search:
        pattern = like_contains_pattern(search)
        # Case-insensitive LIKE done with lower() on both sides so it behaves
        # identically on SQLite and PostgreSQL (see search.py for the why).
        conditions.append(
            or_(
                func.lower(KbArticle.title).like(pattern, escape="\\"),
                func.lower(KbArticle.body_markdown).like(pattern, escape="\\"),
                func.lower(KbArticle.category).like(pattern, escape="\\"),
            )
        )
    total = session.scalar(
        select(func.count()).select_from(KbArticle).where(*conditions)
    ) or 0
    items = list(
        session.scalars(
            select(KbArticle)
            .where(*conditions)
            .order_by(KbArticle.updated_at.desc(), KbArticle.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def published_articles_for_suggestions(
    session: Session, *, tenant_id: UUID, limit: int = 200
) -> list[KbArticle]:
    """Newest-N published articles; the suggestion scorer ranks in Python."""
    return list(
        session.scalars(
            select(KbArticle)
            .where(
                KbArticle.tenant_id == tenant_id,
                KbArticle.status == KbArticleStatus.PUBLISHED.value,
            )
            .order_by(KbArticle.published_at.desc(), KbArticle.id)
            .limit(limit)
        ).all()
    )


# --------------------------------------------------------------------------- #
# CSAT
# --------------------------------------------------------------------------- #


def get_satisfaction(
    session: Session, *, ticket_id: UUID, tenant_id: UUID
) -> TicketSatisfaction | None:
    return session.scalar(
        select(TicketSatisfaction).where(
            TicketSatisfaction.ticket_id == ticket_id,
            TicketSatisfaction.tenant_id == tenant_id,
        )
    )


def csat_aggregates(session: Session, *, tenant_id: UUID, since):
    """Survey + ticket rows created after ``since`` for the stats endpoint.

    SQLite has no portable date_trunc and PostgreSQL lacks strftime, so the
    month bucketing happens in Python. The *window filter* stays SQL-side so
    the scan is bounded by the requested period and uses the tenant indexes.
    """
    survey_rows = session.execute(
        select(
            TicketSatisfaction.rating,
            TicketSatisfaction.responded_at,
            TicketSatisfaction.created_at,
        )
        .where(
            TicketSatisfaction.tenant_id == tenant_id,
            TicketSatisfaction.created_at >= since,
        )
    ).all()
    ticket_rows = session.execute(
        select(Ticket.created_at, Ticket.closed_at)
        .where(Ticket.tenant_id == tenant_id, Ticket.created_at >= since)
    ).all()
    return survey_rows, ticket_rows


def open_ticket_counts(session: Session, *, tenant_id: UUID) -> dict[str, int]:
    """Counts of unresolved tickets grouped by status (open trends card)."""
    rows = session.execute(
        select(Ticket.status, func.count())
        .where(Ticket.tenant_id == tenant_id)
        .group_by(Ticket.status)
    ).all()
    return {status: count for status, count in rows}

