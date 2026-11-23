"""buyer_docs: buyer document vault and collection requests

Revision ID: e7f8a9b0c1d2
Revises: c3d4e5f6a7b9
Create Date: 2026-11-22 23:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "c3d4e5f6a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATEGORY_VALUES = "IDENTITY,ADDRESS,INCOME,BANK,LOAN,PROPERTY,AGREEMENT,PAYMENT,REGISTRATION,POSSESSION,OTHER"


def _quoted_categories() -> str:
    return ",".join(f"'{value}'" for value in _CATEGORY_VALUES.split(","))


def upgrade() -> None:
    # Tenant/id composite indexes come from app.db.tenancy.after_parent_attach.
    op.create_table(
        "buyer_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="SUBMITTED", nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("verified_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(f"category IN ({_quoted_categories()})", name=op.f("ck_buyer_documents_buyer_document_category_valid")),
        sa.CheckConstraint("status IN ('SUBMITTED','UNDER_REVIEW','VERIFIED','REJECTED','EXPIRED')", name=op.f("ck_buyer_documents_buyer_document_status_valid")),
        sa.CheckConstraint("length(content_sha256) = 64", name=op.f("ck_buyer_documents_buyer_document_sha256_valid")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_buyer_documents_buyer_document_size_positive")),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_buyer_documents_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_buyer_documents_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], name=op.f("fk_buyer_documents_uploaded_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], name=op.f("fk_buyer_documents_verified_by_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_documents")),
    )
    op.create_index(op.f("ix_buyer_documents_contact_id"), "buyer_documents", ["contact_id"], unique=False)
    op.create_index(op.f("ix_buyer_documents_tenant_id"), "buyer_documents", ["tenant_id"], unique=False)
    op.create_index("ix_buyer_documents_tenant_status", "buyer_documents", ["tenant_id", "status"], unique=False)
    op.create_index("ix_buyer_documents_tenant_category", "buyer_documents", ["tenant_id", "category"], unique=False)

    op.create_table(
        "document_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(f"category IN ({_quoted_categories()})", name=op.f("ck_document_requests_document_request_category_valid")),
        sa.CheckConstraint("status IN ('OPEN','FULFILLED','CANCELLED')", name=op.f("ck_document_requests_document_request_status_valid")),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_document_requests_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_document_requests_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_document_requests_created_by_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_requests")),
    )
    op.create_index(op.f("ix_document_requests_contact_id"), "document_requests", ["contact_id"], unique=False)
    op.create_index(op.f("ix_document_requests_tenant_id"), "document_requests", ["tenant_id"], unique=False)
    op.create_index("ix_document_requests_tenant_status", "document_requests", ["tenant_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_requests_tenant_status", table_name="document_requests")
    op.drop_index(op.f("ix_document_requests_tenant_id"), table_name="document_requests")
    op.drop_index("ix_document_requests_tenant_id_id", table_name="document_requests")
    op.drop_index(op.f("ix_document_requests_contact_id"), table_name="document_requests")
    op.drop_table("document_requests")
    op.drop_index("ix_buyer_documents_tenant_category", table_name="buyer_documents")
    op.drop_index("ix_buyer_documents_tenant_status", table_name="buyer_documents")
    op.drop_index(op.f("ix_buyer_documents_tenant_id"), table_name="buyer_documents")
    op.drop_index("ix_buyer_documents_tenant_id_id", table_name="buyer_documents")
    op.drop_index(op.f("ix_buyer_documents_contact_id"), table_name="buyer_documents")
    op.drop_table("buyer_documents")
