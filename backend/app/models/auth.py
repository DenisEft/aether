"""Auth models: sessions, refresh tokens, magic links, API keys, passkeys, MFA."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, BYTEA, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow


class Session(Base, UUIDPrimaryKey):
    __tablename__ = "sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


class RefreshToken(Base, UUIDPrimaryKey):
    __tablename__ = "refresh_tokens"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str | None] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class MagicLink(Base, UUIDPrimaryKey):
    __tablename__ = "magic_links"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ApiKey(Base, UUIDPrimaryKey):
    __tablename__ = "api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Passkey(Base, UUIDPrimaryKey):
    __tablename__ = "passkeys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    credential_id: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str | None] = mapped_column(String)
    device_type: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class MFAConfig(Base, UUIDPrimaryKey):
    __tablename__ = "mfa_configs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class OAuthState(Base, UUIDPrimaryKey):
    __tablename__ = "oauth_states"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )