"""service desk: knowledge-base articles, CSAT surveys, tickets.closed_at

Revision ID: a3f5c7e9b2d4
Revises: e2b7c4a9d1f6
Create Date: 2026-11-23 14:00:00

Additive and idempotent: tables are created only when missing, indexes are
guarded, and the tickets.closed_at column is added through batch mode so the
migration is valid on SQLite as well as PostgreSQL. The composite
ix_<table>_tenant_id_id index is emitted automatically by app.db.tenancy's
after_parent_attach listener when op.create_table builds the table object, so
it is created implicitly here and dropped explicitly, matching the earlier
service-desk and buyer-vault migrations.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f5c7e9b2d4"
down_revision: Union[str, None] = "e2b7c4a9d1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector, table: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table)}


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _ensure_index(name: str, table: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if name not in _index_names(inspector, table):
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if "kb_articles" not in _table_names(inspector):
        op.create_table(
            "kb_articles",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("body_markdown", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("author_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint(
                "status IN ('DRAFT', 'PUBLISHED')", name=op.f("ck_kb_articles_status")
            ),
            sa.CheckConstraint(
                "length(trim(title)) BETWEEN 1 AND 255", name=op.f("ck_kb_articles_title")
            ),
            sa.ForeignKeyConstraint(
                ["author_id"], ["users.id"],
                name=op.f("fk_kb_articles_author_id_users"), ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_kb_articles_tenant_id_tenants"), ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_articles")),
            sa.UniqueConstraint("tenant_id", "slug", name="uq_kb_articles_tenant_slug"),
        )
        op.create_index(op.f("ix_kb_articles_author_id"), "kb_articles", ["author_id"], unique=False)
        op.create_index(op.f("ix_kb_articles_tenant_id"), "kb_articles", ["tenant_id"], unique=False)
    _ensure_index("ix_kb_articles_tenant_status", "kb_articles", ["tenant_id", "status"])
    _ensure_index("ix_kb_articles_tenant_category", "kb_articles", ["tenant_id", "category"])

    inspector = sa.inspect(op.get_bind())
    if "ticket_satisfaction" not in _table_names(inspector):
        op.create_table(
            "ticket_satisfaction",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("ticket_id", sa.Uuid(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_ticket_satisfaction_rating")),
            sa.CheckConstraint(
                "feedback IS NULL OR length(feedback) <= 2000",
                name=op.f("ck_ticket_satisfaction_feedback"),
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_ticket_satisfaction_tenant_id_tenants"), ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["tickets.id"],
                name=op.f("fk_ticket_satisfaction_ticket_id_tickets"), ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_satisfaction")),
            sa.UniqueConstraint(
                "tenant_id", "ticket_id", name="uq_ticket_satisfaction_tenant_ticket"
            ),
        )
        op.create_index(
            op.f("ix_ticket_satisfaction_ticket_id"), "ticket_satisfaction", ["ticket_id"], unique=False
        )
        op.create_index(
            op.f("ix_ticket_satisfaction_tenant_id"), "ticket_satisfaction", ["tenant_id"], unique=False
        )
    _ensure_index(
        "ix_ticket_satisfaction_tenant_responded", "ticket_satisfaction",
        ["tenant_id", "responded_at"],
    )

    inspector = sa.inspect(op.get_bind())
    if not _has_column(inspector, "tickets", "closed_at"):
        with op.batch_alter_table("tickets") as batch_op:
            batch_op.add_column(
                sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _has_column(inspector, "tickets", "closed_at"):
        with op.batch_alter_table("tickets") as batch_op:
            batch_op.drop_column("closed_at")

    inspector = sa.inspect(op.get_bind())
    if "ticket_satisfaction" in _table_names(inspector):
        for name in (
            "ix_ticket_satisfaction_tenant_responded",
            "ix_ticket_satisfaction_tenant_id_id",
            op.f("ix_ticket_satisfaction_tenant_id"),
            op.f("ix_ticket_satisfaction_ticket_id"),
        ):
            if name in _index_names(inspector, "ticket_satisfaction"):
                op.drop_index(name, table_name="ticket_satisfaction")
        op.drop_table("ticket_satisfaction")

    inspector = sa.inspect(op.get_bind())
    if "kb_articles" in _table_names(inspector):
        for name in (
            "ix_kb_articles_tenant_category",
            "ix_kb_articles_tenant_status",
            "ix_kb_articles_tenant_id_id",
            op.f("ix_kb_articles_tenant_id"),
            op.f("ix_kb_articles_author_id"),
        ):
            if name in _index_names(inspector, "kb_articles"):
                op.drop_index(name, table_name="kb_articles")
        op.drop_table("kb_articles")
