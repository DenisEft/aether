"""AI models: intents, entities, AI config, knowledge bases."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow
from app.models.enums import EntityValueType


class Intent(Base, UUIDPrimaryKey):
    __tablename__ = "intents"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String, default="other")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    plugin_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntentTemplate(Base, UUIDPrimaryKey):
    __tablename__ = "intent_templates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    intent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intents.id", ondelete="CASCADE"), nullable=False
    )
    example_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EntityType(Base, UUIDPrimaryKey):
    __tablename__ = "entity_types"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    value_type: Mapped[EntityValueType] = mapped_column(String, default=EntityValueType.string)
    pattern: Mapped[str | None] = mapped_column(String)
    examples: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    lookup_table: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIModel(Base, UUIDPrimaryKey):
    __tablename__ = "ai_models"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    capability: Mapped[str] = mapped_column(String, default="chat")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_priority: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DriverConfig(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "driver_configs"

    driver_type: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class DriverMetric(Base, UUIDPrimaryKey):
    __tablename__ = "driver_metrics"

    driver_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("driver_configs.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    requests_total: Mapped[int] = mapped_column(Integer, default=0)
    requests_failed: Mapped[int] = mapped_column(Integer, default=0)
    latency_avg_ms: Mapped[float | None] = mapped_column(Float)
    tokens_in: Mapped[int] = mapped_column(BIGINT, default=0)
    tokens_out: Mapped[int] = mapped_column(BIGINT, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeBase(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "knowledge_bases"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_dim: Mapped[int] = mapped_column(Integer, nullable=False)


class KnowledgeDocument(Base, UUIDPrimaryKey):
    __tablename__ = "knowledge_documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_total: Mapped[int | None] = mapped_column(Integer)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
