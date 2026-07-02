# 📁 Tenant — Мультитенантность, Billing, Rate Limiting

Изоляция tenant в Aether — три уровня: application (contextvar), database (RLS), cache (key prefix).

**Принцип:** Tenant данные НИКОГДА не смешиваются. Row-Level Security на уровне PostgreSQL. Каждый запрос изолирован.

---

## 📊 Обзор

```
backend/app/
├── core/
│   ├── tenant_context.py        # См. backend.md — TenantContext ContextVar
│   └── deps.py                  # См. backend.md — get_tenant_context() dependency
│
├── middleware/
│   ├── tenant.py
│   │   ⚡ 1 класс: TenantMiddleware
│   │   ⚡ 1 dataclass: TenantResolutionResult
│   │   ⚡ 3 функции: resolve_tenant_from_subdomain(), resolve_tenant_from_jwt(), resolve_tenant_from_header()
│   │
│   ├── rate_limit.py
│   │   ⚡ 1 класс: RateLimitMiddleware
│   │   ⚡ 1 класс: TokenBucket
│   │   ⚡ 2 функции: check_rate_limit(), get_rate_limit_headers()
│   │
│   └── audit.py
│       ⚡ 1 класс: AuditMiddleware
│
├── models/
│   ├── tenant.py                 # См. backend.md — Tenant, TenantSubscription, etc.
│   ├── billing.py                # См. backend.md — SubscriptionPlan, Invoice, UsageRecord
│   └── audit.py                  # См. backend.md — AuditLog, ApiCallLog
│
├── services/
│   ├── tenant_service.py
│   │   ⚡ 1 класс: TenantService
│   │
│   └── billing_service.py
│       ⚡ 1 класс: BillingService
│
└── api/v1/
    ├── tenants.py                 # См. backend.md
    └── billing.py                 # См. backend.md

backend/alembic/versions/
├── 0001_initial_core.py           # tenants, users, roles, RLS enable
├── 0002_add_tenant_features_and_limits.py
└── 0005_add_rls_policies.py       # CREATE POLICY для всех таблиц
```

---

## 1. Tenant Isolation — три уровня

### Уровень 1: Application (ContextVar)

```python
# core/tenant_context.py

from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID

@dataclass
class TenantContext:
    tenant_id: UUID
    slug: str
    name: str
    tier: str                       # "free", "starter", "professional", "enterprise"
    is_active: bool
    config: dict = field(default_factory=dict)      # tenant-level настройки
    features: set[str] = field(default_factory=set) # фича-флаги
    limits: dict[str, int] = field(default_factory=dict)  # {"max_users": 10, ...}
    timezone: str = "UTC"
    locale: str = "ru"

_tenant_ctx: ContextVar[TenantContext | None] = ContextVar("tenant_ctx", default=None)


def set_tenant_context(ctx: TenantContext) -> None:
    """Установить tenant контекст для текущего запроса.
    Вызывается TenantMiddleware в начале каждого запроса."""
    _tenant_ctx.set(ctx)


def get_tenant_context() -> TenantContext:
    """Получить tenant контекст текущего запроса.
    Бросает TenantNotResolvedError если контекст не установлен."""
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise TenantNotResolvedError("Tenant context not resolved")
    if not ctx.is_active:
        raise TenantInactiveError(f"Tenant {ctx.slug} is not active")
    return ctx


def reset_tenant_context() -> None:
    """Сбросить tenant контекст. Вызывается в конце запроса."""
    _tenant_ctx.set(None)
```

### Уровень 2: Database (RLS)

```sql
-- 0005_add_rls_policies.py

-- Для каждой таблицы с tenant_id:
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_conversations 
    ON conversations 
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- То же для: messages, channels, service_instances, users, audit_logs, etc.

-- Установка tenant_id в начале сессии:
-- Выполняется в lifespan / middleware через raw SQL
SET app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440000';
```

```python
# core/deps.py — установка tenant_id в БД сессии

async def set_db_tenant_context(
    db: AsyncSession,
    tenant_id: UUID,
) -> None:
    """Установить tenant_id в PostgreSQL сессии для RLS."""
    await db.execute(
        text("SET app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_id)}
    )
```

### Уровень 3: Cache (Redis key prefix)

