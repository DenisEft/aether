"""Tenant-related Pydantic schemas (admin endpoints)."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

# ── Tenants ─────────────────────────────────────────────────


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=2000)
    primary_color: str = Field(default="#1a73e8", pattern=r"^#[0-9a-fA-F]{6}$")
    timezone: str = Field(default="UTC", max_length=100)
    locale: str = Field(default="ru", max_length=10)
    settings: dict = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    domain: str | None = Field(None, max_length=255)
    logo_url: str | None = Field(None, max_length=2000)
    primary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    timezone: str | None = Field(None, max_length=100)
    locale: str | None = Field(None, max_length=10)
    is_active: bool | None = None
    settings: dict | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    domain: str | None
    logo_url: str | None
    primary_color: str
    timezone: str
    locale: str
    is_active: bool
    settings: dict
    created_at: datetime
    updated_at: datetime


# ── Tenant Configs ───────────────────────────────────────────


class TenantConfigCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    description: str | None = Field(None, max_length=1000)


class TenantConfigUpdate(BaseModel):
    value: str | None = Field(None, min_length=1)
    description: str | None = Field(None, max_length=1000)


class TenantConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    key: str
    value: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ── Tenant Features ──────────────────────────────────────────


class TenantFeatureCreate(BaseModel):
    feature_key: str = Field(..., min_length=1, max_length=255)
    is_enabled: bool = True
    config: dict = Field(default_factory=dict)


class TenantFeatureUpdate(BaseModel):
    is_enabled: bool | None = None
    config: dict | None = None


class TenantFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    feature_key: str
    is_enabled: bool
    config: dict
    created_at: datetime


# ── Tenant Limits ────────────────────────────────────────────


class TenantLimitCreate(BaseModel):
    limit_key: str = Field(..., min_length=1, max_length=255)
    hard_limit: int = Field(..., ge=0)
    soft_limit: int = Field(default=0, ge=0)
    current_value: int = Field(default=0, ge=0)


class TenantLimitUpdate(BaseModel):
    hard_limit: int | None = Field(None, ge=0)
    soft_limit: int | None = Field(None, ge=0)
    current_value: int | None = Field(None, ge=0)


class TenantLimitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    limit_key: str
    hard_limit: int
    soft_limit: int
    current_value: int


# ── Tenant Domains ───────────────────────────────────────────


class TenantDomainCreate(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    ssl_enabled: bool = False


class TenantDomainUpdate(BaseModel):
    is_verified: bool | None = None
    verified_at: str | None = None
    ssl_enabled: bool | None = None


class TenantDomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    domain: str
    is_verified: bool
    verified_at: str | None
    ssl_enabled: bool
