"""harden sale_bookings.unit_id FK to RESTRICT and lock direct unit bookings

Revision ID: c5d6e7f8a9b0
Revises: c7d8e9f0a1b2
Create Date: 2026-11-22 21:34:46.805119

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    # SQLite cannot ALTER of constraints; use copy-and-move batch mode.
    with op.batch_alter_table('sale_bookings') as batch_op:
        batch_op.drop_constraint(op.f('fk_sale_bookings_unit_id_property_units'), type_='foreignkey')
        batch_op.create_foreign_key(
            op.f('fk_sale_bookings_unit_id_property_units'), 'property_units',
            ['unit_id'], ['id'], ondelete='RESTRICT',
        )


def downgrade() -> None:
    """Revert the migration."""
    with op.batch_alter_table('sale_bookings') as batch_op:
        batch_op.drop_constraint(op.f('fk_sale_bookings_unit_id_property_units'), type_='foreignkey')
        batch_op.create_foreign_key(
            op.f('fk_sale_bookings_unit_id_property_units'), 'property_units',
            ['unit_id'], ['id'], ondelete='SET NULL',
        )
