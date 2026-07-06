"""AI-related Pydantic schemas: intents, entities, models, drivers, knowledge bases."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EntityValueType

# ── Intents ──────────────────────────────────────────────────


class IntentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    category: str = Field(default="other")
    is_builtin: bool = False
    plugin_ids: list[str] = Field(default_factory=list)


class IntentUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    category: str | None = None
    is_builtin: bool | None = None
    plugin_ids: list[str] | None = None


class IntentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    display_name: str
    description: str | None
    category: str
    is_builtin: bool
    plugin_ids: list[str]
    created_at: datetime


class IntentTemplateCreate(BaseModel):
    intent_id: uuid.UUID
    example_text: str = Field(..., min_length=1)
    language: str = "ru"


class IntentTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    intent_id: uuid.UUID
    example_text: str
    language: str
    created_at: datetime


# ── Entity Types ─────────────────────────────────────────────


class EntityTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    value_type: EntityValueType = EntityValueType.string
    pattern: str | None = None
    examples: list[str] = Field(default_factory=list)
    lookup_table: str | None = None


class EntityTypeUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    value_type: EntityValueType | None = None
    pattern: str | None = None
    examples: list[str] | None = None
    lookup_table: str | None = None


class EntityTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    display_name: str
    value_type: str
    pattern: str | None
    examples: list[str]
    lookup_table: str | None
    created_at: datetime


# ── AI Models ────────────────────────────────────────────────


class AIModelCreate(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    capability: str = "chat"
    is_active: bool = True
    default_priority: int = Field(default=0, ge=0)
    config: dict = Field(default_factory=dict)


class AIModelUpdate(BaseModel):
    provider: str | None = None
    display_name: str | None = Field(None, min_length=1, max_length=255)
    capability: str | None = None
    is_active: bool | None = None
    default_priority: int | None = Field(None, ge=0)
    config: dict | None = None


class AIModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    model_id: str
    provider: str
    display_name: str
    capability: str
    is_active: bool
    default_priority: int
    config: dict
    created_at: datetime


# ── Driver Configs ───────────────────────────────────────────


class DriverConfigCreate(BaseModel):
    driver_type: str = Field(..., min_length=1, max_length=255)
    endpoint: str = Field(..., min_length=1)
    config: dict = Field(default_factory=dict)


class DriverConfigUpdate(BaseModel):
    endpoint: str | None = None
    is_healthy: bool | None = None
    error_message: str | None = None
    config: dict | None = None


class DriverConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_type: str
    endpoint: str
    is_healthy: bool
    last_checked_at: datetime | None
    error_message: str | None
    config: dict
    created_at: datetime
    updated_at: datetime


# ── Driver Metrics ───────────────────────────────────────────


class DriverMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_config_id: uuid.UUID
    model_id: str
    requests_total: int
    requests_failed: int
    latency_avg_ms: float | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    recorded_at: datetime


# ── Knowledge Bases ──────────────────────────────────────────


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    embedding_model: str = Field(..., min_length=1)
    vector_dim: int = Field(..., gt=0)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    embedding_model: str | None = None
    document_count: int | None = Field(None, ge=0)
    vector_dim: int | None = Field(None, gt=0)


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    embedding_model: str
    document_count: int
    vector_dim: int
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_url: str | None = Field(None, max_length=2000)
    file_type: str | None = None
    chunk_count: int = Field(default=0, ge=0)
    tokens_total: int | None = None


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    title: str
    content: str
    source_url: str | None
    file_type: str | None
    chunk_count: int
    tokens_total: int | None
    indexed_at: datetime | None
    created_at: datetime