```python
# Все ключи Redis используют префикс tenant_id
CACHE_KEY_PATTERNS = {
    "conversation_context": "tenant:{tenant_id}:conversation:{conversation_id}",
    "rate_limit": "tenant:{tenant_id}:rate_limit:{endpoint}:{window}",
    "user_session": "tenant:{tenant_id}:user_session:{user_id}",
    "tenant_config": "tenant:{tenant_id}:config",
}

def make_tenant_key(pattern: str, tenant_id: str, **kwargs) -> str:
    """Создать Redis ключ с tenant префиксом."""
    return pattern.format(tenant_id=tenant_id, **kwargs)
```

---

## 2. `middleware/tenant.py` — TenantMiddleware

```python
@dataclass
class TenantResolutionResult:
    tenant_id: UUID | None
    resolution_method: str              # "subdomain", "jwt", "header"
    error: str | None

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware извлечения tenant.
    
    Порядок разрешения:
    1. Subdomain: tenant.logicore.ru → slug="tenant"
    2. JWT claim: токен содержит tenant_id
    3. X-Tenant-ID header (для API clients)
    4. Default tenant (только для dev mode)
    
    Для каждого запроса:
    1. Извлечь tenant
    2. Загрузить TenantContext из Redis (cache) или PostgreSQL
    3. Установить contextvar
    4. Установить app.current_tenant_id в PostgreSQL сессии
    5. Проверить активность + подписку
    6. Продолжить запрос
    7. В конце: сбросить contextvar
    """
    
    def __init__(self, app, db_session_factory, redis, settings) -> None: ...
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Полный lifecycle tenant для запроса:
        1. resolve_tenant(request)
        2. load_tenant_context(tenant_id)
        3. validate_tenant_access(tenant_context)
        4. set_tenant_context(tenant_context)
        5. set_db_tenant_context(db, tenant_id)
        6. response = await call_next(request)
        7. reset_tenant_context()
        8. return response
        """
        ...
    
    async def resolve_tenant(self, request: Request) -> TenantResolutionResult:
        """Извлечь tenant из запроса."""
        ...
    
    async def load_tenant_context(
        self, tenant_id: UUID
    ) -> TenantContext:
        """
        Загрузить TenantContext.
        Сначала Redis (быстро), если miss → PostgreSQL → сохранить в Redis.
        """
        ...
    
    async def validate_tenant_access(
        self, ctx: TenantContext
    ) -> None:
        """
        Проверить что tenant:
        1. Активен
        2. Подписка не истекла
        3. Лимиты не превышены
        """
        ...

async def resolve_tenant_from_subdomain(request: Request) -> TenantResolutionResult:
    """Извлечь tenant из subdomain: tenant-slug.aether.cloud"""
    host = request.headers.get("host", "")
    # Парсинг: tenant-slug.aether.cloud → slug="tenant-slug"
    ...

async def resolve_tenant_from_jwt(request: Request) -> TenantResolutionResult:
    """Извлечь tenant_id из JWT токена."""
    ...

async def resolve_tenant_from_header(request: Request) -> TenantResolutionResult:
    """Извлечь tenant из X-Tenant-ID заголовка."""
    ...
```

---

## 3. `services/tenant_service.py` — TenantService

