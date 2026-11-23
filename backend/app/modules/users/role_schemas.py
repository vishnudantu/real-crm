"""API contracts for the permission registry and tenant custom roles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.users.permissions import validate_permissions


class CustomRoleBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Role name must contain at least two characters.")
        return normalized

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, value: list[str]) -> list[str]:
        try:
            return validate_permissions(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class CustomRoleCreateRequest(CustomRoleBase):
    """A new tenant role with only grantable registry permissions."""


class CustomRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = Field(default=None, max_length=32)
    is_builtin: bool | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("permissions")
    @classmethod
    def _validate_permissions(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        try:
            return validate_permissions(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _validate_update(self) -> "CustomRoleUpdateRequest":
        if "is_builtin" in self.model_fields_set:
            raise ValueError("Built-in role status cannot be changed.")
        editable = {"name", "description", "permissions"} & self.model_fields_set
        if not editable:
            raise ValueError("At least one editable field must be provided.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null.")
        if "permissions" in self.model_fields_set and self.permissions is None:
            raise ValueError("permissions cannot be null.")
        return self


class CustomRoleResponse(CustomRoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    is_builtin: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class CustomRoleListResponse(BaseModel):
    items: list[CustomRoleResponse]
    total: int


class PermissionResponse(BaseModel):
    key: str
    area: str
    description: str
    grantable: bool
    enabled: bool


class PermissionListResponse(BaseModel):
    items: list[PermissionResponse]
    total: int
