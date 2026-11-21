"""Tenant API request and response contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.modules.auth.security import validate_password_strength
from app.modules.tenancy.models import TenantStatus


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    brand_name: str
    status: TenantStatus
    plan_id: UUID | None
    logo_path: str | None
    theme_json: dict
    country: str
    timezone: str
    currency: str


class TenantTheme(BaseModel):
    primary: str = "#536B59"
    accent: str = "#C5A77D"
    default_color_scheme: Literal["light", "dark"] = "light"


class TenantSettingsResponse(BaseModel):
    slug: str
    brand_name: str
    logo_path: str | None = None
    theme: TenantTheme = TenantTheme()
    currency: str = "INR"
    timezone: str = "UTC"
    date_format: str = "DD/MM/YYYY"


class TenantSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brand_name: str | None = Field(default=None, min_length=2, max_length=255)
    logo_path: str | None = Field(default=None, max_length=500)
    theme: TenantTheme | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=64)
    date_format: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _at_least_one(self) -> "TenantSettingsUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one setting must be provided.")
        return self


class TenantSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: SecretStr
    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: SecretStr) -> SecretStr:
        validate_password_strength(value.get_secret_value())
        return value
