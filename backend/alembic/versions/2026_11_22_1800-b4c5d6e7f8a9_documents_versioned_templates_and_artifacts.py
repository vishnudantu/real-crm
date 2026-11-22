"""documents: versioned templates, immutable PDF artifacts, and evidence

Revision ID: b4c5d6e7f8a9
Revises: a5b6c7d8e9f0
Create Date: 2026-11-22 18:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create versioned template and document tables.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "document_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("key IN ('DEMAND_LETTER','RECEIPT','STATEMENT')", name=op.f("ck_document_templates_document_template_key_valid")),
        sa.CheckConstraint("version > 0", name=op.f("ck_document_templates_document_template_version_positive")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_document_templates_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_document_templates_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_templates")),
        sa.UniqueConstraint("tenant_id", "key", "version", name="uq_document_templates_tenant_key_version"),
    )
    op.create_index(op.f("ix_document_templates_tenant_id"), "document_templates", ["tenant_id"], unique=False)
    op.create_index("ix_document_templates_tenant_key_active", "document_templates", ["tenant_id", "key", "is_active"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=24), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("document_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("kind IN ('DEMAND_LETTER','RECEIPT','STATEMENT')", name=op.f("ck_documents_document_kind_valid")),
        sa.CheckConstraint("reference_type IN ('installment','receipt')", name=op.f("ck_documents_document_reference_type_valid")),
        sa.CheckConstraint("status IN ('DRAFT','ISSUED','VOIDED')", name=op.f("ck_documents_document_status_valid")),
        sa.CheckConstraint("template_version > 0", name=op.f("ck_documents_document_template_version_positive")),
        sa.CheckConstraint("length(content_sha256) = 64", name=op.f("ck_documents_document_sha256_valid")),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], name=op.f("fk_documents_issued_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["document_templates.id"], name=op.f("fk_documents_template_id_document_templates"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_documents_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("tenant_id", "document_number", name="uq_documents_tenant_number"),
        sa.UniqueConstraint("tenant_id", "kind", "reference_id", "template_version", name="uq_documents_reference_template_version"),
    )
    op.create_index(op.f("ix_documents_reference_id"), "documents", ["reference_id"], unique=False)
    op.create_index(op.f("ix_documents_tenant_id"), "documents", ["tenant_id"], unique=False)
    op.create_index("ix_documents_tenant_kind_created", "documents", ["tenant_id", "kind", "created_at"], unique=False)
    op.create_index("ix_documents_tenant_reference", "documents", ["tenant_id", "reference_type", "reference_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_tenant_reference", table_name="documents")
    op.drop_index("ix_documents_tenant_kind_created", table_name="documents")
    op.drop_index(op.f("ix_documents_tenant_id"), table_name="documents")
    op.drop_index("ix_documents_tenant_id_id", table_name="documents")
    op.drop_index(op.f("ix_documents_reference_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_document_templates_tenant_key_active", table_name="document_templates")
    op.drop_index(op.f("ix_document_templates_tenant_id"), table_name="document_templates")
    op.drop_index("ix_document_templates_tenant_id_id", table_name="document_templates")
    op.drop_table("document_templates")
