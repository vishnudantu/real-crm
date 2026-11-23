"""Business rules for tenant-owned custom roles."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users import role_repository
from app.modules.users.models import CustomRole, User
from app.modules.users.role_schemas import (
    CustomRoleCreateRequest,
    CustomRoleUpdateRequest,
)


def _duplicate_name() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A custom role with this name already exists.",
    )


def _get_role_for_write(
    session: Session, role_id: UUID, *, tenant_id: UUID
) -> CustomRole:
    role = role_repository.get_custom_role(session, role_id, tenant_id=tenant_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom role not found.")
    if role.is_builtin:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Built-in roles cannot be edited."
        )
    return role


def create_custom_role(
    session: Session, *, actor: User, payload: CustomRoleCreateRequest
) -> CustomRole:
    if role_repository.get_custom_role_by_name(
        session, payload.name, tenant_id=actor.tenant_id
    ):
        raise _duplicate_name()
    role = CustomRole(
        tenant_id=actor.tenant_id,
        name=payload.name,
        description=payload.description,
        permissions=list(payload.permissions),
        is_builtin=False,
        created_by=actor.id,
    )
    session.add(role)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _duplicate_name() from None
    session.refresh(role)
    return role


def list_custom_roles(session: Session, *, actor: User) -> list[CustomRole]:
    return role_repository.list_custom_roles(session, tenant_id=actor.tenant_id)


def update_custom_role(
    session: Session,
    *,
    actor: User,
    role_id: UUID,
    payload: CustomRoleUpdateRequest,
) -> CustomRole:
    role = _get_role_for_write(session, role_id, tenant_id=actor.tenant_id)
    if payload.name is not None:
        existing = role_repository.get_custom_role_by_name(
            session, payload.name, tenant_id=actor.tenant_id
        )
        if existing is not None and existing.id != role.id:
            raise _duplicate_name()
        role.name = payload.name
    if "description" in payload.model_fields_set:
        role.description = payload.description
    if payload.permissions is not None:
        role.permissions = list(payload.permissions)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _duplicate_name() from None
    session.refresh(role)
    return role


def delete_custom_role(
    session: Session, *, actor: User, role_id: UUID
) -> None:
    role = _get_role_for_write(session, role_id, tenant_id=actor.tenant_id)
    if role_repository.count_custom_role_users(session, role.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This role is assigned to users and cannot be deleted.",
        )
    session.delete(role)
    session.commit()
