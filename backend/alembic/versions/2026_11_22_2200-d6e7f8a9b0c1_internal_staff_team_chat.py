"""teamchat: internal staff channels and messages (canonical-schema aware)

Revision ID: d6e7f8a9b0c1
Revises: c6d7e8f9a0b1
Create Date: 2026-11-22 22:00:00

The team_channels/team_channel_members/team_messages tables may already exist
from the earlier staff-chat rollout (canonical schema: topic/kind/is_general,
author_user_id, mentions, last_read_at). This migration is therefore
idempotent:

- On a database that already has the tables, it only ADDS the missing
  ``is_private`` column to ``team_channels`` (guarded by a column-existence
  check) and otherwise leaves the canonical schema untouched.
- On a truly fresh database with none of the tables, it creates the canonical
  schema from scratch (including is_private), so a fresh install converges to
  the same shape.

Downgrade removes only the column this migration adds; it never drops the
shared tables (a fresh-DB teardown of the tables happens in the migration that
originally created them, or is intentionally out of scope here to protect the
canonical rollout's data).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables_present(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _columns_present(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _tables_present(inspector)

    if "team_channels" in tables:
        # Canonical rollout exists: only add the missing is_private column.
        if "team_channels" in tables:
            columns = _columns_present(inspector, "team_channels")
            if "is_private" not in columns:
                with op.batch_alter_table("team_channels") as batch_op:
                    batch_op.add_column(
                        sa.Column("is_private", sa.Boolean(), server_default="false", nullable=False)
                    )
        # members/messages tables are part of the canonical rollout; nothing to do.
        return

    # Fresh database: create the canonical schema from scratch.
    inspector = sa.inspect(bind)
    tables = _tables_present(inspector)
    if "team_channels" not in tables:
        op.create_table(
            "team_channels",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("topic", sa.String(length=500), nullable=True),
            sa.Column("kind", sa.String(length=16), server_default="CHANNEL", nullable=False),
            sa.Column("is_general", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("is_private", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_team_channels_created_by_users"), ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_channels_tenant_id_tenants"), ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_team_channels")),
            sa.UniqueConstraint("tenant_id", "name", name="uq_team_channels_tenant_name"),
        )
        op.create_index(op.f("ix_team_channels_tenant_id"), "team_channels", ["tenant_id"], unique=False)
        op.create_index("ix_team_channels_tenant_kind", "team_channels", ["tenant_id", "kind"], unique=False)

    inspector = sa.inspect(bind)
    tables = _tables_present(inspector)
    if "team_channel_members" not in tables:
        op.create_table(
            "team_channel_members",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("channel_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(length=16), server_default="MEMBER", nullable=False),
            sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["channel_id"], ["team_channels.id"], name=op.f("fk_team_channel_members_channel_id_team_channels"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_team_channel_members_user_id_users"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_channel_members_tenant_id_tenants"), ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_team_channel_members")),
            sa.UniqueConstraint("tenant_id", "channel_id", "user_id", name="uq_team_channel_members_tenant_channel_user"),
            sa.CheckConstraint("role IN ('OWNER','MODERATOR','MEMBER')", name="team_channel_member_role_valid"),
        )
        op.create_index(op.f("ix_team_channel_members_tenant_id"), "team_channel_members", ["tenant_id"], unique=False)
        op.create_index("ix_team_channel_members_user_channel", "team_channel_members", ["tenant_id", "user_id", "channel_id"], unique=False)

    inspector = sa.inspect(bind)
    tables = _tables_present(inspector)
    if "team_messages" not in tables:
        op.create_table(
            "team_messages",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("channel_id", sa.Uuid(), nullable=False),
            sa.Column("author_user_id", sa.Uuid(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("mentions", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(["channel_id"], ["team_channels.id"], name=op.f("fk_team_messages_channel_id_team_channels"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], name=op.f("fk_team_messages_author_user_id_users"), ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_team_messages_tenant_id_tenants"), ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_team_messages")),
        )
        op.create_index(op.f("ix_team_messages_tenant_id"), "team_messages", ["tenant_id"], unique=False)
        op.create_index("ix_team_messages_tenant_channel_created", "team_messages", ["tenant_id", "channel_id", "created_at"], unique=False)


def downgrade() -> None:
    """Remove only what this migration adds: the is_private column.

    The tables themselves belong to the canonical staff-chat rollout and are
    intentionally preserved on downgrade to protect existing chat history.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _tables_present(inspector)
    if "team_channels" in tables and "is_private" in _columns_present(inspector, "team_channels"):
        with op.batch_alter_table("team_channels") as batch_op:
            batch_op.drop_column("is_private")
