# 📁 backend

Бэкенд — FastAPI, async, multi-tenant, AI-powered.

**Стек:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Redis, Celery.
**Принцип:** Zero hardcode. Plugin architecture. Tenant isolation через RLS + contextvar.
**DB:** PostgreSQL 16+ с Row-Level Security per tenant.

---

## 📊 Обзор

```
backend/
├── 📁 alembic/
│   ├── env.py
│   │   ⚡ 0 классов
│   │   ⚡ 3 функции: run_migrations_online(), run_migrations_offline(), get_tenant_context_for_migrations()
│   ├── script.py.mako
│   └── 📁 versions/
│       ├── 0001_initial_core.py
│       │   ⚡ 2 функции: upgrade(), downgrade()
│       ├── 0002_add_tenant_features_and_limits.py
│       │   ⚡ 2 функции: upgrade(), downgrade()
│       ├── 0003_add_channel_tables.py
│       │   ⚡ 2 функции: upgrade(), downgrade()
│       ├── 0004_add_service_plugin_tables.py
│       │   ⚡ 2 функции: upgrade(), downgrade()
│       └── 0005_add_rls_policies.py
│           ⚡ 2 функции: upgrade(), downgrade()
│
├── 📁 app/
│   ├── main.py
│   │   ⚡ 0 классов
│   │   ⚡ 3 функции: create_app(), lifespan(), health_check()
│   │
│   ├── 📁 core/
│   │   ├── config.py
│   │   │   ⚡ 1 класс: Settings(BaseSettings) — DATABASE_URL, REDIS_URL, CELERY_BROKER_URL, SECRET_KEY, ENCRYPTION_KEY, ENVIRONMENT, LOG_LEVEL, DEFAULT_MODEL
│   │   │   ⚡ 1 функция: get_settings() -> Settings (cached lru)
│   │   ├── security.py
│   │   │   ⚡ 2 класса: TokenPair, TokenData
│   │   │   ⚡ 6 функций: create_access_token(), create_refresh_token(), decode_token(), hash_password(), verify_password(), encrypt_credential() / decrypt_credential()
│   │   ├── deps.py
│   │   │   ⚡ 0 классов
│   │   │   ⚡ 8 функций: get_db() -> AsyncSession, get_tenant_context() -> TenantContext, get_current_user() -> User, require_feature(feature: str), require_subscription(tier: str), check_rate_limit(endpoint: str), get_channel_router() -> ChannelRouter, get_ai_router() -> AIRouter
│   │   ├── tenant_context.py
│   │   │   ⚡ 1 dataclass: TenantContext(tenant_id, slug, tier, config, features, limits)
│   │   │   ⚡ 4 функции: set_tenant_context(ctx), get_tenant_context(), reset_tenant_context(), _tenant_ctx (ContextVar)
│   │   ├── exceptions.py
│   │   │   ⚡ 1 базовый класс: AetherException
│   │   │   ⚡ 12 классов-наследников: TenantNotFoundError, TenantInactiveError, SubscriptionExpiredError, RateLimitExceededError, FeatureNotAvailableError, DriverUnavailableError, InferenceError, EntityExtractionError, IntentClassificationError, PluginNotFoundError, PluginExecutionError, ChannelDeliveryError
│   │   └── logging.py
│   │       ⚡ 0 классов
│   │       ⚡ 2 функции: setup_logging(), get_logger(name)
│   │
│   ├── 📁 models/
│   │   ├── base.py
│   │   │   ⚡ 2 класса: Base (DeclarativeBase), TimestampMixin (created_at, updated_at), TenantMixin (tenant_id UUID FK)
│   │   │   ⚡ 0 функций
│   │   ├── tenant.py
│   │   │   ⚡ 6 классов: Tenant, TenantSubscription, TenantConfig, TenantFeature, TenantLimit, TenantDomain
│   │   ├── user.py
│   │   │   ⚡ 4 класса: User, Role, Permission, UserTenant (association)
│   │   ├── channel.py
│   │   │   ⚡ 3 класса: Channel, ChannelConfig, ChannelCredential
│   │   ├── conversation.py
│   │   │   ⚡ 3 класса: Conversation, Message, MessageAttachment
│   │   ├── service.py
│   │   │   ⚡ 4 класса: ServiceDefinition, ServiceInstance, ServiceBinding, ServiceExecution
│   │   ├── intent.py
│   │   │   ⚡ 3 класса: Intent, IntentTemplate, EntityType
│   │   ├── billing.py
│   │   │   ⚡ 5 классов: SubscriptionPlan, TenantSubscription (расширенная), Invoice, UsageRecord, PaymentMethod
│   │   └── audit.py
│   │       ⚡ 2 класса: AuditLog, ApiCallLog
│   │
│   ├── 📁 api/
│   │   ├── router.py
│   │   │   ⚡ 0 классов
│   │   │   ⚡ 1 функция: create_api_router() -> APIRouter
│   │   └── 📁 v1/
│   │       ├── __init__.py
│   │       │   ⚡ 1 класс: V1Router
│   │       ├── tenants.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 8 функций: list_tenants(), create_tenant(), get_tenant(), update_tenant(), delete_tenant(), suspend_tenant(), reactivate_tenant(), get_tenant_stats()
│   │       ├── auth.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 5 функций: login(), refresh_token(), logout(), create_api_key(), revoke_api_key()
│   │       ├── channels.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 7 функций: list_channels(), create_channel(), get_channel(), update_channel(), delete_channel(), test_channel_connection(), get_channel_status()
│   │       ├── conversations.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 5 функций: list_conversations(), get_conversation(), get_messages(), send_message(), close_conversation()
│   │       ├── services.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 7 функций: list_installed_services(), get_service_catalog(), install_service(), uninstall_service(), update_service_config(), test_service(), get_service_metrics()
│   │       ├── intents.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 5 функций: list_intents(), create_intent(), update_intent(), delete_intent(), test_intent_classification()
│   │       ├── webhooks.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 4 функций: telegram_webhook(), email_inbound_webhook(), whatsapp_webhook(), generic_inbound_webhook()
│   │       ├── billing.py
│   │       │   ⚡ 0 классов
│   │       │   ⚡ 6 функций: get_subscription(), change_plan(), get_invoices(), get_usage_report(), get_credits_balance(), add_credits()
│   │       └── admin.py
│   │           ⚡ 0 классов
│   │           ⚡ 5 функций: get_system_health(), get_platform_stats(), get_tenant_list(), get_audit_log(), get_driver_status()
│   │
│   ├── 📁 middleware/
│   │   ├── tenant.py
│   │   │   ⚡ 1 класс: TenantMiddleware (BaseHTTPMiddleware)
│   │   │   ⚡ 1 dataclass: TenantResolutionResult
│   │   │   ⚡ 3 функции: resolve_tenant_from_subdomain(), resolve_tenant_from_jwt(), resolve_tenant_from_header()
│   │   ├── rate_limit.py
│   │   │   ⚡ 1 класс: RateLimitMiddleware (BaseHTTPMiddleware)
│   │   │   ⚡ 2 функции: check_token_bucket(), get_rate_limit_headers()
│   │   ├── audit.py
│   │   │   ⚡ 1 класс: AuditMiddleware (BaseHTTPMiddleware)
│   │   │   ⚡ 1 функция: log_api_call()
│   │   └── cors.py
│   │       ⚡ 1 класс: PerTenantCORSMiddleware (BaseHTTPMiddleware)
│   │       ⚡ 1 функция: get_allowed_origins_for_tenant()
│   │
│   ├── 📁 schemas/
│   │   ├── common.py
│   │   │   ⚡ 3 класса: PaginatedResponse, ErrorResponse, HealthResponse
│   │   ├── tenant.py
│   │   │   ⚡ 5 классов: TenantCreate, TenantUpdate, TenantResponse, TenantStatsResponse, TenantConfigUpdate
│   │   ├── user.py
│   │   │   ⚡ 4 классов: UserCreate, UserResponse, UserUpdate, LoginRequest
│   │   ├── channel.py
│   │   │   ⚡ 4 классов: ChannelCreate, ChannelUpdate, ChannelResponse, ChannelStatusResponse
│   │   ├── conversation.py
│   │   │   ⚡ 4 классов: MessageResponse, ConversationResponse, SendMessageRequest, ConversationListResponse
│   │   ├── service.py
│   │   │   ⚡ 5 классов: ServiceDefinitionResponse, ServiceInstanceCreate, ServiceInstanceResponse, ServiceConfigUpdate, ServiceTestRequest
│   │   ├── intent.py
│   │   │   ⚡ 3 классов: IntentCreate, IntentUpdate, IntentResponse
│   │   └── webhook.py
│   │       ⚡ 3 классов: TelegramWebhookPayload, EmailInboundPayload, GenericWebhookPayload
│   │
│   └── 📁 tasks/
│       ├── __init__.py
│       │   ⚡ 1 класс: CeleryApp
│       │   ⚡ 1 функция: make_celery()
│       ├── inference.py
│       │   ⚡ 3 tasks: process_intent_task(), generate_embedding_batch(), health_check_drivers()
│       ├── notifications.py
│       │   ⚡ 3 tasks: send_email_notification(), send_push_notification(), send_telegram_notification()
│       ├── billing.py
│       │   ⚡ 3 tasks: aggregate_usage_metrics(), generate_invoices(), check_trial_expiry()
│       └── maintenance.py
│           ⚡ 3 tasks: cleanup_expired_conversations(), archive_old_audit_logs(), vacuum_database()
│
└── 📁 tests/
    ├── conftest.py
    │   ⚡ 6 fixtures: async_client, db_session, test_tenant, test_user, auth_headers, mock_inference_pool
    ├── test_core/
    │   ├── test_config.py
    │   ├── test_security.py
    │   └── test_tenant_context.py
    ├── test_api/
    │   ├── test_auth.py
    │   ├── test_tenants.py
    │   ├── test_channels.py
    │   └── test_conversations.py
    ├── test_services/
    │   ├── test_channel_router.py
    │   ├── test_plugin_registry.py
    │   └── test_intent_classifier.py
    └── test_integration/
        ├── test_full_pipeline.py
        └── test_tenant_isolation.py
```

