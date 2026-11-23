"""custom role designer and user custom-role assignments

Revision ID: d4e6a8b2c1f3
Revises: c3a7f1d9e2b5
Create Date: 2026-11-23 13:00:00

Additive, idempotent, and batch-safe on SQLite. No built-in role is inserted
into custom_roles; custom rows are always tenant-owned and is_builtin=false.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e6a8b2c1f3"
down_revision: Union[str, None] = "c3a7f1d9e2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector, table: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table)}


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if name not in _index_names(inspector, table):
        op.create_index(name, table, columns, unique=False)


def _ensure_user_custom_role_fk() -> None:
    inspector = sa.inspect(op.get_bind())
    foreign_keys = inspector.get_foreign_keys("users")
    if not any(
        foreign_key.get("referred_table") == "custom_roles"
        and foreign_key.get("constrained_columns") == ["custom_role_id"]
        for foreign_key in foreign_keys
    ):
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_foreign_key(
                op.f("fk_users_custom_role_id_custom_roles"),
                "custom_roles", ["custom_role_id"], ["id"], ondelete="RESTRICT",
            )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "custom_roles" not in inspector.get_table_names():
        op.create_table(
            "custom_roles",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("is_builtin", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_custom_roles_tenant_id_tenants"), ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"], ["users.id"],
                name=op.f("fk_custom_roles_created_by_users"), ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_roles")),
            sa.UniqueConstraint(
                "tenant_id", "name", name="uq_custom_roles_tenant_id_name"
            ),
        )
        op.create_index(op.f("ix_custom_roles_tenant_id"), "custom_roles", ["tenant_id"])
        op.create_index(op.f("ix_custom_roles_created_by"), "custom_roles", ["created_by"])
    else:
        _create_index_if_missing(op.f("ix_custom_roles_tenant_id"), "custom_roles", ["tenant_id"])
        _create_index_if_missing(op.f("ix_custom_roles_created_by"), "custom_roles", ["created_by"])

    # The ORM's TenantOwned listener creates this composite metadata index;
    # migrations create it explicitly because DDL does not emit ORM listeners.
    _create_index_if_missing(
        "ix_custom_roles_tenant_id_id", "custom_roles", ["tenant_id", "id"]
    )

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "custom_role_id" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("custom_role_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                op.f("fk_users_custom_role_id_custom_roles"),
                "custom_roles", ["custom_role_id"], ["id"], ondelete="RESTRICT",
            )
            batch_op.create_index(
                op.f("ix_users_custom_role_id"), ["custom_role_id"], unique=False
            )
    else:
        _create_index_if_missing(op.f("ix_users_custom_role_id"), "users", ["custom_role_id"])
    _ensure_user_custom_role_fk()


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "custom_role_id" in {column["name"] for column in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_index(op.f("ix_users_custom_role_id"))
            batch_op.drop_constraint(
                op.f("fk_users_custom_role_id_custom_roles"), type_="foreignkey"
            )
            batch_op.drop_column("custom_role_id")

    inspector = sa.inspect(op.get_bind())
    if "custom_roles" in inspector.get_table_names():
        for name in (
            "ix_custom_roles_tenant_id_id",
            op.f("ix_custom_roles_created_by"),
            op.f("ix_custom_roles_tenant_id"),
        ):
            if name in _index_names(inspector, "custom_roles"):
                op.drop_index(name, table_name="custom_roles")
        op.drop_table("custom_roles")
