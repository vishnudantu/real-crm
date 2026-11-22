"""approval side-effect columns for bookings and property units

Revision ID: c8d9e0f1a2b3
Revises: f7a8b9c0d1e2
Create Date: 2026-11-23 00:00:00

Adds the entity-side flag columns wired to the approvals dispatcher:

- bookings.car_request_status (NOT NULL, default 'NONE', check-constrained to
  NONE/PENDING/APPROVED/REJECTED)
- property_units.approved_discount_paise (NULLable BigInteger; written only by
  an APPROVED DISCOUNT decision)
- property_units.discount_status (NOT NULL, default 'NONE', check-constrained
  to NONE/PENDING/APPROVED/REJECTED)

Batch mode keeps the ALTER TABLE valid on SQLite (copy-and-move) while
emitting plain ALTER TABLE on PostgreSQL.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAR_REQUEST_VALUES = "('NONE','PENDING','APPROVED','REJECTED')"
DISCOUNT_STATUS_VALUES = "('NONE','PENDING','APPROVED','REJECTED')"


def _add_column_if_missing(batch_op, column: sa.Column) -> None:
    """Add a column only when the physical table lacks it (idempotent guard)."""

    table_name = batch_op.impl.table_name
    existing = {column_info["name"] for column_info in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in existing:
        batch_op.add_column(column)


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch:
        _add_column_if_missing(
            batch,
            sa.Column(
                "car_request_status", sa.String(length=16),
                server_default="NONE", nullable=False,
            ),
        )
        existing_checks = {
            constraint["name"]
            for constraint in sa.inspect(op.get_bind()).get_check_constraints("bookings")
        }
        if "ck_bookings_ck_bookings_car_request_status" not in existing_checks:
            # Name mirrors Base.metadata's convention-formatted rendering of the
            # model constraint (declared name + ck_%(table_name)s_ prefix).
            batch.create_check_constraint(
                "ck_bookings_ck_bookings_car_request_status",
                f"car_request_status IN {CAR_REQUEST_VALUES}",
            )

    with op.batch_alter_table("property_units") as batch:
        _add_column_if_missing(
            batch,
            sa.Column("approved_discount_paise", sa.BigInteger(), nullable=True),
        )
        _add_column_if_missing(
            batch,
            sa.Column(
                "discount_status", sa.String(length=16),
                server_default="NONE", nullable=False,
            ),
        )
        existing_checks = {
            constraint["name"]
            for constraint in sa.inspect(op.get_bind()).get_check_constraints("property_units")
        }
        if "ck_property_units_unit_discount_status_valid" not in existing_checks:
            batch.create_check_constraint(
                "ck_property_units_unit_discount_status_valid",
                f"discount_status IN {DISCOUNT_STATUS_VALUES}",
            )
        if "ck_property_units_unit_approved_discount_positive" not in existing_checks:
            batch.create_check_constraint(
                "ck_property_units_unit_approved_discount_positive",
                "approved_discount_paise IS NULL OR approved_discount_paise > 0",
            )


def downgrade() -> None:
    with op.batch_alter_table("property_units") as batch:
        batch.drop_column("discount_status")
        batch.drop_column("approved_discount_paise")
        batch.drop_constraint(
            "ck_property_units_unit_approved_discount_positive", type_="check"
        )
        batch.drop_constraint(
            "ck_property_units_unit_discount_status_valid", type_="check"
        )

    with op.batch_alter_table("bookings") as batch:
        batch.drop_column("car_request_status")
        batch.drop_constraint(
            "ck_bookings_ck_bookings_car_request_status", type_="check"
        )