```python
class TenantService:
    """
    Управление tenant lifecycle: создание, настройка, удаление.
    
    Только superadmin может создавать/удалять tenant.
    Tenant self-service для white-label настроек.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        billing_service: BillingService,
    ) -> None:
        ...
    
    async def provision_tenant(
        self,
        data: TenantCreate,
    ) -> Tenant:
        """
        Полное создание tenant:
        1. Создать Tenant запись в БД
        2. Создать дефолтный канал Web Widget
        3. Создать дефолтного admin пользователя
        4. Создать дефолтную подписку (trial 14 дней)
        5. Установить дефолтные фичи (free tier)
        6. Установить дефолтные лимиты
        7. Создать Qdrant коллекцию для tenant
        8. Записать audit log
        """
        ...
    
    async def deprovision_tenant(
        self,
        tenant_id: UUID,
        hard_delete: bool = False,
    ) -> None:
        """
        Удаление tenant:
        1. Если hard_delete=False → soft-delete (is_active=False)
        2. Если hard_delete=True:
           a. Удалить все данные tenant (conversations, messages, etc)
           b. Удалить Qdrant коллекции
           c. Удалить Redis ключи (SCAN tenant:{tenant_id}:*)
           d. Удалить файлы
        3. Записать audit log
        """
        ...
    
    async def update_tenant_config(
        self,
        tenant_id: UUID,
        config: TenantUpdate,
    ) -> Tenant:
        """Обновить white-label настройки tenant."""
        ...
    
    async def get_tenant_stats(
        self,
        tenant_id: UUID,
        period: str = "30d",
    ) -> dict:
        """
        Статистика tenant:
        - active_users, total_conversations, messages_today
        - api_calls, tokens_used, cost_usd
        - top_intents, top_channels
        - storage_used_mb
        """
        ...
    
    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Tenant], int]:
        """Список tenant с пагинацией и фильтрацией."""
        ...
    
    async def migrate_tenant_data(
        self,
        from_tenant_id: UUID,
        to_tenant_id: UUID,
        tables: list[str] | None = None,
    ) -> dict:
        """
        Перенос данных между tenant.
        Используется при миграции/слиянии клиентов.
        """
        ...
    
    async def set_feature_flag(
        self,
        tenant_id: UUID,
        feature_key: str,
        is_enabled: bool,
    ) -> TenantFeature:
        """Включить/выключить фича-флаг для tenant."""
        ...
    
    async def update_limits(
        self,
        tenant_id: UUID,
        limit_key: str,
        limit_value: int,
    ) -> TenantLimit:
        """Обновить лимит для tenant."""
        ...
```

---

## 4. `services/billing_service.py` — BillingService

```python
class BillingService:
    """
    Управление подписками и биллингом.
    
    Stage 1: internal billing (ручная обработка платежей).
    Stage 3: Stripe/Paddle интеграция.
    """
    
    def __init__(self, db: AsyncSession) -> None:
        ...
    
    async def get_subscription(
        self, tenant_id: UUID
    ) -> TenantSubscription:
        """Текущая подписка tenant."""
        ...
    
    async def create_trial_subscription(
        self, tenant_id: UUID, plan_id: str = "starter"
    ) -> TenantSubscription:
        """
        Создать триал подписку.
        trial_ends_at = now + 14 дней.
        Статус: trial.
        """
        ...
    
    async def change_plan(
        self, tenant_id: UUID, new_plan_id: str
    ) -> TenantSubscription:
        """
        Сменить тарифный план.
        Если upgrade → немедленно.
        Если downgrade → с конца текущего периода.
        """
        ...
    
    async def cancel_subscription(
        self, tenant_id: UUID
    ) -> TenantSubscription:
        """Отменить подписку. Статус → cancelled."""
        ...
    
    async def check_subscription_status(
        self, tenant_id: UUID
    ) -> str:
        """
        Проверить статус подписки:
        - trial expired → downgrade to free
        - subscription expired → downgrade to free
        - past_due > 7 дней → suspend tenant
        """
        ...
    
    async def record_usage(
        self,
        tenant_id: UUID,
        metric: str,         # "api_calls", "tokens_used", "storage_bytes"
        value: float,
    ) -> UsageRecord:
        """Записать использование метрики."""
        ...
    
    async def check_usage_limits(
        self, tenant_id: UUID
    ) -> dict[str, bool]:
        """
        Проверить не превышены ли лимиты.
        Возвращает {"max_users": True, "max_api_calls": False}.
        """
        ...
    
    async def generate_invoice(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> Invoice:
        """Сгенерировать счёт."""
        ...
    
    async def get_usage_report(
        self,
        tenant_id: UUID,
        period: str = "current_month",
    ) -> dict:
        """Детальный отчёт об использовании."""
        ...
    
    async def get_credits_balance(
        self, tenant_id: UUID
    ) -> dict:
        """Баланс предоплаченных кредитов для AI inference."""
        ...
    
    async def add_credits(
        self, tenant_id: UUID, amount_usd: float
    ) -> None:
        """Добавить кредиты."""
        ...
    
    async def get_available_plans(self) -> list[SubscriptionPlan]:
        """Список доступных тарифных планов."""
        ...
```

---

## 5. `middleware/auth_rate_limit.py` — AuthRateLimitMiddleware

