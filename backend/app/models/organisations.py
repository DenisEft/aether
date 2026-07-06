"""Organisation model (separate from tenants to avoid circular imports)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Organisation(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "organisations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String)

    tenant: Mapped[Tenant] = relationship(back_populates="organisations")
    memberships: Mapped[list[Membership]] = relationship(back_populates="organisation")
