"""PostgreSQL enum types used across Aether models."""

from __future__ import annotations

import enum


class ChannelTypeEnum(str, enum.Enum):
    telegram = "telegram"
    web_widget = "web_widget"
    email = "email"
    whatsapp = "whatsapp"
    rest_api = "rest_api"


class ConversationStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    archived = "archived"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    trial = "trial"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    past_due = "past_due"


class CredentialTypeEnum(str, enum.Enum):
    api_key = "api_key"
    bot_token = "bot_token"
    smtp_password = "smtp_password"
    oauth_token = "oauth_token"


class UsagePeriod(str, enum.Enum):
    hourly = "hourly"
    daily = "daily"
    monthly = "monthly"


class EntityValueType(str, enum.Enum):
    string = "string"
    number = "number"
    date = "date"
    email = "email"
    phone = "phone"


class ExecutionResult(str, enum.Enum):
    success = "success"
    error = "error"
    partial = "partial"
