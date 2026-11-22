"""Pydantic contracts for integration connection administration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetaPageConnectionUpsert(BaseModel):
    """Replace the routing and credentials for a Meta Lead Ads page."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    access_token: str = Field(min_length=1, max_length=4096)
    app_secret: str = Field(min_length=1, max_length=255)
    webhook_verify_token: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool = True


class IntegrationConnectionResponse(BaseModel):
    """Public health and routing fields; secrets are deliberately excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    external_account_id: str
    project_id: UUID | None
    is_active: bool
    connection_status: str
    pending_expires_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderConfigurationResponse(BaseModel):
    """Public configuration status; secret values never leave the backend."""

    provider: str
    mode: str
    configured: bool
    missing: list[str]
    instructions_url: str


class ConnectUrlResponse(BaseModel):
    """The provider authorization URL for a browser-triggered OAuth start."""

    url: str


class MetaPageSelection(BaseModel):
    id: str
    name: str


class MetaPagesResponse(BaseModel):
    connection_id: UUID
    pages: list[MetaPageSelection]


class MetaFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    connection_id: UUID
    page_id: str = Field(min_length=1, max_length=128)
    project_id: UUID
    verify_token: str | None = Field(default=None, min_length=16, max_length=255)


class MetaFinalizeResponse(BaseModel):
    connection: IntegrationConnectionResponse
    webhook_url: str
    webhook_verify_token: str
    subscription_checklist: list[str]


class GoogleFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    connection_id: UUID
    customer_id: str = Field(pattern=r"^\d{10}$")
    project_id: UUID


class GoogleManualConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    developer_token: str = Field(min_length=1, max_length=255)
    refresh_token: str = Field(min_length=1, max_length=4096)
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str = Field(min_length=1, max_length=255)
    customer_id: str = Field(pattern=r"^\d{10}$")
    project_id: UUID


class ConnectionStatusResponse(BaseModel):
    connection_id: UUID
    provider: str
    configured: bool
    health: str
    missing: list[str]
    last_success_at: datetime | None
    last_error: str | None


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
