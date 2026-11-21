"""omnichannel channels, messages, calls and recordings

Revision ID: c9f1a2b3d4e5
Revises: 3177f6deb62a
Create Date: 2026-11-21 21:41:23.510195

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f1a2b3d4e5'
down_revision: Union[str, None] = '3177f6deb62a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration.

    Idempotent per the repository convention: an interrupted previous run may
    have left some tables behind; existing objects are skipped rather than
    dropped so no data is lost while the schema converges.
    """
    # ### auto-generated, then adjusted: composite tenant_id_id indexes are emitted
    # by app.db.tenancy.after_parent_attach during create_table, so they are not repeated here. ###
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def existing_indexes(table: str) -> set[str]:
        if table not in existing_tables:
            return set()
        return {ix["name"] for ix in inspector.get_indexes(table)}

    def ensure_index(name: str, table: str, columns: list[str], unique: bool = False) -> None:
        if name not in existing_indexes(table):
            op.create_index(name, table, columns, unique=unique)

    if 'channel_credentials' not in existing_tables:
        op.create_table('channel_credentials',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('credentials_ciphertext', sa.Text(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('webhook_verify_token_hash', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint("channel IN ('WEB_CHAT', 'WHATSAPP', 'INSTAGRAM', 'MESSENGER', 'SMS', 'EMAIL', 'VOICE')", name=op.f('ck_channel_credentials_channel')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_channel_credentials_tenant_id_tenants'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_credentials')),
        sa.UniqueConstraint('tenant_id', 'channel', name='uq_channel_credentials_tenant_channel')
        )
    ensure_index('ix_channel_credentials_channel', 'channel_credentials', ['channel'])
    ensure_index('ix_channel_credentials_tenant_id', 'channel_credentials', ['tenant_id'])

    if 'channel_conversations' not in existing_tables:
        op.create_table('channel_conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_to_id', sa.Uuid(), nullable=True),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('external_thread_id', sa.String(length=255), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_handle', sa.String(length=255), nullable=True),
        sa.Column('contact_avatar_url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('last_message_preview', sa.String(length=500), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], name=op.f('fk_channel_conversations_assigned_to_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contact_id'], ['users.id'], name=op.f('fk_channel_conversations_contact_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_channel_conversations_lead_id_leads'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_channel_conversations_tenant_id_tenants'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_conversations')),
        sa.UniqueConstraint('tenant_id', 'channel', 'external_thread_id', name='uq_channel_conversations_thread')
        )
    ensure_index('ix_channel_conversations_assigned_to_id', 'channel_conversations', ['assigned_to_id'])
    ensure_index('ix_channel_conversations_channel', 'channel_conversations', ['channel'])
    ensure_index('ix_channel_conversations_contact_id', 'channel_conversations', ['contact_id'])
    ensure_index('ix_channel_conversations_lead_id', 'channel_conversations', ['lead_id'])
    ensure_index('ix_channel_conversations_status', 'channel_conversations', ['status'])
    ensure_index('ix_channel_conversations_tenant_id', 'channel_conversations', ['tenant_id'])
    ensure_index('ix_channel_conversations_tenant_unread', 'channel_conversations', ['tenant_id', 'unread_count'])
    ensure_index('ix_channel_conversations_tenant_updated', 'channel_conversations', ['tenant_id', 'updated_at'])

    if 'call_records' not in existing_tables:
        op.create_table('call_records',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('conversation_id', sa.Uuid(), nullable=True),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('room_name', sa.String(length=255), nullable=False),
        sa.Column('destination', sa.String(length=255), nullable=True),
        sa.Column('caller_identity', sa.String(length=255), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint("direction IN ('INBOUND', 'OUTBOUND')", name=op.f('ck_call_records_direction')),
        sa.CheckConstraint("status IN ('INITIATED', 'RINGING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'MISSED', 'BUSY')", name=op.f('ck_call_records_status')),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], name=op.f('fk_call_records_agent_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id'], ['channel_conversations.id'], name=op.f('fk_call_records_conversation_id_channel_conversations'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], name=op.f('fk_call_records_lead_id_leads'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_call_records_tenant_id_tenants'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_call_records')),
        sa.UniqueConstraint('tenant_id', 'room_name', name='uq_call_records_room')
        )
    ensure_index('ix_call_records_agent_id', 'call_records', ['agent_id'])
    ensure_index('ix_call_records_lead_id', 'call_records', ['lead_id'])
    ensure_index('ix_call_records_tenant_created', 'call_records', ['tenant_id', 'created_at'])
    ensure_index('ix_call_records_tenant_id', 'call_records', ['tenant_id'])

    if 'channel_messages' not in existing_tables:
        op.create_table('channel_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=True),
        sa.Column('channel', sa.String(length=32), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('external_message_id', sa.String(length=255), nullable=True),
        sa.Column('sender_handle', sa.String(length=255), nullable=True),
        sa.Column('content_type', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(length=1000), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint("direction IN ('INBOUND', 'OUTBOUND')", name=op.f('ck_channel_messages_direction')),
        sa.ForeignKeyConstraint(['conversation_id'], ['channel_conversations.id'], name=op.f('fk_channel_messages_conversation_id_channel_conversations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], name=op.f('fk_channel_messages_sender_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_channel_messages_tenant_id_tenants'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_messages')),
        sa.UniqueConstraint('tenant_id', 'channel', 'external_message_id', name='uq_channel_messages_external_id')
        )
    ensure_index('ix_channel_messages_channel', 'channel_messages', ['channel'])
    ensure_index('ix_channel_messages_conversation_created', 'channel_messages', ['conversation_id', 'created_at'])
    ensure_index('ix_channel_messages_conversation_id', 'channel_messages', ['conversation_id'])
    ensure_index('ix_channel_messages_created_at', 'channel_messages', ['created_at'])
    ensure_index('ix_channel_messages_status', 'channel_messages', ['status'])
    ensure_index('ix_channel_messages_tenant_id', 'channel_messages', ['tenant_id'])

    if 'call_recordings' not in existing_tables:
        op.create_table('call_recordings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('call_id', sa.Uuid(), nullable=False),
        sa.Column('egress_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('storage_url', sa.String(length=1000), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'RECORDING', 'COMPLETED', 'FAILED')", name=op.f('ck_call_recordings_status')),
        sa.CheckConstraint('size_bytes >= 0', name=op.f('ck_call_recordings_size_non_negative')),
        sa.ForeignKeyConstraint(['call_id'], ['call_records.id'], name=op.f('fk_call_recordings_call_id_call_records'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_call_recordings_tenant_id_tenants'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_call_recordings'))
        )
    ensure_index('ix_call_recordings_call_id', 'call_recordings', ['call_id'])
    ensure_index('ix_call_recordings_tenant_id', 'call_recordings', ['tenant_id'])


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index('ix_call_recordings_tenant_id_id', table_name='call_recordings')
    op.drop_index('ix_call_recordings_tenant_id', table_name='call_recordings')
    op.drop_index('ix_call_recordings_call_id', table_name='call_recordings')
    op.drop_table('call_recordings')
    op.drop_index('ix_channel_messages_tenant_id_id', table_name='channel_messages')
    op.drop_index('ix_channel_messages_tenant_id', table_name='channel_messages')
    op.drop_index('ix_channel_messages_status', table_name='channel_messages')
    op.drop_index('ix_channel_messages_created_at', table_name='channel_messages')
    op.drop_index('ix_channel_messages_conversation_created', table_name='channel_messages')
    op.drop_index('ix_channel_messages_conversation_id', table_name='channel_messages')
    op.drop_index('ix_channel_messages_channel', table_name='channel_messages')
    op.drop_table('channel_messages')
    op.drop_index('ix_call_records_tenant_id_id', table_name='call_records')
    op.drop_index('ix_call_records_tenant_created', table_name='call_records')
    op.drop_index('ix_call_records_tenant_id', table_name='call_records')
    op.drop_index('ix_call_records_lead_id', table_name='call_records')
    op.drop_index('ix_call_records_agent_id', table_name='call_records')
    op.drop_table('call_records')
    op.drop_index('ix_channel_conversations_tenant_updated', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_tenant_unread', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_tenant_id_id', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_tenant_id', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_status', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_lead_id', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_contact_id', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_channel', table_name='channel_conversations')
    op.drop_index('ix_channel_conversations_assigned_to_id', table_name='channel_conversations')
    op.drop_table('channel_conversations')
    op.drop_index('ix_channel_credentials_tenant_id_id', table_name='channel_credentials')
    op.drop_index('ix_channel_credentials_tenant_id', table_name='channel_credentials')
    op.drop_index('ix_channel_credentials_channel', table_name='channel_credentials')
    op.drop_table('channel_credentials')