---

## 1. `backend/app/main.py` — Entry Point

```python
# Классы: нет
# Функции:
def create_app() -> FastAPI:
    """
    Создаёт FastAPI приложение с middleware chain:
    1. PerTenantCORSMiddleware
    2. TenantMiddleware
    3. RateLimitMiddleware
    4. AuditMiddleware
    Монтирует роутеры, lifespan, exception handlers.
    """

async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup: подключает БД, инициализирует InferencePool, PluginRegistry,
             ChannelRouter, запускает Celery worker.
    Shutdown: закрывает пулы соединений, выключает драйверы.
    """

async def health_check() -> dict:
    """GET /health — проверка БД, Redis, Celery, драйверов."""
```

---

## 2. models — SQLAlchemy ORM

### `models/base.py`

```python
class Base(DeclarativeBase):
    """Базовая модель. Все модели наследуют Base."""

class TimestampMixin:
    created_at: Mapped[datetime] — server_default=func.now()
    updated_at: Mapped[datetime] — onupdate=func.now()

class TenantMixin:
    """Миксин для row-level security. ДОЛЖЕН быть в каждой таблице."""
    tenant_id: Mapped[UUID] — ForeignKey("tenants.id", ondelete="CASCADE"), index=True
```

### `models/tenant.py`

```python
class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        Index("ix_tenants_slug", "slug", unique=True),
    )
    id: UUID — primary_key, server_default=func.gen_random_uuid()
    slug: str(100) — unique, subdomain
    name: str(255)
    domain: str(255) | None — custom domain
    logo_url: str(500) | None
    primary_color: str(7) — default "#1a73e8"
    timezone: str(50) — default "UTC"
    locale: str(10) — default "ru"
    is_active: bool — default True
    settings: dict — JSONB (white-label, features, limits overrides)

class TenantSubscription(Base, TimestampMixin, TenantMixin):
    __tablename__ = "tenant_subscriptions"
    plan_id: str — "free", "starter", "professional", "enterprise"
    status: str — "active", "trial", "cancelled", "expired", "past_due"
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    current_period_start: datetime
    current_period_end: datetime
    auto_renew: bool — default True
    payment_method_id: UUID | None

class TenantConfig(Base, TenantMixin):
    __tablename__ = "tenant_configs"
    key: str(255)
    value: dict — JSONB

class TenantFeature(Base, TenantMixin):
    __tablename__ = "tenant_features"
    feature_key: str(100)
    is_enabled: bool — default False
    config: dict | None — JSONB

class TenantLimit(Base, TenantMixin):
    __tablename__ = "tenant_limits"
    limit_key: str(100) — "max_users", "max_conversations_per_day", etc.
    limit_value: int
    current_usage: int — default 0
    period: str — "daily", "monthly", "total"

class TenantDomain(Base, TenantMixin):
    __tablename__ = "tenant_domains"
    domain: str(255) — unique
    is_verified: bool — default False
    ssl_certificate_id: str | None
```

