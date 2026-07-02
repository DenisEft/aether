"""Service-related Pydantic schemas: definitions, instances, bindings, executions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExecutionResult


# ── Service Definitions ─────────────────────────────────────

class ServiceDefinitionCreate(BaseModel):
    plugin_id: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    version: str = "1.0.0"
    is_builtin: bool = False
    is_active: bool = True
    capabilities: list[str] = Field(default_factory=list)
    config_schema: dict = Field(default_factory=dict)


class ServiceDefinitionUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    version: str | None = None
    is_builtin: bool | None = None
    is_active: bool | None = None
    capabilities: list[str] | None = None
    config_schema: dict | None = None


class ServiceDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plugin_id: str
    display_name: str
    description: str | None
    version: str
    is_builtin: bool
    is_active: bool
    capabilities: list[str]
    config_schema: dict
    created_at: datetime
    updated_at: datetime


# ── Service Instances ────────────────────────────────────────

class ServiceInstanceCreate(BaseModel):
    service_definition_id: uuid.UUID
    config: dict = Field(default_factory=dict)
    is_active: bool = True


class ServiceInstanceUpdate(BaseModel):
    config: dict | None = None
    is_active: bool | None = None


class ServiceInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    service_definition_id: uuid.UUID
    config: dict
    is_active: bool
    installed_at: datetime
    updated_at: datetime


# ── Service Bindings ─────────────────────────────────────────

class ServiceBindingCreate(BaseModel):
    service_instance_id: uuid.UUID
    channel_id: uuid.UUID | None = None
    priority: int = Field(default=0, ge=0)


class ServiceBindingUpdate(BaseModel):
    channel_id: uuid.UUID | None = None
    priority: int | None = Field(None, ge=0)


class ServiceBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    service_instance_id: uuid.UUID
    channel_id: uuid.UUID | None
    priority: int
    created_at: datetime


# ── Service Executions ───────────────────────────────────────

class ServiceExecutionCreate(BaseModel):
    service_instance_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    intent: str | None = None
    entities: dict | None = None


class ServiceExecutionUpdate(BaseModel):
    result: ExecutionResult | None = None
    response_text: str | None = None
    duration_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    error_message: str | None = None


class ServiceExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    service_instance_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    intent: str | None
    entities: dict | None
    result: str
    response_text: str | None
    duration_ms: int | None
    tokens_used: int | None
    cost_usd: float | None
    error_message: str | None
    created_at: datetime
