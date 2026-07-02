"""Tenants, organisations, and tenant configuration models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow

if TYPE_CHECKING:
    from app.models.documents import Document


class Tenant(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, unique=True)
    logo_url: Mapped[str | None] = mapped_column(String)
    primary_color: Mapped[str] = mapped_column(String, default="#1a73e8")
    timezone: Mapped[str] = mapped_column(String, default="UTC")
    locale: Mapped[str] = mapped_column(String, default="ru")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    organisations: Mapped[list["Organisation"]] = relationship(back_populates="tenant")
    channels: Mapped[list["Channel"]] = relationship(back_populates="tenant")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="tenant")
    documents: Mapped[list["Document"]] = relationship(back_populates="tenant")


class TenantConfig(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenant_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    tenant: Mapped["Tenant"] = relationship()


class TenantFeature(Base, UUIDPrimaryKey):
    __tablename__ = "tenant_features"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class TenantLimit(Base, UUIDPrimaryKey):
    __tablename__ = "tenant_limits"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    limit_key: Mapped[str] = mapped_column(String, nullable=False)
    hard_limit: Mapped[int] = mapped_column(Integer)
    soft_limit: Mapped[int] = mapped_column(Integer, default=0)
    current_value: Mapped[int] = mapped_column(Integer, default=0)


class TenantDomain(Base, UUIDPrimaryKey):
    __tablename__ = "tenant_domains"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[str | None] = mapped_column(String)  # timestamptz as text for simplicity
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
