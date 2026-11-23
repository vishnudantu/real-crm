"""bookings: native contact link (additive contact_id FK)

Revision ID: d9b3e5c7a1f4
Revises: c3a7f1d9e2b5
Create Date: 2026-11-23 15:00:00

Site-visit bookings gain a first-class link to the canonical customer graph:

- bookings.contact_id (Uuid, nullable) -> contacts.id ON DELETE SET NULL,
  with ix_bookings_contact_id.

Additive-only: ``lead_id`` remains the intake system-of-record and is NOT
removed. NULL contact_id leaves legacy bookings byte-for-byte unchanged, and
deleting a contact never cascades into visit history.

Batch mode (copy-and-move) keeps the ALTER TABLE + FK valid on SQLite while
emitting plain ALTER TABLE on PostgreSQL. Re-running upgrade() on a database
that already carries the column is a no-op (idempotent guard).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9b3e5c7a1f4"
down_revision: Union[str, None] = "e2b7c4a9d1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("bookings")}
    if "contact_id" not in existing:
        # SQLite ignores FK options on plain ADD COLUMN; batch mode carries the
        # FK + index through the copy-and-move recreate on SQLite and emits a
        # plain ALTER on PostgreSQL.
        with op.batch_alter_table("bookings") as batch_op:
            batch_op.add_column(sa.Column("contact_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_bookings_contact_id", ["contact_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_bookings_contact_id_contacts",
                "contacts",
                ["contact_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint(
            "fk_bookings_contact_id_contacts", type_="foreignkey"
        )
        batch_op.drop_index("ix_bookings_contact_id")
        batch_op.drop_column("contact_id")
