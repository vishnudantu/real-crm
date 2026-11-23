"""Admin-only custom role designer and permission registry endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.users import role_service
from app.modules.users.permissions import (
    INVENTORY_HOLDS,
    INVENTORY_READ,
    INVENTORY_WRITE,
    PERMISSIONS,
)
from app.modules.users.role_schemas import (
    CustomRoleCreateRequest,
    CustomRoleListResponse,
    CustomRoleResponse,
    CustomRoleUpdateRequest,
    PermissionListResponse,
    PermissionResponse,
)

router = APIRouter(prefix="/roles", tags=["custom roles"])

# Only these registry entries currently replace a router's legacy role gate.
# Other grantable keys are preparatory UI metadata, not access grants yet.
PILOT_PERMISSIONS = frozenset({INVENTORY_READ, INVENTORY_WRITE, INVENTORY_HOLDS})


@router.get("/permissions", response_model=PermissionListResponse)
def get_permission_registry(_: AdminUser) -> PermissionListResponse:
    items = [
        PermissionResponse(
            key=item.key,
            area=item.area,
            description=item.description,
            grantable=item.grantable,
            enabled=item.key in PILOT_PERMISSIONS,
        )
        for item in sorted(PERMISSIONS, key=lambda entry: (entry.area, entry.key))
    ]
    return PermissionListResponse(items=items, total=len(items))


@router.get("/custom", response_model=CustomRoleListResponse)
def list_roles(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CustomRoleListResponse:
    items = role_service.list_custom_roles(db, actor=admin)
    return CustomRoleListResponse(items=items, total=len(items))


@router.post(
    "/custom", response_model=CustomRoleResponse, status_code=status.HTTP_201_CREATED
)
def create_role(
    payload: CustomRoleCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CustomRoleResponse:
    return role_service.create_custom_role(db, actor=admin, payload=payload)


@router.patch("/custom/{role_id}", response_model=CustomRoleResponse)
def update_role(
    role_id: UUID,
    payload: CustomRoleUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> CustomRoleResponse:
    return role_service.update_custom_role(
        db, actor=admin, role_id=role_id, payload=payload
    )


@router.delete("/custom/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    role_service.delete_custom_role(db, actor=admin, role_id=role_id)
