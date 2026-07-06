"""PostgreSQL enum types used across Aether models."""

from __future__ import annotations

from enum import StrEnum


class ChannelTypeEnum(StrEnum):
    telegram = "telegram"
    web_widget = "web_widget"
    email = "email"
    whatsapp = "whatsapp"
    rest_api = "rest_api"


class ConversationStatus(StrEnum):
    active = "active"
    closed = "closed"
    archived = "archived"


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class SubscriptionStatus(StrEnum):
    active = "active"
    trial = "trial"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"


class InvoiceStatus(StrEnum):
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    past_due = "past_due"


class CredentialTypeEnum(StrEnum):
    api_key = "api_key"
    bot_token = "bot_token"
    smtp_password = "smtp_password"
    oauth_token = "oauth_token"


class UsagePeriod(StrEnum):
    hourly = "hourly"
    daily = "daily"
    monthly = "monthly"


class EntityValueType(StrEnum):
    string = "string"
    number = "number"
    date = "date"
    email = "email"
    phone = "phone"


class ExecutionResult(StrEnum):
    success = "success"
    error = "error"
    partial = "partial"


class DocumentType(StrEnum):
    order = "order"
    invoice = "invoice"
    contract = "contract"
    custom = "custom"