### `models/user.py`

```python
class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"
    id: UUID
    email: str(255) — unique per tenant
    hashed_password: str(255)
    full_name: str(255)
    is_active: bool
    is_superadmin: bool — default False (platform-level)
    last_login_at: datetime | None
    mfa_enabled: bool — default False
    mfa_secret: str | None

class Role(Base, TenantMixin):
    __tablename__ = "roles"
    id: UUID
    name: str(100)
    permissions: list[str] — ARRAY или JSONB

class UserTenant(Base):
    __tablename__ = "user_tenants"
    user_id: UUID — FK users.id
    tenant_id: UUID — FK tenants.id
    role_id: UUID | None — FK roles.id
```

### `models/channel.py`

```python
class Channel(Base, TimestampMixin, TenantMixin):
    __tablename__ = "channels"
    id: UUID
    channel_type: str(50) — "telegram", "web_widget", "email", "whatsapp", "rest_api"
    display_name: str(255)
    is_active: bool — default True
    config: dict — JSONB (типо-специфичные настройки)
    priority: int — default 0

class ChannelCredential(Base, TenantMixin):
    __tablename__ = "channel_credentials"
    id: UUID
    channel_id: UUID — FK channels.id
    credential_type: str — "api_key", "bot_token", "smtp_password", "oauth_token"
    encrypted_value: bytes — AES-256-GCM encrypted
    expires_at: datetime | None

class ChannelUsage(Base, TenantMixin):
    __tablename__ = "channel_usage"
    channel_id: UUID
    date: date
    messages_in: int
    messages_out: int
    errors: int
    latency_avg_ms: float
```