```python
class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting на auth endpoints — IP-based, ДО tenant resolution.
    
    RateLimitMiddleware работает на уровне tenant, но auth происходит
    до идентификации tenant → нужен отдельный middleware.
    
    Enforced only for paths matching /auth/*.
    
    Лимиты:
    - POST /auth/login: 5 попыток/минуту/IP
    - POST /auth/signup: 3 попытки/час/IP
    - POST /auth/verify: 10 попыток/минуту/IP
    - POST /auth/refresh: 20 попыток/минуту/IP
    - POST /auth/mfa/verify: 3 попытки/минуту/IP
    
    Storage: Redis key auth_rate:{path}:{ip}:{window_timestamp}
    Превышение: HTTP 429 + Retry-After.
    """
    
    ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
        "/auth/login": (5, 60),          # 5 в минуту
        "/auth/signup": (3, 3600),       # 3 в час
        "/auth/verify": (10, 60),
        "/auth/refresh": (20, 60),
        "/auth/mfa/verify": (3, 60),
        "/auth/login/password": (5, 60),
        "/auth/login/magic-link": (10, 60),
        "/auth/login/passkey/complete": (10, 60),
    }
    
    def __init__(self, app, redis: Redis) -> None: ...
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        1. Если path не /auth/* → пропустить
        2. Получить IP (X-Forwarded-For, затем client.host)
        3. Найти лимиты для path (exact match, затем prefix)
        4. Redis INCR + EXPIRE для учёта
        5. Если превышен → 429 + Retry-After
        6. Добавить X-RateLimit-* заголовки
        """
        ...
    
    def _get_client_ip(self, request: Request) -> str:
        """Извлечь IP учитывая reverse proxy."""
        forwarded = request.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() if forwarded else request.client.host
    
    def _get_rate_key(self, path: str, ip: str, window: int) -> str:
        """Redis ключ: auth_rate:/auth/login:192.168.1.1:1719360000"""
        window_ts = int(time.time() / window) * window
        return f"auth_rate:{path}:{ip}:{window_ts}"
```

---

## 6. `middleware/rate_limit.py` — RateLimitMiddleware

```python
class TokenBucket:
    """Реализация token bucket алгоритма на Redis."""
    
    def __init__(self, redis: Redis, key: str, capacity: int, refill_rate: float) -> None:
        ...
    
    async def consume(self, tokens: int = 1) -> bool:
        """
        Попробовать потребить токены.
        Возвращает True если лимит не превышен.
        Redis-backed: атомарные операции.
        """
        ...
    
    async def get_remaining(self) -> int:
        """Оставшиеся токены."""
        ...

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware — per-tenant.
    
    Конфигурация из TenantLimit:
    - max_api_calls_per_minute: 100 (free), 1000 (starter), 10000 (pro)
    - max_conversations_per_day: 50 (free), 500 (starter), unlimited (pro)
    
    Возвращает заголовки:
    - X-RateLimit-Limit: максимальное количество запросов
    - X-RateLimit-Remaining: оставшиеся
    - X-RateLimit-Reset: когда сбросится окно
    
    При превышении: HTTP 429 + Retry-After.
    """
    
    def __init__(self, app, redis: Redis) -> None: ...
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        1. Получить tenant_id из contextvar
        2. Загрузить лимиты для tenant (из кэша)
        3. Проверить endpoint-specific лимит
        4. Проверить global tenant лимит
        5. Добавить rate limit заголовки в ответ
        """
        ...
    
    async def get_tenant_limits(
        self, tenant_id: UUID
    ) -> dict[str, int]:
        """Загрузить лимиты tenant из кэша/БД."""
        ...

async def check_rate_limit(
    request: Request,
    tenant_id: UUID,
    redis: Redis,
) -> None:
    """
    Dependency для FastAPI — проверка rate limit на уровне роута.
    Использование:
    @router.post("/messages", dependencies=[Depends(check_rate_limit)])
    """
    ...

def get_rate_limit_headers(
    limit: int, remaining: int, reset_at: float
) -> dict[str, str]:
    """Сгенерировать RateLimit заголовки."""
    ...
```

---

## 6. Subscription Plans (seed данные)

