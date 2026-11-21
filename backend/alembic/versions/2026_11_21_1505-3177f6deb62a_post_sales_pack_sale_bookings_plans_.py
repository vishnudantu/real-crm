"""post-sales pack: sale bookings, plans, installments, receipts, brokers

Revision ID: 3177f6deb62a
Revises: e8f2a3b4c5d6
Create Date: 2026-11-21 15:05:34.939570

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3177f6deb62a'
down_revision: Union[str, None] = 'e8f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    # ### auto-generated, then adjusted: composite tenant_id_id indexes are emitted
    # by app.db.tenancy.after_parent_attach during create_table, so they are not repeated here. ###
    op.create_table('sale_bookings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('lead_id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('unit_number', sa.String(length=64), nullable=False),
    sa.Column('configuration', sa.String(length=100), nullable=True),
    sa.Column('carpet_area_sqft', sa.Integer(), nullable=True),
    sa.Column('consideration_paise', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=24), server_default='BOOKED', nullable=False),
    sa.Column('booked_on', sa.Date(), nullable=False),
    sa.Column('agreement_date', sa.Date(), nullable=True),
    sa.Column('expected_possession', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('consideration_paise >= 0', name=op.f('ck_sale_bookings_consideration_non_negative')),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_sale_bookings_customer_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_sale_bookings_lead_id_leads'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_sale_bookings_project_id_projects'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_sale_bookings_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sale_bookings'))
    )
    op.create_index(op.f('ix_sale_bookings_customer_id'), 'sale_bookings', ['customer_id'], unique=False)
    op.create_index(op.f('ix_sale_bookings_lead_id'), 'sale_bookings', ['lead_id'], unique=False)
    op.create_index(op.f('ix_sale_bookings_project_id'), 'sale_bookings', ['project_id'], unique=False)
    op.create_index(op.f('ix_sale_bookings_tenant_id'), 'sale_bookings', ['tenant_id'], unique=False)
    op.create_index('ix_sale_bookings_tenant_lead', 'sale_bookings', ['tenant_id', 'lead_id'], unique=True)
    op.create_index('ix_sale_bookings_tenant_status', 'sale_bookings', ['tenant_id', 'status'], unique=False)
    op.create_table('broker_commissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sale_booking_id', sa.Uuid(), nullable=False),
    sa.Column('broker_name', sa.String(length=255), nullable=False),
    sa.Column('broker_phone', sa.String(length=32), nullable=True),
    sa.Column('basis', sa.JSON(), nullable=False),
    sa.Column('amount_paise', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('amount_paise >= 0', name=op.f('ck_broker_commissions_commission_amount_non_negative')),
    sa.ForeignKeyConstraint(['sale_booking_id'], ['sale_bookings.id'], name=op.f('fk_broker_commissions_sale_booking_id_sale_bookings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_broker_commissions_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_broker_commissions'))
    )
    op.create_index(op.f('ix_broker_commissions_sale_booking_id'), 'broker_commissions', ['sale_booking_id'], unique=False)
    op.create_index(op.f('ix_broker_commissions_tenant_id'), 'broker_commissions', ['tenant_id'], unique=False)
    op.create_index('ix_broker_commissions_tenant_status', 'broker_commissions', ['tenant_id', 'status'], unique=False)
    op.create_table('payment_plans',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sale_booking_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('plan_type', sa.String(length=24), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("plan_type IN ('CONSTRUCTION_LINKED','TIME_LINKED','HYBRID')", name=op.f('ck_payment_plans_plan_type_valid')),
    sa.ForeignKeyConstraint(['sale_booking_id'], ['sale_bookings.id'], name=op.f('fk_payment_plans_sale_booking_id_sale_bookings'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_payment_plans_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_plans'))
    )
    op.create_index('ix_payment_plans_booking', 'payment_plans', ['sale_booking_id'], unique=False)
    op.create_index(op.f('ix_payment_plans_tenant_id'), 'payment_plans', ['tenant_id'], unique=False)
    op.create_table('installments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=False),
    sa.Column('sequence_no', sa.Integer(), nullable=False),
    sa.Column('milestone', sa.String(length=160), nullable=False),
    sa.Column('amount_paise', sa.BigInteger(), nullable=False),
    sa.Column('due_on', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
    sa.Column('demand_letter_sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('amount_paise >= 0', name=op.f('ck_installments_installment_amount_non_negative')),
    sa.ForeignKeyConstraint(['plan_id'], ['payment_plans.id'], name=op.f('fk_installments_plan_id_payment_plans'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_installments_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_installments')),
    sa.UniqueConstraint('plan_id', 'sequence_no', name='uq_installments_plan_sequence')
    )
    op.create_index(op.f('ix_installments_due_on'), 'installments', ['due_on'], unique=False)
    op.create_index(op.f('ix_installments_tenant_id'), 'installments', ['tenant_id'], unique=False)
    op.create_index('ix_installments_tenant_status_due', 'installments', ['tenant_id', 'status', 'due_on'], unique=False)
    op.create_table('receipts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('installment_id', sa.Uuid(), nullable=False),
    sa.Column('receipt_number', sa.String(length=64), nullable=False),
    sa.Column('amount_paise', sa.BigInteger(), nullable=False),
    sa.Column('channel', sa.String(length=24), nullable=False),
    sa.Column('reference', sa.String(length=160), nullable=True),
    sa.Column('received_by_id', sa.Uuid(), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('amount_paise > 0', name=op.f('ck_receipts_receipt_amount_positive')),
    sa.ForeignKeyConstraint(['installment_id'], ['installments.id'], name=op.f('fk_receipts_installment_id_installments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['received_by_id'], ['users.id'], name=op.f('fk_receipts_received_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_receipts_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_receipts')),
    sa.UniqueConstraint('tenant_id', 'receipt_number', name='uq_receipts_tenant_number')
    )
    op.create_index(op.f('ix_receipts_installment_id'), 'receipts', ['installment_id'], unique=False)
    op.create_index(op.f('ix_receipts_tenant_id'), 'receipts', ['tenant_id'], unique=False)
    op.create_index('ix_receipts_tenant_paid_at', 'receipts', ['tenant_id', 'paid_at'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Revert the migration."""
    # ### auto-generated, then adjusted: composite tenant_id_id indexes are emitted
    # by app.db.tenancy.after_parent_attach during create_table, so they are not repeated here. ###
    op.drop_index('ix_receipts_tenant_paid_at', table_name='receipts')
    op.drop_index('ix_receipts_tenant_id_id', table_name='receipts')
    op.drop_index(op.f('ix_receipts_tenant_id'), table_name='receipts')
    op.drop_index(op.f('ix_receipts_installment_id'), table_name='receipts')
    op.drop_table('receipts')
    op.drop_index('ix_installments_tenant_status_due', table_name='installments')
    op.drop_index('ix_installments_tenant_id_id', table_name='installments')
    op.drop_index(op.f('ix_installments_tenant_id'), table_name='installments')
    op.drop_index(op.f('ix_installments_due_on'), table_name='installments')
    op.drop_table('installments')
    op.drop_index('ix_payment_plans_tenant_id_id', table_name='payment_plans')
    op.drop_index(op.f('ix_payment_plans_tenant_id'), table_name='payment_plans')
    op.drop_index('ix_payment_plans_booking', table_name='payment_plans')
    op.drop_table('payment_plans')
    op.drop_index('ix_broker_commissions_tenant_status', table_name='broker_commissions')
    op.drop_index('ix_broker_commissions_tenant_id_id', table_name='broker_commissions')
    op.drop_index(op.f('ix_broker_commissions_tenant_id'), table_name='broker_commissions')
    op.drop_index(op.f('ix_broker_commissions_sale_booking_id'), table_name='broker_commissions')
    op.drop_table('broker_commissions')
    op.drop_index('ix_sale_bookings_tenant_status', table_name='sale_bookings')
    op.drop_index('ix_sale_bookings_tenant_lead', table_name='sale_bookings')
    op.drop_index('ix_sale_bookings_tenant_id_id', table_name='sale_bookings')
    op.drop_index(op.f('ix_sale_bookings_tenant_id'), table_name='sale_bookings')
    op.drop_index(op.f('ix_sale_bookings_project_id'), table_name='sale_bookings')
    op.drop_index(op.f('ix_sale_bookings_lead_id'), table_name='sale_bookings')
    op.drop_index(op.f('ix_sale_bookings_customer_id'), table_name='sale_bookings')
    op.drop_table('sale_bookings')
    # ### end Alembic commands ###
