"""teamchat: tenant-scoped staff channels, direct messages and read cursors

Revision ID: d5e6f7a8b9c0
Revises: c6d7e8f9a0b1
Create Date: 2026-11-22 19:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create private staff chat tables.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "team_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=True),
        sa.Column("kind", sa.String(length=16), server_default="CHANNEL", nullable=False),
        sa.Column("is_general", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_team_channels_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_channels_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_channels")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_team_channels_tenant_name"),
    )
    op.create_index(op.f("ix_team_channels_tenant_id"), "team_channels", ["tenant_id"], unique=False)
    op.create_index("ix_team_channels_tenant_kind", "team_channels", ["tenant_id", "kind"], unique=False)

    op.create_table(
        "team_channel_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="MEMBER", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("role IN ('OWNER','MODERATOR','MEMBER')", name=op.f("ck_team_channel_members_team_channel_member_role_valid")),
        sa.ForeignKeyConstraint(["channel_id"], ["team_channels.id"], name=op.f("fk_team_channel_members_channel_id_team_channels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_team_channel_members_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_channel_members_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_channel_members")),
        sa.UniqueConstraint("tenant_id", "channel_id", "user_id", name="uq_team_channel_members_tenant_channel_user"),
    )
    op.create_index(op.f("ix_team_channel_members_tenant_id"), "team_channel_members", ["tenant_id"], unique=False)
    op.create_index("ix_team_channel_members_user_channel", "team_channel_members", ["tenant_id", "user_id", "channel_id"], unique=False)

    op.create_table(
        "team_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("mentions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 4000", name=op.f("ck_team_messages_team_message_body_valid")),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], name=op.f("fk_team_messages_author_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["team_channels.id"], name=op.f("fk_team_messages_channel_id_team_channels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_messages_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_messages")),
    )
    op.create_index(op.f("ix_team_messages_tenant_id"), "team_messages", ["tenant_id"], unique=False)
    op.create_index("ix_team_messages_tenant_channel_created", "team_messages", ["tenant_id", "channel_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_team_messages_tenant_channel_created", table_name="team_messages")
    op.drop_index(op.f("ix_team_messages_tenant_id"), table_name="team_messages")
    op.drop_index("ix_team_messages_tenant_id_id", table_name="team_messages")
    op.drop_table("team_messages")

    op.drop_index("ix_team_channel_members_user_channel", table_name="team_channel_members")
    op.drop_index(op.f("ix_team_channel_members_tenant_id"), table_name="team_channel_members")
    op.drop_index("ix_team_channel_members_tenant_id_id", table_name="team_channel_members")
    op.drop_table("team_channel_members")

    op.drop_index("ix_team_channels_tenant_kind", table_name="team_channels")
    op.drop_index(op.f("ix_team_channels_tenant_id"), table_name="team_channels")
    op.drop_index("ix_team_channels_tenant_id_id", table_name="team_channels")
    op.drop_table("team_channels")
