"""Tenant-scoped persistence for custom roles."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.users.models import CustomRole, User


def get_custom_role(
    session: Session, role_id: UUID, *, tenant_id: UUID
) -> CustomRole | None:
    return session.scalar(
        select(CustomRole).where(
            CustomRole.id == role_id, CustomRole.tenant_id == tenant_id
        )
    )


def get_custom_role_by_name(
    session: Session, name: str, *, tenant_id: UUID
) -> CustomRole | None:
    return session.scalar(
        select(CustomRole).where(
            func.lower(CustomRole.name) == name.strip().lower(),
            CustomRole.tenant_id == tenant_id,
        )
    )


def list_custom_roles(session: Session, *, tenant_id: UUID) -> list[CustomRole]:
    return list(
        session.scalars(
            select(CustomRole)
            .where(CustomRole.tenant_id == tenant_id)
            .order_by(CustomRole.created_at.desc(), CustomRole.id)
        ).all()
    )


def count_custom_role_users(session: Session, role_id: UUID) -> int:
    return session.scalar(
        select(func.count(User.id)).where(User.custom_role_id == role_id)
    ) or 0