```python
# 0002_add_tenant_features_and_limits.py — seed данные

SUBSCRIPTION_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price_monthly_usd": 0,
        "features": ["chat", "web_widget", "faq", "echo"],
        "limits": {
            "max_users": 1,
            "max_channels": 1,
            "max_conversations_per_day": 20,
            "max_api_calls_per_minute": 10,
            "max_storage_mb": 100,
            "max_service_plugins": 2,
        },
    },
    {
        "id": "starter",
        "name": "Starter",
        "price_monthly_usd": 49,
        "features": ["chat", "web_widget", "telegram", "email", "faq", "scheduler", "form", "classifier", "escalation", "knowledge_base"],
        "limits": {
            "max_users": 5,
            "max_channels": 3,
            "max_conversations_per_day": 500,
            "max_api_calls_per_minute": 100,
            "max_storage_mb": 1000,
            "max_service_plugins": 5,
        },
    },
    {
        "id": "professional",
        "name": "Professional",
        "price_monthly_usd": 149,
        "features": ["chat", "web_widget", "telegram", "email", "rest_api", "faq", "scheduler", "form", "classifier", "escalation", "knowledge_base", "analytics", "white_label"],
        "limits": {
            "max_users": 20,
            "max_channels": 10,
            "max_conversations_per_day": 5000,
            "max_api_calls_per_minute": 1000,
            "max_storage_mb": 10000,
            "max_service_plugins": 20,
        },
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly_usd": 499,
        "features": ["*"],  # всё
        "limits": {
            "max_users": 999999,
            "max_channels": 999,
            "max_conversations_per_day": 999999,
            "max_api_calls_per_minute": 10000,
            "max_storage_mb": 100000,
            "max_service_plugins": 999,
        },
    },
]
```

---

## 7. Isolation Guarantees — тесты

```python
# tests/integration/test_tenant_isolation.py

async def test_cross_tenant_data_inaccessible(
    async_client: AsyncClient,
    tenant_a: Tenant,
    tenant_b: Tenant,
):
    """
    Tenant A не может видеть данные Tenant B.
    
    1. Создать conversation в tenant_a
    2. Попытаться прочитать через tenant_b → 404
    """

async def test_rls_prevents_cross_tenant_write(
    db_session: AsyncSession,
    tenant_a_id: UUID,
    tenant_b_id: UUID,
):
    """
    PostgreSQL RLS не даёт записать message с tenant_b_id 
    когда app.current_tenant_id = tenant_a_id.
    """

async def test_tenant_context_not_leaking_between_requests(
    async_client: AsyncClient,
):
    """
    ContextVar изолирован — после запроса tenant_id сбрасывается.
    """

async def test_redis_keys_isolated(
    redis: Redis,
    tenant_a_id: UUID,
    tenant_b_id: UUID,
):
    """
    Redis ключи tenant_a не видны tenant_b.
    tenant:{tenant_a}:* ≠ tenant:{tenant_b}:*
    """
```

---

## 8. Organisation Model — ролевая модель организации

### Концепция

**Регистрация организации → invitation сотрудников → роли внутри организации.**

Это не просто tenant — это Workspace с командой. Аналоги: Slack, Notion, Linear, Intercom.

```
User регистрирует Organisation
  → становится Owner
  → приглашает сотрудников по email
  → сотрудник получает magic link / invitation link
  → выбирает роль: Admin / Member / Viewer
  → попадает в Workspace
```

### `models/organisation.py`

```python
class Organisation(Base, TimestampMixin):
    """Организация — это tenant в Aether. Каждая организация = один workspace."""
    __tablename__ = "organisations"
    id: UUID = primary key
    slug: str(100) — unique, URL-safe
    name: str(255)
    logo_url: str | None
    primary_color: str — default "#6366f1"
    timezone: str — default "UTC"
    locale: str — default "ru"
    is_active: bool — default True
    created_at: datetime
    updated_at: datetime

class Membership(Base, TimestampMixin):
    """Связь User ↔ Organisation с ролью."""
    __tablename__ = "memberships"
    id: UUID
    user_id: UUID — FK users.id
    organisation_id: UUID — FK organisations.id
    role: enum(OrganisationRole) — owner, admin, member, viewer
    is_active: bool — default True
    invited_at: datetime
    accepted_at: datetime | None
    invited_by: UUID | None — FK users.id (кто пригласил)

class OrganisationRole(str, Enum):
    OWNER = "owner"          # Создал организацию. Может всё + удалить организацию.
    ADMIN = "admin"          # Управление: каналы, сервисы, пользователи, биллинг
    MEMBER = "member"        # Работа с диалогами, документами
    VIEWER = "viewer"        # Только просмотр: аналитика, аудит

class OrganisationInvite(Base, TimestampMixin):
    """Приглашение в организацию."""
    __tablename__ = "organisation_invites"
    id: UUID
    organisation_id: UUID — FK organisations.id
    email: str(255)
    role: enum(OrganisationRole) — предлагаемая роль
    token: str(512) — SHA-256 хеш, передаётся в ссылке plaintext
    invited_by: UUID — FK users.id
    status: enum(InviteStatus) — pending, accepted, expired, revoked
    expires_at: datetime — default now() + 7d
    accepted_at: datetime | None

class InviteStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"
```

