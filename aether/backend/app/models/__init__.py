"""Aether SQLAlchemy models — mirrors schema.sql for PostgreSQL 16."""

from app.models.base import Base
from app.models.enums import (
    ChannelTypeEnum,
    ConversationStatus,
    MessageRole,
    SubscriptionStatus,
    InvoiceStatus,
    CredentialTypeEnum,
    UsagePeriod,
    EntityValueType,
    ExecutionResult,
)
from app.models.tenants import Tenant, TenantConfig, TenantFeature, TenantLimit, TenantDomain
from app.models.users import User, Role, Membership
from app.models.organisations import Organisation
from app.models.auth import Session, RefreshToken, MagicLink, ApiKey, Passkey
from app.models.channels import Channel, ChannelCredential, ChannelUsage
from app.models.conversations import Conversation, Message, MessageAttachment
from app.models.ai import Intent, IntentTemplate, EntityType, AIModel, DriverConfig, DriverMetric, KnowledgeBase, KnowledgeDocument
from app.models.services import ServiceDefinition, ServiceInstance, ServiceBinding, ServiceExecution
from app.models.billing import SubscriptionPlan, Subscription, Invoice, UsageRecord, PaymentMethod
from app.models.documents import (
    Document,
    DocumentVersion,
    DocumentOperation,
    DocumentTag,
    Tag,
    Template,
)
from app.models.audit import AuditLog, ApiCallLog
from app.models.process_runtime import ProcessInstance, ProcessTransition

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
    "Tenant", "TenantConfig", "TenantFeature", "TenantLimit", "TenantDomain",
    "User", "Role", "Membership",
    "Organisation",
    "Session", "RefreshToken", "MagicLink", "ApiKey", "Passkey",
    "Channel", "ChannelCredential", "ChannelUsage",
    "Conversation", "Message", "MessageAttachment",
    "Intent", "IntentTemplate", "EntityType",
    "AIModel", "DriverConfig", "DriverMetric",
    "KnowledgeBase", "KnowledgeDocument",
    # Documents
    "Document", "DocumentVersion", "DocumentOperation", "DocumentTag", "Tag", "Template",
    "ServiceDefinition", "ServiceInstance", "ServiceBinding", "ServiceExecution",
    "SubscriptionPlan", "Subscription", "Invoice", "UsageRecord", "PaymentMethod",
    "AuditLog", "ApiCallLog",
    "ProcessInstance", "ProcessTransition",
]
