"""City Intelligence Engine (Phase 1) — curated data models.

Two tenant-owned tables hold admin-curated, source-attributed input. Nothing is
geocoded or fetched from an external provider: every row carries a source and a
confidence level so locality claims are traceable, never invented.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned

__all__ = ["ProjectAmenity", "LocalityReport", "CONFIDENCE_LEVELS", "AMENITY_CATEGORIES"]


def utcnow() -> datetime:
    return datetime.now(UTC)


AMENITY_CATEGORIES = ("school", "hospital", "transit", "employment", "amenity")
CONFIDENCE_LEVELS = ("verified", "estimated", "unverified")


class ProjectAmenity(TenantOwned, Base):
    """A curated point of interest near a project (school, transit, etc.).

    Distances are authored by an admin (curated), not geocoded. ``source_ref``
    records where the figure came from; ``confidence`` states how certain it is.
    """

    __tablename__ = "project_amenities"
    __table_args__ = (
        CheckConstraint(
            "category IN ('school','hospital','transit','employment','amenity')",
            name="amenity_category_valid",
        ),
        CheckConstraint("distance_km >= 0", name="amenity_distance_non_negative"),
        CheckConstraint("travel_minutes >= 0", name="amenity_travel_non_negative"),
        CheckConstraint(
            "confidence IN ('verified','estimated','unverified')",
            name="amenity_confidence_valid",
        ),
        Index("ix_project_amenities_tenant_project", "tenant_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    travel_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(16), nullable=False, default="estimated", server_default="estimated"
    )
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class LocalityReport(TenantOwned, Base):
    """An authored, source-verified locality research note for a project.

    ``sources`` is a JSON list of ``{label, ref, observed_on, confidence}`` so the
    report states its evidence and uncertainty. Reports enter the existing
    DRAFT ProjectFact approve flow via ``facts.generate_locality_facts``.
    """

    __tablename__ = "locality_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','APPROVED')", name="locality_report_status_valid"
        ),
        UniqueConstraint(
            "tenant_id", "project_id", "title",
            name="uq_locality_reports_tenant_project_title",
        ),
        Index("ix_locality_reports_tenant_project", "tenant_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
