"""Channel models: channels, credentials, usage."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow
from app.models.enums import ChannelTypeEnum, CredentialTypeEnum


class Channel(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "channels"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    channel_type: Mapped[ChannelTypeEnum] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    tenant: Mapped[Tenant] = relationship(back_populates="channels")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="channel")


class ChannelCredential(Base, UUIDPrimaryKey):
    __tablename__ = "channel_credentials"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    credential_type: Mapped[CredentialTypeEnum] = mapped_column(String, nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChannelUsage(Base, UUIDPrimaryKey):
    __tablename__ = "channel_usage"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    messages_in: Mapped[int] = mapped_column(Integer, default=0)
    messages_out: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    latency_avg_ms: Mapped[float | None] = mapped_column
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
