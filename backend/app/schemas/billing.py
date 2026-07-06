"""Billing-related Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InvoiceStatus, SubscriptionStatus, UsagePeriod

# ── Subscription Plans ───────────────────────────────────────


class SubscriptionPlanCreate(BaseModel):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    price_monthly_usd: float = Field(default=0.0, ge=0)
    price_yearly_usd: float | None = Field(None, ge=0)
    features: list[str] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)
    is_public: bool = True
    sort_order: int = 0


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    price_monthly_usd: float | None = Field(None, ge=0)
    price_yearly_usd: float | None = Field(None, ge=0)
    features: list[str] | None = None
    limits: dict | None = None
    is_public: bool | None = None
    sort_order: int | None = None


class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    price_monthly_usd: float
    price_yearly_usd: float | None
    features: list[str]
    limits: dict
    is_public: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


# ── Subscriptions ────────────────────────────────────────────


class SubscriptionCreate(BaseModel):
    plan_id: str = Field(..., min_length=1)
    trial_days: int | None = Field(None, ge=0, le=365)


class SubscriptionUpdate(BaseModel):
    plan_id: str | None = None
    status: SubscriptionStatus | None = None
    auto_renew: bool | None = None
    payment_method_id: uuid.UUID | None = None


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    plan_id: str
    status: str
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    auto_renew: bool
    payment_method_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ── Invoices ─────────────────────────────────────────────────


class InvoiceCreate(BaseModel):
    subscription_id: uuid.UUID
    amount_usd: float = Field(..., gt=0)
    currency: str = "USD"
    due_date: date


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    paid_at: datetime | None = None
    invoice_pdf_url: str | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    subscription_id: uuid.UUID
    amount_usd: float
    currency: str
    status: str
    due_date: date
    paid_at: datetime | None
    invoice_pdf_url: str | None
    created_at: datetime


# ── Usage Records ────────────────────────────────────────────


class UsageRecordCreate(BaseModel):
    metric: str = Field(..., min_length=1)
    value: float = Field(default=0.0)
    period: UsagePeriod = UsagePeriod.daily


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    metric: str
    value: float
    period: str
    recorded_at: datetime


class UsageSummaryResponse(BaseModel):
    tenant_id: uuid.UUID
    metric: str
    period: str
    total: float
    count: int
    recorded_at: datetime


# ── Payment Methods ──────────────────────────────────────────


class PaymentMethodCreate(BaseModel):
    provider: str = Field(..., min_length=1)
    provider_payment_method_id: str = Field(..., min_length=1)
    last_four: str | None = Field(None, max_length=4)
    card_brand: str | None = Field(None, max_length=50)
    is_default: bool = False


class PaymentMethodUpdate(BaseModel):
    last_four: str | None = Field(None, max_length=4)
    card_brand: str | None = Field(None, max_length=50)
    is_default: bool | None = None


class PaymentMethodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    provider_payment_method_id: str
    last_four: str | None
    card_brand: str | None
    is_default: bool
    created_at: datetime
