"""Tenant ownership helpers for shared-schema isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Uuid, event
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy.schema import Table

from app.modules.tenancy.models import Tenant, TenantStatus

if TYPE_CHECKING:
    from sqlalchemy import Select


class TenantOwned:
    """A non-null tenant ownership column for domain and auth-session tables."""

    @declared_attr
    def tenant_id(cls) -> Mapped[UUID]:
        return mapped_column(
            Uuid(as_uuid=True),
            ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def tenant(cls) -> Mapped[Tenant]:
        from sqlalchemy.orm import relationship

        return relationship(Tenant, lazy="joined")


@event.listens_for(Table, "after_parent_attach")
def _index_tenant_lookups(table: Table, parent) -> None:
    """Add composite tenant indexes without obscuring module table args."""

    if "tenant_id" not in table.c:
        return
    if table.name.startswith("_alembic_tmp_"):
        return
    if table.name == "tenants":
        return
    if table.name == "system_settings":
        return  # (tenant_id, key) is the composite primary key.
    key = "jti" if table.name == "revoked_access_tokens" else "id"
    name = f"ix_{table.name}_tenant_id_{key}"
    if any(index.name == name for index in table.indexes):
        return
    if key in table.c:
        index = Index(name, table.c.tenant_id, table.c[key])
        index.table = table


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID


def require_tenant_context(tenant: Tenant) -> TenantContext:
    if tenant.status != TenantStatus.ACTIVE.value:
        raise ValueError("An active tenant is required.")
    return TenantContext(tenant_id=tenant.id)


def with_tenant(statement: Select, tenant_id: UUID) -> Select:
    """Apply a mandatory tenant predicate to a query's root entity."""

    model = statement.column_descriptions[0]["entity"]
    if model is None or not hasattr(model, "tenant_id"):
        raise TypeError("Tenant scoping requires a tenant-owned root model.")
    return statement.where(model.tenant_id == tenant_id)


TENANT_TABLES = frozenset({
    "users", "projects", "project_facts", "fact_versions", "leads", "lead_assignments",
    "conversations", "messages", "visit_slots", "bookings", "handoffs", "follow_ups",
    "notifications", "notification_templates", "system_settings", "marketing_spends",
    "audit_logs", "refresh_tokens", "revoked_access_tokens",
    "sale_bookings", "payment_plans", "installments", "receipts", "broker_commissions",
    "lead_ingestion_events", "subscriptions", "invoices",
    "channel_credentials", "channel_conversations", "channel_messages",
    "call_records", "call_recordings", "tenant_features", "integration_connections",
    "contacts", "contact_methods", "opportunities", "contact_merges",
    "property_units", "unit_status_events", "unit_holds",
    "document_templates", "documents",
    "team_channels", "team_channel_members", "team_messages",
    "approval_requests",
})
