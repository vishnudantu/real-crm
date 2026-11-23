"""Solar-facing data models: tower orientations and site coordinates."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned

__all__ = ["TowerOrientation"]


def utcnow() -> datetime:
    return datetime.now(UTC)


class TowerOrientation(TenantOwned, Base):
    """Captures the facade bearing for a tower within a project.

    The bearing is the direction the tower's primary facade faces, measured
    in degrees clockwise from true north (0 = N, 90 = E, 180 = S, 270 = W).
    """

    __tablename__ = "tower_orientations"
    __table_args__ = (
        CheckConstraint(
            "orientation_deg >= 0 AND orientation_deg < 360",
            name="tower_orientation_range",
        ),
        UniqueConstraint(
            "tenant_id", "project_id", "tower_label",
            name="uq_tower_orientations_tenant_project_tower",
        ),
        Index(
            "ix_tower_orientations_tenant_project",
            "tenant_id", "project_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tower_label: Mapped[str] = mapped_column(String(64), nullable=False)
    orientation_deg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