### Permission Matrix

| Действие | Owner | Admin | Member | Viewer |
|----------|-------|-------|--------|--------|
| Управление каналами | ✅ | ✅ | ❌ | ❌ |
| Управление сервисами | ✅ | ✅ | ❌ | ❌ |
| AI-настройки | ✅ | ✅ | ❌ | ❌ |
| Приглашение пользователей | ✅ | ✅ | ❌ | ❌ |
| Удаление пользователей | ✅ | ✅ | ❌ | ❌ |
| Изменение ролей | ✅ | ✅ | ❌ | ❌ |
| Биллинг и подписка | ✅ | ✅ | ❌ | ❌ |
| Работа с диалогами | ✅ | ✅ | ✅ | ❌ |
| Отправка документов | ✅ | ✅ | ✅ | ❌ |
| Просмотр аналитики | ✅ | ✅ | ✅ | ✅ |
| Просмотр аудита | ✅ | ✅ | ✅ | ✅ |
| Удаление организации | ✅ | ❌ | ❌ | ❌ |
| Передача ownership | ✅ | ❌ | ❌ | ❌ |

### `services/organisation_service.py`

```python
class OrganisationService:
    """Управление организациями, участниками и приглашениями."""
    
    def __init__(self, db: AsyncSession, email_service: EmailService) -> None: ...
    
    async def create_organisation(
        self, user_id: UUID, data: OrganisationCreate
    ) -> Organisation:
        """
        Создать организацию:
        1. Создать Organisation запись
        2. Создать Membership (role=owner)
        3. Provision: дефолтный Web Widget канал
        4. Создать trial подписку
        5. Отправить welcome email
        """
        ...
    
    async def invite_member(
        self,
        organisation_id: UUID,
        invited_by: UUID,
        email: str,
        role: OrganisationRole,
    ) -> OrganisationInvite:
        """
        Пригласить пользователя в организацию:
        1. Проверить что invited_by имеет право приглашать
        2. Проверить что email ещё не в организации
        3. Создать OrganisationInvite с token
        4. Отправить email с invitation link
        5. Вернуть invite (токен ТОЛЬКО в email, не в ответе API)
        """
        ...
    
    async def accept_invitation(
        self, token: str, user_id: UUID
    ) -> Membership:
        """
        Принять приглашение:
        1. Найти invite по token (SHA-256 хеш)
        2. Проверить статус pending + не истёк
        3. Создать Membership
        4. Пометить invite accepted
        5. Отправить уведомление пригласившему
        """
        ...
    
    async def revoke_invitation(
        self, invite_id: UUID, revoked_by: UUID
    ) -> None:
        """Отозвать приглашение."""
        ...
    
    async def change_role(
        self,
        organisation_id: UUID,
        user_id: UUID,
        new_role: OrganisationRole,
        changed_by: UUID,
    ) -> Membership:
        """Изменить роль участника. Только owner/admin."""
        ...
    
    async def remove_member(
        self,
        organisation_id: UUID,
        user_id: UUID,
        removed_by: UUID,
    ) -> None:
        """Удалить участника из организации."""
        ...
    
    async def transfer_ownership(
        self,
        organisation_id: UUID,
        new_owner_id: UUID,
        current_owner_id: UUID,
    ) -> None:
        """Передать ownership. Только owner → owner."""
        ...
    
    async def get_members(
        self, organisation_id: UUID
    ) -> list[Membership]:
        """Список участников организации."""
        ...
    
    async def get_pending_invites(
        self, organisation_id: UUID
    ) -> list[OrganisationInvite]:
        """Список непринятых приглашений."""
        ...
```

