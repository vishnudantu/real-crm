"""SQLAlchemy models for the canonical customer + opportunity graph (PF-008/009)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned
from app.modules.leads.models import Lead
from app.modules.postsales.models import SaleBooking
from app.modules.projects.models import Project
from app.modules.users.models import User


class ContactStatus(StrEnum):
    ACTIVE = "ACTIVE"
    MERGED = "MERGED"
    ANONYMIZED = "ANONYMIZED"


class ContactMethodKind(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    WHATSAPP_ID = "WHATSAPP_ID"
    INSTAGRAM_HANDLE = "INSTAGRAM_HANDLE"
    MESSENGER_HANDLE = "MESSENGER_HANDLE"


class VerificationState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"


class OpportunityStage(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    VISITED = "VISITED"
    NEGOTIATING = "NEGOTIATING"
    BOOKED = "BOOKED"
    WON = "WON"
    LOST = "LOST"
    LOST_DORMANT = "LOST_DORMANT"


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def _quoted_values(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class Contact(TenantOwned, Base):
    """Canonical tenant customer identity, above the legacy lead record.

    ``canonical_key`` is a stored, immutable normalized identity string: the
    lexicographically lowest VERIFIED contact method value prefixed by its
    kind (e.g. ``email:a@b.com``), or ``uuid:<uuid4>`` when no verified method
    exists. It is stable across merges (merged rows keep their own key) and
    is unique per tenant.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_key", name="uq_contacts_tenant_canonical_key"),
        CheckConstraint(
            f"status IN ({_quoted_values(ContactStatus)})",
            name="ck_contacts_status",
        ),
        Index("ix_contacts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    canonical_key: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ContactStatus.ACTIVE.value,
        server_default=ContactStatus.ACTIVE.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_into_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    methods: Mapped[list["ContactMethod"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ContactMethod.contact_id",
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="contact",
        foreign_keys="Opportunity.contact_id",
    )


class ContactMethod(TenantOwned, Base):
    """A single verified or unverified way of reaching a contact.

    ``normalized_value``: lowercase for EMAIL/social handles, ``+digits`` or
    ``digits`` for PHONE/WHATSAPP_ID. Unique per (tenant, kind, value).
    """

    __tablename__ = "contact_methods"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kind", "normalized_value",
            name="uq_contact_methods_tenant_kind_value",
        ),
        CheckConstraint(
            f"kind IN ({_quoted_values(ContactMethodKind)})",
            name="ck_contact_methods_kind",
        ),
        CheckConstraint(
            f"verification_state IN ({_quoted_values(VerificationState)})",
            name="ck_contact_methods_verification_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    contact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(320), nullable=False)
    verification_state: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VerificationState.UNVERIFIED.value,
        server_default=VerificationState.UNVERIFIED.value,
    )
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    contact: Mapped[Contact] = relationship(
        back_populates="methods", foreign_keys=[contact_id]
    )


class Opportunity(TenantOwned, Base):
    """A purchase intent linking a contact to a project (and optional lead)."""

    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            f"stage IN ({_quoted_values(OpportunityStage)})",
            name="ck_opportunities_stage",
        ),
        CheckConstraint("budget_min IS NULL OR budget_min >= 0", name="ck_opportunities_budget_min"),
        CheckConstraint("budget_max IS NULL OR budget_max >= 0", name="ck_opportunities_budget_max"),
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_opportunities_budget_ordered",
        ),
        Index("ix_opportunities_tenant_contact", "tenant_id", "contact_id"),
        Index("ix_opportunities_tenant_project", "tenant_id", "project_id"),
        Index("ix_opportunities_tenant_owner", "tenant_id", "owner_user_id"),
        Index(
            "uq_opportunities_tenant_lead",
            "tenant_id", "lead_id",
            unique=True,
            postgresql_where=text("lead_id IS NOT NULL"),
            sqlite_where=text("lead_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    contact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=OpportunityStage.NEW.value,
        server_default=OpportunityStage.NEW.value,
        index=True,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    budget_min: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    preferred_configuration: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    loss_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    won_booking_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sale_bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    value_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    contact: Mapped[Contact] = relationship(
        back_populates="opportunities", foreign_keys=[contact_id]
    )
    project: Mapped[Project] = relationship(foreign_keys=[project_id])
    lead: Mapped[Lead | None] = relationship(foreign_keys=[lead_id])
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_user_id])
    won_booking: Mapped[SaleBooking | None] = relationship(
        foreign_keys=[won_booking_id]
    )


class ContactMerge(TenantOwned, Base):
    """Audit record for a contact merge; evidence drives exact revert.

    ``evidence`` JSON shape::

        {
          "moved_method_ids": [uuid-str, ...],       # loser methods repointed
          "skipped_method_ids": [uuid-str, ...],     # kept on loser (conflict)
          "repointed_opportunity_ids": [uuid-str,...],
          "survivor_canonical_key": str,
          "merged_canonical_key": str,
          "merged_previous_status": str,
          "merged_previous_display_name": str,
        }
    """

    __tablename__ = "contact_merges"
    __table_args__ = (
        Index("ix_contact_merges_tenant_survivor", "tenant_id", "survivor_id"),
        Index("ix_contact_merges_tenant_merged", "tenant_id", "merged_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    survivor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    merged_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reverted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
