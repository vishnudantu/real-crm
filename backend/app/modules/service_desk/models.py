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