---

## 9. Auth v2 — современная регистрация и логин

### Принципы (2025-2026 best practices)

1. **Passwordless-first**: magic link по умолчанию, пароль — опционально
2. **Single-field signup**: только email → проверка → welcome
3. **Passkeys (WebAuthn)**: для returning users — биометрия/security key
4. **Social OAuth**: Google, GitHub (для РФ — Яндекс ID, VK ID)
5. **MFA**: TOTP, hardware keys (обязательно для admin/owner)
6. **SSO (OIDC/SAML)**: Okta, Azure AD, Keycloak (Stage 3 enterprise)

### Flow: Регистрация новой организации

```
Пользователь → /signup
  → Вводит: email, имя компании
  → Система: создаёт Organisation + User (role=owner) + Membership
  → Отправляет magic link на email
  → Пользователь кликает ссылку → /auth/verify?token=xxx
  → Устанавливает имя, пароль (опционально), аватар
  → Попадает в Workspace → onboarding wizard
```

### Flow: Приглашение сотрудника

```
Owner/Admin → Settings → Users → Invite
  → Вводит email сотрудника
  → Выбирает роль (Admin/Member/Viewer)
  → Система: создаёт OrganisationInvite
  → Отправляет email: "Вас пригласили в [Компания] на Aether"
  → Сотрудник кликает → если нет аккаунта → signup
  → Если есть аккаунт → /invitations/{token} → Accept
  → Попадает в Workspace
```

### Flow: Ежедневный логин

```
Пользователь → /login
  → Вводит email
  → Система проверяет:
    - Есть passkey? → предложить WebAuthn (биометрия)
    - Есть пароль? → поле пароля
    - Ни того ни другого? → magic link
  → После логина → выбор Workspace (если несколько организаций)
```

### `services/auth_service.py` — обновлённый

```python
class AuthService:
    """Современная аутентификация: passwordless-first + passkeys + OAuth."""
    
    async def signup(
        self, email: str, company_name: str
    ) -> SignupResult:
        """
        Single-field регистрация:
        1. Проверить email не занят
        2. Создать User (без пароля)
        3. Создать Organisation + Membership (owner)
        4. Сгенерировать verification token
        5. Отправить magic link email
        """
        ...
    
    async def verify_signup(
        self, token: str
    ) -> VerifyResult:
        """
        Подтверждение регистрации по magic link:
        1. Проверить токен (SHA-256 хеш, не храним plaintext)
        2. Активировать User
        3. Создать сессию (access + refresh токены)
        4. Вернуть User + Organisation + токены
        """
        ...
    
    async def login(
        self, email: str
    ) -> LoginChallenge:
        """
        Начало логина — возвращает доступные методы:
        - has_passkey: bool
        - has_password: bool
        - magic_link_sent: bool
        
        Если нет passkey/password → автоматически отправляет magic link.
        """
        ...
    
    async def login_with_password(
        self, email: str, password: str
    ) -> LoginResult:
        """Логин с паролем + проверка MFA если включена."""
        ...
    
    async def login_with_passkey(
        self, credential_id: str, authenticator_data: bytes, ...
    ) -> LoginResult:
        """Логин через WebAuthn passkey."""
        ...
    
    async def login_with_magic_link(
        self, token: str
    ) -> LoginResult:
        """Логин по magic link из email."""
        ...
    
    async def register_passkey(
        self, user_id: UUID, credential: WebAuthnCredential
    ) -> None:
        """Зарегистрировать passkey для пользователя."""
        ...
    
    async def setup_mfa(
        self, user_id: UUID
    ) -> MfaSetupResult:
        """
        Настроить MFA:
        1. Сгенерировать TOTP secret
        2. Вернуть QR code URI (otpauth://)
        3. Потребовать верификационный код
        """
        ...
    
    async def verify_mfa(
        self, user_id: UUID, code: str
    ) -> bool:
        """Проверить TOTP код."""
        ...
    
    async def oauth_callback(
        self, provider: str, code: str, state: str
    ) -> OAuthResult:
        """
        OAuth callback (Google, Yandex ID, VK ID):
        1. Обменять code на access_token
        2. Получить профиль пользователя
        3. Найти или создать User
        4. Вернуть сессию
        """
        ...
    
    async def switch_workspace(
        self, user_id: UUID, organisation_id: UUID
    ) -> SessionTokens:
        """
        Переключиться между Workspace.
        Возвращает новые токены с organisation_id в JWT claims.
        """
        ...
    
    async def get_available_workspaces(
        self, user_id: UUID
    ) -> list[WorkspaceInfo]:
        """Список организаций пользователя (может быть в нескольких)."""
        ...
```

