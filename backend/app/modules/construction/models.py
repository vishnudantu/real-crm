"""Construction milestones and append-only progress updates."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned


class MilestoneStatus(StrEnum):
    """Construction progress and certification lifecycle."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    CERTIFIED = "CERTIFIED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class ConstructionMilestone(TenantOwned, Base):
    """A scheduled unit of construction work belonging to one project."""

    __tablename__ = "construction_milestones"
    __table_args__ = (
        CheckConstraint(
            "percent_complete BETWEEN 0 AND 100",
            name="percent_complete_range",
        ),
        CheckConstraint(
            "status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','DELAYED','CERTIFIED')",
            name="status_valid",
        ),
        UniqueConstraint(
            "tenant_id", "project_id", "sequence_no",
            name="uq_construction_milestones_tenant_project_sequence",
        ),
        Index(
            "ix_construction_milestones_tenant_project_status",
            "tenant_id", "project_id", "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MilestoneStatus.NOT_STARTED.value,
        server_default=MilestoneStatus.NOT_STARTED.value,
    )
    percent_complete: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    certified_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )

    updates: Mapped[list["MilestoneUpdate"]] = relationship(
        back_populates="milestone",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MilestoneUpdate.created_at",
    )


class MilestoneUpdate(TenantOwned, Base):
    """Append-only site progress observation for a construction milestone."""

    __tablename__ = "milestone_updates"
    __table_args__ = (
        CheckConstraint(
            "percent_complete BETWEEN 0 AND 100",
            name="percent_complete_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    milestone_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("construction_milestones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    percent_complete: Mapped[int] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    milestone: Mapped[ConstructionMilestone] = relationship(back_populates="updates")