### `models/conversation.py`

```python
class Conversation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "conversations"
    id: UUID
    user_id: UUID | None — FK users.id (может быть анонимный)
    channel_id: UUID — FK channels.id
    external_user_id: str(255) — Telegram user_id, email address etc.
    status: str — "active", "closed", "archived"
    subject: str(500) | None — авто-извлечённая тема
    metadata: dict — JSONB

class Message(Base, TenantMixin):
    __tablename__ = "messages"
    id: UUID
    conversation_id: UUID — FK conversations.id
    role: str — "user", "assistant", "system"
    content: str — TEXT
    content_type: str — "text", "html", "markdown"
    intent: str | None — classified intent
    entities: dict | None — JSONB extracted entities
    tokens_used: int | None
    cost_usd: float | None
    metadata: dict — JSONB
    created_at: datetime — server_default=func.now()

class MessageAttachment(Base, TenantMixin):
    __tablename__ = "message_attachments"
    id: UUID
    message_id: UUID — FK messages.id
    file_type: str — "image", "document", "audio", "video"
    file_url: str(1000)
    file_size_bytes: int
    mime_type: str(255)
```

### `models/intent.py`

```python
class Intent(Base, TenantMixin):
    __tablename__ = "intents"
    id: UUID
    name: str(100) — "document_submission", "order_tracking"
    display_name: str(255)
    description: str(1000)
    category: str — "greeting", "question", "action", "complaint", "other"
    is_builtin: bool — default False
    plugin_ids: list[str] — ARRAY, какие плагины обрабатывают

class IntentTemplate(Base, TenantMixin):
    __tablename__ = "intent_templates"
    id: UUID
    intent_id: UUID — FK intents.id
    example_text: str — пример сообщения "Подай ГУ-12 на вагон 1234"
    language: str(10) — "ru"

class EntityType(Base, TenantMixin):
    __tablename__ = "entity_types"
    id: UUID
    name: str(100) — "wagon_number", "container_number"
    display_name: str(255)
    value_type: str — "string", "number", "date", "email", "phone"
    pattern: str(500) | None — regex
    examples: list[str] — ARRAY
    lookup_table: str | None — имя таблицы для валидации
```