### `schemas/auth.py`

```python
class SignupRequest(BaseModel):
    email: EmailStr
    company_name: str — min 2, max 100
    locale: str = "ru"

class LoginRequest(BaseModel):
    email: EmailStr

class LoginChallenge(BaseModel):
    has_passkey: bool
    has_password: bool
    has_mfa: bool
    magic_link_sent: bool
    passkey_options: dict | None — WebAuthn PublicKeyCredentialRequestOptions

class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int — 3600 (1 час)
    token_type: str = "bearer"
    user: UserResponse
    workspace: WorkspaceInfo

class WorkspaceInfo(BaseModel):
    organisation_id: UUID
    slug: str
    name: str
    logo_url: str | None
    role: OrganisationRole
```

### API endpoints (добавить к существующим)

| Метод | Путь | Функция | Описание |
|-------|------|---------|----------|
| POST | `/auth/signup` | `signup()` | Регистрация компании (email + название) |
| POST | `/auth/verify` | `verify_signup()` | Подтверждение по magic link |
| POST | `/auth/login` | `begin_login()` | Начало логина → возвращает доступные методы |
| POST | `/auth/login/password` | `login_password()` | Логин с паролем |
| POST | `/auth/login/magic-link` | `login_magic_link()` | Логин по magic link |
| POST | `/auth/login/passkey/begin` | `begin_passkey_login()` | Начать WebAuthn аутентификацию |
| POST | `/auth/login/passkey/complete` | `complete_passkey_login()` | Завершить WebAuthn |
| POST | `/auth/passkeys` | `register_passkey()` | Зарегистрировать passkey |
| GET | `/auth/passkeys` | `list_passkeys()` | Список passkey пользователя |
| DELETE | `/auth/passkeys/{id}` | `remove_passkey()` | Удалить passkey |
| POST | `/auth/mfa/setup` | `setup_mfa()` | Начать настройку MFA |
| POST | `/auth/mfa/verify` | `verify_mfa()` | Подтвердить MFA |
| POST | `/auth/mfa/disable` | `disable_mfa()` | Отключить MFA |
| POST | `/auth/refresh` | `refresh_token()` | Обновить access токен |
| POST | `/auth/logout` | `logout()` | Выход |
| GET | `/auth/workspaces` | `list_workspaces()` | Список организаций пользователя |
| POST | `/auth/workspaces/{id}/switch` | `switch_workspace()` | Переключить Workspace |
| GET | `/auth/oauth/{provider}` | `oauth_redirect()` | Редирект на OAuth провайдера |
| GET | `/auth/oauth/{provider}/callback` | `oauth_callback()` | OAuth callback |

---

## 📊 Статистика модуля

| Компонент | Файл | Классов | Методов/Функций |
|-----------|------|---------|-----------------|
| TenantContext | core/tenant_context.py | 1 dataclass | 3 функции |
| TenantMiddleware | middleware/tenant.py | 1 класс + 1 dataclass | 5 методов + 3 функции |
| RateLimitMiddleware | middleware/rate_limit.py | 2 класса | 4 функции |
| AuditMiddleware | middleware/audit.py | 1 класс | 1 функция |
| TenantService | services/tenant_service.py | 1 класс | 8 методов |
| BillingService | services/billing_service.py | 1 класс | 10 методов |
| API | api/v1/tenants.py + billing.py | 0 | 14 эндпоинтов |
| Модели | models/tenant.py + billing.py + audit.py | 13 классов | 0 |
| Миграции | alembic/versions/* | 0 | 6 функций |
| **Итого** | **~12 файлов** | **~20 классов** | **~54 методов** |
