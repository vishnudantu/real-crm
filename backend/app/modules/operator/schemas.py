"""SaaS operator control-plane contracts."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.modules.auth.security import validate_password_strength
from app.modules.tenancy.models import TenantStatus


class OperatorLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr


class OperatorTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OperatorUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: str
    permissions: list
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class OperatorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: SecretStr
    role: str = Field(default="SUPPORT", pattern=r"^(OWNER|SUPPORT|SALES|DEPLOYER)$")
    permissions: list[str] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def _strong_password(cls, value: SecretStr) -> SecretStr:
        validate_password_strength(value.get_secret_value())
        return value


class OperatorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, pattern=r"^(OWNER|SUPPORT|SALES|DEPLOYER)$")
    permissions: list[str] | None = None
    is_active: bool | None = None


class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    name: str = Field(min_length=2, max_length=255)
    brand_name: str | None = Field(default=None, max_length=255)
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=255)
    admin_password: SecretStr
    country: str = Field(default="IN", min_length=2, max_length=2)
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    plan_id: UUID | None = None

    @field_validator("admin_password")
    @classmethod
    def _strong_password(cls, value: SecretStr) -> SecretStr:
        validate_password_strength(value.get_secret_value())
        return value


class TenantProvisionResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    brand_name: str
    status: TenantStatus
    plan_id: UUID | None
    admin_user_id: UUID
    admin_email: EmailStr


class TenantStatusUpdateRequest(BaseModel):
    status: TenantStatus


class TenantFeatureUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    enabled: bool
    reason: str | None = Field(default=None, max_length=500)


class TenantFeatureEntry(BaseModel):
    feature: str
    label: str
    description: str
    enabled: bool
    source: str
    reason: str | None = None
    updated_at: str | None = None


class TenantOnboardRequest(TenantCreateRequest):
    """One-step onboarding wizard: provision tenant and seed starter flags."""

    plan_code: str | None = None
    enable_omnichannel: bool = False
    enable_calling: bool = False
    enable_connectors: bool = False
    enable_post_sales: bool = False
    embed_url: str | None = Field(default=None, max_length=500)


class TenantDeploymentRequest(BaseModel):
    provider: str = Field(pattern=r"^(railway|render|aws|local|manual)$")
    environment: str = Field(default="production", max_length=64)
    region: str | None = Field(default=None, max_length=64)
    repository_url: str | None = Field(default=None, max_length=500)
    api_base_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class TenantDeploymentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    provider: str
    environment: str
    region: str | None
    status: str
    deployment_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(pattern=r"^[a-z0-9_]+$", max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    price_paise: int = Field(ge=0, description="Monthly price in Indian paise (minor units).")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    max_users: int = Field(default=10, ge=1)
    leads_per_month: int = Field(default=1000, ge=1)
    whatsapp_msgs_per_month: int = Field(default=1000, ge=1)
    features: dict = Field(default_factory=dict)
    is_active: bool = True


class PlanUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    price_paise: int | None = Field(default=None, ge=0)
    max_users: int | None = Field(default=None, ge=1)
    leads_per_month: int | None = Field(default=None, ge=1)
    whatsapp_msgs_per_month: int | None = Field(default=None, ge=1)
    features: dict | None = None
    is_active: bool | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    price_paise: int
    currency: str
    max_users: int
    leads_per_month: int
    whatsapp_msgs_per_month: int
    features: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OperatorAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operator_id: UUID | None
    actor_email: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Tenant config read / patch
# ---------------------------------------------------------------------------


class TenantPlanSummary(BaseModel):
    id: UUID
    code: str
    name: str
    price_paise: int


class TenantBrandingSummary(BaseModel):
    brand_name: str
    logo_path: str | None
    theme_json: dict


class TenantWidgetSummary(BaseModel):
    enabled: bool
    embed_url: str | None


class TenantChannelSummary(BaseModel):
    channel: str
    provider: str
    is_active: bool
    updated_at: datetime | None


class TenantAISummary(BaseModel):
    provider: str | None
    model: str | None
    configured: bool


class TenantFeatureMatrixSummary(BaseModel):
    enabled_count: int
    total_count: int


class TenantCountsSummary(BaseModel):
    users: int
    active_users: int
    leads_total: int
    projects: int
    bookings: int
    open_conversations: int


class TenantConfigResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    country: str
    timezone: str
    currency: str
    plan: TenantPlanSummary | None
    branding: TenantBrandingSummary
    widget: TenantWidgetSummary
    channels: list[TenantChannelSummary]
    ai: TenantAISummary
    features: TenantFeatureMatrixSummary
    counts: TenantCountsSummary


class TenantConfigPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brand_name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = None
    currency: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    theme_json: dict | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        # Always require an IANA-shaped key (Area/Location or UTC).
        if not re.fullmatch(r"(?:[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+)+|UTC)", cleaned):
            raise ValueError(f"Invalid timezone key: {value!r}")
        try:
            ZoneInfo(cleaned)
            return cleaned
        except ZoneInfoNotFoundError:
            # When no IANA database is installed (stripped CI images), fall back
            # to membership in available_timezones() if that set is populated;
            # otherwise accept the syntactically-valid key.
            if available_timezones():
                raise ValueError(f"Unknown timezone: {value!r}") from None
            return cleaned

    @field_validator("currency")
    @classmethod
    def _valid_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("Currency must be an ISO-4217 three-letter code (e.g. INR).")
        return cleaned


# ---------------------------------------------------------------------------
# Usage / health
# ---------------------------------------------------------------------------


class TenantUsageMeter(BaseModel):
    used: int
    limit: int | None
    period_start: str | None
    period_end: str | None
    period_source: str | None


class TenantUsageDailyPoint(BaseModel):
    date: str
    leads: int
    messages_sent: int


class TenantUsageResponse(BaseModel):
    days: int
    meters: dict[str, TenantUsageMeter]
    leads_total: int
    bookings_total: int
    messages_sent_total: int
    active_users: int
    channels_active: int
    series: list[TenantUsageDailyPoint]


class TenantHealthCheck(BaseModel):
    name: str
    state: str  # green | yellow | red
    detail: str


class TenantHealthResponse(BaseModel):
    tenant_id: UUID
    overall: str  # worst state across checks
    checks: list[TenantHealthCheck]


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------


class ImpersonatedUser(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str


class ImpersonationResponse(BaseModel):
    access_token: str
    expires_in: int
    user: ImpersonatedUser


# ---------------------------------------------------------------------------
# Bulk feature update
# ---------------------------------------------------------------------------


class BulkFeatureUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    features: dict[str, bool]
