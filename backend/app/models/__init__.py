"""Aether SQLAlchemy models — mirrors schema.sql for PostgreSQL 16."""

from app.models.ai import (
    AIModel,
    DriverConfig,
    DriverMetric,
    EntityType,
    Intent,
    IntentTemplate,
    KnowledgeBase,
    KnowledgeDocument,
)
from app.models.audit import ApiCallLog, AuditLog
from app.models.auth import ApiKey, MagicLink, Passkey, RefreshToken, Session
from app.models.base import Base
from app.models.billing import Invoice, PaymentMethod, Subscription, SubscriptionPlan, UsageRecord
from app.models.channels import Channel, ChannelCredential, ChannelUsage
from app.models.conversations import Conversation, Message, MessageAttachment
from app.models.documents import (
    Document,
    DocumentOperation,
    DocumentTag,
    DocumentVersion,
    Tag,
    Template,
)
from app.models.enums import (
    ChannelTypeEnum,
    ConversationStatus,
    CredentialTypeEnum,
    EntityValueType,
    ExecutionResult,
    InvoiceStatus,
    MessageRole,
    SubscriptionStatus,
    UsagePeriod,
)
from app.models.organisations import Organisation
from app.models.services import (
    ServiceBinding,
    ServiceDefinition,
    ServiceExecution,
    ServiceInstance,
)
from app.models.tenants import Tenant, TenantConfig, TenantDomain, TenantFeature, TenantLimit
from app.models.users import Membership, Role, User

__all__ = [
    "Base",
    # Enums
    "ChannelTypeEnum",
    "ConversationStatus",
    "MessageRole",
    "SubscriptionStatus",
    "InvoiceStatus",
    "CredentialTypeEnum",
    "UsagePeriod",
    "EntityValueType",
    "ExecutionResult",
    # Models
    "Tenant",
    "TenantConfig",
    "TenantFeature",
    "TenantLimit",
    "TenantDomain",
    "User",
    "Role",
    "Membership",
    "Organisation",
    "Session",
    "RefreshToken",
    "MagicLink",
    "ApiKey",
    "Passkey",
    "Channel",
    "ChannelCredential",
    "ChannelUsage",
    "Conversation",
    "Message",
    "MessageAttachment",
    "Intent",
    "IntentTemplate",
    "EntityType",
    "AIModel",
    "DriverConfig",
    "DriverMetric",
    "KnowledgeBase",
    "KnowledgeDocument",
    # Documents
    "Document",
    "DocumentVersion",
    "DocumentOperation",
    "DocumentTag",
    "Tag",
    "Template",
    "ServiceDefinition",
    "ServiceInstance",
    "ServiceBinding",
    "ServiceExecution",
    "SubscriptionPlan",
    "Subscription",
    "Invoice",
    "UsageRecord",
    "PaymentMethod",
    "AuditLog",
    "ApiCallLog",
]
