"""SSO configuration schemas."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class SSOConfigCreate(BaseModel):
    """Create a new SSO configuration."""

    provider: str = Field(..., examples=["OIDC", "SAML"])
    domain: str | None = Field(None, description="Email domain for auto-linking")
    metadata_url: str | None = Field(None, description="OP metadata URL for OIDC")
    client_id: str = Field(..., description="OAuth/OIDC client ID")
    client_secret: str = Field(..., description="OAuth/OIDC client secret")
    is_enabled: bool = Field(default=False)


class SSOConfigUpdate(BaseModel):
    """Update an existing SSO configuration (all fields optional)."""

    provider: str | None = Field(None, examples=["OIDC", "SAML"])
    domain: str | None = Field(None)
    metadata_url: str | None = Field(None)
    client_id: str | None = Field(None)
    client_secret: str | None = Field(None)
    is_enabled: bool | None = Field(None)


class SSOConfigResponse(BaseModel):
    """SSO configuration response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(...)
    tenant_id: uuid.UUID = Field(...)
    provider: str = Field(...)
    domain: str | None = Field(None)
    metadata_url: str | None = Field(None)
    client_id: str = Field(...)
    is_enabled: bool = Field(default=False)
    created_at: datetime = Field(...)
