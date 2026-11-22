"""bank transactions for reconciliation ingestion and match suggestions

Revision ID: c4d5e6f7a8b9
Revises: c5d6e7f8a9b0
Create Date: 2026-11-22 22:30:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the bank transaction ingestion table.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_label", sa.String(length=64), nullable=False),
        sa.Column("utr", sa.String(length=128), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("payer_name", sa.String(length=255), nullable=True),
        sa.Column("payer_detail", sa.String(length=255), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="UNMATCHED", nullable=False),
        sa.Column("matched_installment_id", sa.Uuid(), nullable=True),
        sa.Column("matched_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["matched_installment_id"], ["installments.id"],
            name=op.f("fk_bank_transactions_matched_installment_id_installments"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_bank_transactions_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_transactions")),
        sa.UniqueConstraint(
            "tenant_id", "account_label", "utr", name="uq_bank_transactions_tenant_account_utr"
        ),
    )
    op.create_index(op.f("ix_bank_transactions_utr"), "bank_transactions", ["utr"], unique=False)
    op.create_index(
        op.f("ix_bank_transactions_matched_installment_id"),
        "bank_transactions", ["matched_installment_id"], unique=False,
    )
    op.create_index(op.f("ix_bank_transactions_tenant_id"), "bank_transactions", ["tenant_id"], unique=False)
    op.create_index(
        "ix_bank_transactions_tenant_status", "bank_transactions", ["tenant_id", "status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_tenant_status", table_name="bank_transactions")
    op.drop_index(op.f("ix_bank_transactions_tenant_id"), table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_tenant_id_id", table_name="bank_transactions")
    op.drop_index(op.f("ix_bank_transactions_matched_installment_id"), table_name="bank_transactions")
    op.drop_index(op.f("ix_bank_transactions_utr"), table_name="bank_transactions")
    op.drop_table("bank_transactions")
