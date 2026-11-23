"""Service-desk support tickets with SLA due tracking and staff comments."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned


class TicketCategory(StrEnum):
    PAYMENT = "PAYMENT"
    DEFECT = "DEFECT"
    DOCUMENT = "DOCUMENT"
    GENERAL = "GENERAL"


class TicketPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_CUSTOMER = "WAITING_ON_CUSTOMER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class KbArticleStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _quoted_values(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class Ticket(TenantOwned, Base):
    """A customer support ticket with a priority-derived SLA deadline.

    ``ticket_number`` is a tenant-unique ``TCK-000001`` sequence allocated
    under a per-tenant advisory lock (see repository). ``sla_due_at`` is set
    once at creation from priority; no SLA pause is modeled at this stage.
    """

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ticket_number", name="uq_tickets_tenant_number"),
        CheckConstraint(
            f"category IN ({_quoted_values(TicketCategory)})", name="ck_tickets_category"
        ),
        CheckConstraint(
            f"priority IN ({_quoted_values(TicketPriority)})", name="ck_tickets_priority"
        ),
        CheckConstraint(
            f"status IN ({_quoted_values(TicketStatus)})", name="ck_tickets_status"
        ),
        Index("ix_tickets_tenant_status", "tenant_id", "status"),
        Index("ix_tickets_tenant_sla_due_at", "tenant_id", "sla_due_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ticket_number: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TicketCategory.GENERAL.value,
        server_default=TicketCategory.GENERAL.value,
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TicketPriority.MEDIUM.value,
        server_default=TicketPriority.MEDIUM.value,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=TicketStatus.OPEN.value,
        server_default=TicketStatus.OPEN.value,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    booking_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sale_bookings.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )

    comments: Mapped[list["TicketComment"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="TicketComment.ticket_id",
        order_by="TicketComment.created_at, TicketComment.id",
    )
    satisfaction: Mapped["TicketSatisfaction | None"] = relationship(
        back_populates="ticket",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="TicketSatisfaction.ticket_id",
    )


class TicketComment(TenantOwned, Base):
    """A staff or customer-facing comment on a ticket thread."""

    __tablename__ = "ticket_comments"
    __table_args__ = (
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 4000", name="ck_ticket_comments_body"),
        Index("ix_ticket_comments_tenant_ticket_created", "tenant_id", "ticket_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    ticket: Mapped[Ticket] = relationship(back_populates="comments", foreign_keys=[ticket_id])


class KbArticle(TenantOwned, Base):
    """A tenant knowledge-base article.

    Staff author articles in DRAFT and publish them; only PUBLISHED rows are
    visible to buyers through the help-center surface. ``category`` is a plain
    free-text string (kept deliberately simple — no category table), and
    ``slug`` is unique per tenant for stable deep links.
    """

    __tablename__ = "kb_articles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_kb_articles_tenant_slug"),
        CheckConstraint(
            f"status IN ({_quoted_values(KbArticleStatus)})", name="ck_kb_articles_status"
        ),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 255", name="ck_kb_articles_title"),
        Index("ix_kb_articles_tenant_status", "tenant_id", "status"),
        Index("ix_kb_articles_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=KbArticleStatus.DRAFT.value,
        server_default=KbArticleStatus.DRAFT.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class TicketSatisfaction(TenantOwned, Base):
    """A CSAT survey row for a closed ticket: 1-5 rating plus free text.

    Exactly one row per ticket (enforced by the tenant+ticket unique key) is
    opened when staff move a ticket to CLOSED; the buyer — or a staff member
    on their behalf — may record one rating. Later submissions overwrite the
    first so a customer can change their mind.
    """

    __tablename__ = "ticket_satisfaction"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ticket_id", name="uq_ticket_satisfaction_tenant_ticket"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_ticket_satisfaction_rating"),
        CheckConstraint(
            "feedback IS NULL OR length(feedback) <= 2000", name="ck_ticket_satisfaction_feedback"
        ),
        Index("ix_ticket_satisfaction_tenant_responded", "tenant_id", "responded_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ticket: Mapped[Ticket] = relationship(back_populates="satisfaction", foreign_keys=[ticket_id])