### `models/service.py`

```python
class ServiceDefinition(Base):
    __tablename__ = "service_definitions"
    __table_args__ = (Index("ix_service_def_plugin_id_version", "plugin_id", "version", unique=True),)
    id: UUID
    plugin_id: str(100) — "gu12", "faq", "scheduler"
    display_name: str(255)
    description: str(1000)
    version: str(20)
    is_builtin: bool — default False
    is_active: bool — default True
    capabilities: list[str] — ARRAY ("document_generation", "calculation", etc)
    config_schema: dict — JSON Schema для валидации конфига
    created_at: datetime

class ServiceInstance(Base, TenantMixin, TimestampMixin):
    __tablename__ = "service_instances"
    id: UUID
    service_definition_id: UUID — FK service_definitions.id
    config: dict — JSONB, per-tenant настройки плагина
    is_active: bool — default True
    installed_at: datetime

class ServiceBinding(Base, TenantMixin):
    __tablename__ = "service_bindings"
    id: UUID
    service_instance_id: UUID — FK service_instances.id
    channel_id: UUID | None — None = all channels
    priority: int — default 0

class ServiceExecution(Base, TenantMixin):
    __tablename__ = "service_executions"
    __table_args__ = (
        Index("ix_service_exec_ts_tenant", "tenant_id", "created_at"),
    )
    id: UUID
    service_instance_id: UUID
    conversation_id: UUID
    intent: str
    entities: dict — JSONB
    result: str — "success", "error", "partial"
    response_text: str | None
    duration_ms: int
    tokens_used: int
    cost_usd: float | None
    error_message: str | None
    created_at: datetime
```

### `models/billing.py`

```python
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: str — "free", "starter", "professional", "enterprise"
    name: str(255)
    description: str(1000)
    price_monthly_usd: float
    price_yearly_usd: float | None
    features: list[str] — ARRAY
    limits: dict — JSONB (max_users, max_conversations, etc)
    is_public: bool — default True

class Invoice(Base, TenantMixin):
    __tablename__ = "invoices"
    id: UUID
    subscription_id: UUID
    amount_usd: float
    currency: str(3) — "USD", "RUB"
    status: str — "draft", "open", "paid", "void", "past_due"
    due_date: date
    paid_at: datetime | None
    invoice_pdf_url: str(1000) | None

class UsageRecord(Base, TenantMixin):
    __tablename__ = "usage_records"
    id: UUID
    metric: str — "api_calls", "tokens_used", "storage_bytes", "active_users"
    value: float
    recorded_at: datetime — server_default=func.now()
    period: str — "hourly", "daily", "monthly"

class PaymentMethod(Base, TenantMixin):
    __tablename__ = "payment_methods"
    id: UUID
    provider: str — "stripe", "paddle", "manual"
    provider_payment_method_id: str
    last_four: str(4) | None
    card_brand: str(50) | None
    is_default: bool — default False
```

### `models/audit.py`

```python
class AuditLog(Base, TenantMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_ts_tenant", "tenant_id", "created_at"),
    )
    id: UUID
    user_id: UUID | None
    action: str — "tenant.create", "channel.update", "user.login", etc.
    resource: str — "tenants", "channels", "users"
    resource_id: UUID | None
    details: dict — JSONB
    ip_address: str(45)
    user_agent: str(500) | None

class ApiCallLog(Base, TenantMixin):
    __tablename__ = "api_call_logs"
    id: UUID
    method: str(10)
    path: str(1000)
    status_code: int
    duration_ms: int
    user_id: UUID | None
    ip_address: str(45)
```

---

## 3. API Endpoints (полная спецификация)

Все эндпоинты под `/api/v1/`. Tenant-scoped эндпоинты используют префикс `/tenants/{tenant_id}`.

### `api/v1/auth.py`

