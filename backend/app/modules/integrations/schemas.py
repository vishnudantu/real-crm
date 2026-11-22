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
    project_id: UUID
    is_active: bool
    last_success_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime
