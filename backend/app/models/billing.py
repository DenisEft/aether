"""Billing models: plans, subscriptions, invoices, usage, payment methods."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow
from app.models.enums import InvoiceStatus, SubscriptionStatus, UsagePeriod


class SubscriptionPlan(Base, UUIDPrimaryKey):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Override UUID — text PK
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_monthly_usd: Mapped[float] = mapped_column(Float, default=0.0)
    price_yearly_usd: Mapped[float | None] = mapped_column(Float)
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String, ForeignKey("subscription_plans.id"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(String, default=SubscriptionStatus.active)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    plan: Mapped[SubscriptionPlan] = relationship()


class Invoice(Base, UUIDPrimaryKey):
    __tablename__ = "invoices"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    status: Mapped[InvoiceStatus] = mapped_column(String, default=InvoiceStatus.draft)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoice_pdf_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageRecord(Base, UUIDPrimaryKey):
    __tablename__ = "usage_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    period: Mapped[UsagePeriod] = mapped_column(String, default=UsagePeriod.daily)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentMethod(Base, UUIDPrimaryKey):
    __tablename__ = "payment_methods"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_payment_method_id: Mapped[str] = mapped_column(String, nullable=False)
    last_four: Mapped[str | None] = mapped_column(String)
    card_brand: Mapped[str | None] = mapped_column(String)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