| Метод | Путь | Функция | Описание |
|-------|------|---------|----------|
| POST | `/auth/login` | `login()` | Email + password → access_token + refresh_token |
| POST | `/auth/refresh` | `refresh_token()` | Refresh token → новый access_token |
| POST | `/auth/logout` | `logout()` | Revoke refresh token |
| POST | `/auth/api-keys` | `create_api_key()` | Создать API key для tenant |
| DELETE | `/auth/api-keys/{key_id}` | `revoke_api_key()` | Отозвать API key |

### `api/v1/tenants.py` (superadmin required)

| Метод | Путь | Функция | Описание |
|-------|------|---------|----------|
| GET | `/tenants` | `list_tenants()` | Список, пагинация, фильтр по статусу |
| POST | `/tenants` | `create_tenant()` | Создать tenant + provision |
| GET | `/tenants/{id}` | `get_tenant()` | Детали tenant |
| PUT | `/tenants/{id}` | `update_tenant()` | Обновить настройки |
| DELETE | `/tenants/{id}` | `delete_tenant()` | Soft-delete |
| POST | `/tenants/{id}/suspend` | `suspend_tenant()` | Заблокировать |
| POST | `/tenants/{id}/reactivate` | `reactivate_tenant()` | Разблокировать |
| GET | `/tenants/{id}/stats` | `get_tenant_stats()` | Статистика использования |

### `api/v1/channels.py`

| Метод | Путь | Функция |
|-------|------|---------|
| GET | `/tenants/{tid}/channels` | `list_channels()` |
| POST | `/tenants/{tid}/channels` | `create_channel()` |
| GET | `/tenants/{tid}/channels/{cid}` | `get_channel()` |
| PUT | `/tenants/{tid}/channels/{cid}` | `update_channel()` |
| DELETE | `/tenants/{tid}/channels/{cid}` | `delete_channel()` |
| POST | `/tenants/{tid}/channels/{cid}/test` | `test_channel_connection()` |
| GET | `/tenants/{tid}/channels/{cid}/status` | `get_channel_status()` |

### `api/v1/conversations.py`

| Метод | Путь | Функция |
|-------|------|---------|
| GET | `/tenants/{tid}/conversations` | `list_conversations()` |
| GET | `/tenants/{tid}/conversations/{cid}` | `get_conversation()` |
| GET | `/tenants/{tid}/conversations/{cid}/messages` | `get_messages()` |
| POST | `/tenants/{tid}/conversations/{cid}/messages` | `send_message()` |
| POST | `/tenants/{tid}/conversations/{cid}/close` | `close_conversation()` |

### `api/v1/services.py`

| Метод | Путь | Функция |
|-------|------|---------|
| GET | `/tenants/{tid}/services` | `list_installed_services()` |
| GET | `/tenants/{tid}/services/catalog` | `get_service_catalog()` |
| POST | `/tenants/{tid}/services` | `install_service()` |
| DELETE | `/tenants/{tid}/services/{sid}` | `uninstall_service()` |
| PUT | `/tenants/{tid}/services/{sid}/config` | `update_service_config()` |
| POST | `/tenants/{tid}/services/{sid}/test` | `test_service()` |
| GET | `/tenants/{tid}/services/{sid}/metrics` | `get_service_metrics()` |

### `api/v1/webhooks.py` (публичные, tenant определяется по URL/webhook_id)

| Метод | Путь | Функция |
|-------|------|---------|
| POST | `/webhooks/telegram/{channel_id}` | `telegram_webhook()` |
| POST | `/webhooks/email/{channel_id}` | `email_inbound_webhook()` |
| POST | `/webhooks/whatsapp/{channel_id}` | `whatsapp_webhook()` |
| POST | `/webhooks/generic/{channel_id}` | `generic_inbound_webhook()` |

### `api/v1/billing.py`

| Метод | Путь | Функция |
|-------|------|---------|
| GET | `/tenants/{tid}/billing/subscription` | `get_subscription()` |
| POST | `/tenants/{tid}/billing/subscription/change` | `change_plan()` |
| GET | `/tenants/{tid}/billing/invoices` | `get_invoices()` |
| GET | `/tenants/{tid}/billing/usage` | `get_usage_report()` |
| GET | `/tenants/{tid}/billing/credits` | `get_credits_balance()` |
| POST | `/tenants/{tid}/billing/credits/add` | `add_credits()` |

### 🛡 Ролевое разделение API

**Три роли:**
- `superadmin` — управление платформой: tenants, subscriptions, drivers, аудит. Видит ВСЕ данные.
- `tenant_admin` — управление СВОИМ бизнесом: каналы, сервисы, пользователи, AI-настройки.
- `tenant_user` — оператор: работа с диалогами, документами (read/write только в рамках своего tenant).

**Принцип префиксов:**
- `/admin/` → superadmin-only (платформенное управление)
- `/tenants/{tid}/` → tenant-скоп (tenant_admin/tenant_user могут видеть только свой tenant_id)
- `/webhooks/` → публичные endpoints (tenant определяется по channel_id из БД)

### `api/v1/admin.py` — Admin Dashboard API (суперадминка)

| Метод | Путь | Функция | Описание |
|-------|------|---------|----------|
| GET | `/admin/health` | `get_system_health()` | Статус всех компонентов (БД, Redis, драйверы, Celery) |
| GET | `/admin/stats` | `get_platform_stats()` | Аггрегированная статистика платформы |
| GET | `/admin/tenants` | `get_tenant_list()` | Все tenant'ы с пагинацией, поиском, фильтром по статусу |
| POST | `/admin/tenants` | `create_tenant()` | Создать tenant + provision (каналы, admin user, trial) |
| GET | `/admin/tenants/{id}` | `get_tenant_detail()` | Полная инфа: статус, подписка, каналы, пользователи |
| PUT | `/admin/tenants/{id}` | `update_tenant()` | Обновить white-label, лимиты |
| POST | `/admin/tenants/{id}/suspend` | `suspend_tenant()` | Заблокировать tenant |
| POST | `/admin/tenants/{id}/reactivate` | `reactivate_tenant()` | Разблокировать tenant |
| DELETE | `/admin/tenants/{id}` | `delete_tenant()` | Soft-delete + cleanup |
| GET | `/admin/subscriptions` | `list_subscriptions()` | Все подписки |
| POST | `/admin/subscriptions/{tid}/change` | `change_subscription()` | Сменить тариф (admin override) |
| GET | `/admin/plugins` | `list_all_plugins()` | Все установленные плагины по всем tenant |
| POST | `/admin/plugins/{pid}/approve` | `approve_plugin()` | Апрувнуть сторонний плагин (Stage 3 marketplace) |
| GET | `/admin/drivers` | `get_driver_status()` | Статус AI-драйверов: latency, load, errors |
| POST | `/admin/drivers/{did}/reload` | `reload_driver()` | Hot-reload конфигурации драйвера |
| GET | `/admin/audit` | `get_audit_log()` | Платформенный аудит (все tenant'ы) |
| GET | `/admin/billing/invoices` | `get_all_invoices()` | Все счета платформы |
| GET | `/admin/analytics` | `get_platform_analytics()` | MRR, churn, ARPU, DAU |

### `api/v1/settings.py` — Client Workspace API (tenant_admin самообслуживание)

> Все под `/tenants/{tid}/settings/`. Tenant видит только свой tenant_id.
> Принцип: компактно. Не одна форма = целая страница. Сгруппировано по смыслу.

| Метод | Путь | Функция | Описание |
|-------|------|---------|----------|
| GET | `/tenants/{tid}/settings` | `get_workspace_settings()` | Все настройки бизнес-кабинета компактно |
| PUT | `/tenants/{tid}/settings/brand` | `update_branding()` | Лого, цвета, название (white-label) |
| PUT | `/tenants/{tid}/settings/ai` | `update_ai_settings()` | AI-модель, промпты, язык, tone |
| GET | `/tenants/{tid}/settings/channels` | `list_my_channels()` | Каналы клиента (компактно, без platform info) |
| PUT | `/tenants/{tid}/settings/channels/{cid}` | `update_channel_config()` | Настройки одного канала |
| POST | `/tenants/{tid}/settings/channels/{cid}/test` | `test_channel()` | Проверить соединение |
| GET | `/tenants/{tid}/settings/services` | `list_my_services()` | Установленные сервисы |
| PUT | `/tenants/{tid}/settings/services/{sid}` | `configure_service()` | Настроить PromptDrivenPlugin |
| GET | `/tenants/{tid}/settings/users` | `list_my_users()` | Пользователи бизнеса |
| POST | `/tenants/{tid}/settings/users` | `invite_user()` | Пригласить оператора |
| DELETE | `/tenants/{tid}/settings/users/{uid}` | `remove_user()` | Удалить оператора |
| GET | `/tenants/{tid}/settings/billing` | `get_my_billing()` | Подписка, счета, кредиты |
| GET | `/tenants/{tid}/settings/audit` | `get_my_audit_log()` | Аудит действий в рамках бизнеса |
| GET | `/tenants/{tid}/settings/analytics` | `get_my_analytics()` | Статистика своего бизнеса |

---

## 4. schemas — Pydantic (примеры ключевых)

```python
# schemas/common.py
class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int

class ErrorResponse(BaseModel):
    error: str
    detail: str | None
    error_code: str | None
    timestamp: datetime

# schemas/tenant.py
class TenantCreate(BaseModel):
    slug: str — regex ^[a-z0-9-]+$
    name: str
    domain: str | None
    timezone: str
    locale: str

class TenantResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    domain: str | None
    logo_url: str | None
    primary_color: str
    timezone: str
    locale: str
    is_active: bool
    subscription_tier: str
    features: dict
    created_at: datetime

# schemas/channel.py
class ChannelCreate(BaseModel):
    channel_type: ChannelType — enum из БД
    display_name: str
    config: dict — зависит от channel_type
    credentials: dict | None — зашифруются

# schemas/conversation.py
class SendMessageRequest(BaseModel):
    content: str
    content_type: str = "text"
    metadata: dict | None

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    intent: str | None
    entities: dict | None
    created_at: datetime

# schemas/service.py
class ServiceInstanceCreate(BaseModel):
    service_definition_id: UUID
    config: dict | None
```

---

## 5. Alembic Миграции

### `0001_initial_core.py`
```python
def upgrade():
    # tenants, users, roles, user_tenants
    # Все таблицы с tenant_id и RLS policies:
    # ALTER TABLE ... ENABLE ROW LEVEL SECURITY
    # CREATE POLICY tenant_isolation ON ... USING (tenant_id = current_setting('app.current_tenant_id')::UUID)

def downgrade():
    # DROP всё в обратном порядке
```

### `0002_add_tenant_features_and_limits.py`
```python
def upgrade():
    # tenant_features, tenant_limits, tenant_domains, tenant_configs
    # subscription_plans (seed: free, starter, professional, enterprise)

def downgrade():
    # DROP
```

### `0003_add_channel_tables.py`
```python
def upgrade():
    # channels, channel_credentials, channel_usage
    # Seed: web_widget канал по умолчанию для каждого tenant

def downgrade():
    # DROP
```

### `0004_add_service_plugin_tables.py`
```python
def upgrade():
    # service_definitions, service_instances, service_bindings, service_executions
    # Seed: builtin plugins (echo, faq, scheduler, form, classifier, escalation)

def downgrade():
    # DROP
```

### `0005_add_rls_policies.py`
```python
def upgrade():
    # Добавляет RLS policies для всех таблиц у которых есть tenant_id
    # Для каждой таблицы: ENABLE ROW LEVEL SECURITY + CREATE POLICY

def downgrade():
    # DROP policies
```

---

## 📊 Статистика модуля backend

| Компонент | Файлов | Классов | Методов/Функций |
|-----------|--------|---------|-----------------|
| Core | 6 | 17 | 21 |
| Models | 10 | 35 | 0 (+5 миксинов) |
| API v1 | 10 | 1 | ~55 эндпоинтов |
| Schemas | 8 | 31 | 0 |
| Middleware | 4 | 4 | 6 |
| Tasks | 5 | 1 | 12 задач |
| Alembic | 5 миграций | 0 | 10 функций |
| Tests | ~20 | 0 | ~150+ тестов |
| **Итого** | **~68** | **~89** | **~254** |
