# 🗂 Aether — Project Architecture Graph

_Источник правды для аудита и планирования. Генерируется вручную, обновляется при изменениях._

**Статус:** Stage 1 — архитектурное проектирование (аудит завершён: 28 проблем, 5 critical закрыты)  
**Объём:** 7 документов, 5,286 строк, ~216 KB  
**Стек:** Python FastAPI + PostgreSQL + Redis + Celery  
**Принцип:** White-label SaaS. Никакого хардкода. Plugin architecture. Tenant isolation.

---

## 📋 Модули

| Модуль | Описание | Файл |
|--------|----------|------|
| 📁 `backend` | Бэкенд — FastAPI, ORM, AI Core, Channels, Plugins, Tenant | [`docs/architecture/backend.md`](./architecture/backend.md) |
| 📁 `channels` | Система каналов — Telegram, Web Widget, Email, WhatsApp, REST API | [`docs/architecture/channels.md`](./architecture/channels.md) |
| 📁 `ai-core` | AI-ядро — inference drivers, intent classifier, entity extraction, embedding | [`docs/architecture/ai-core.md`](./architecture/ai-core.md) |
| 📁 `tenant` | Мультитенантность — isolation, billing, rate limiting, white-label | [`docs/architecture/tenant.md`](./architecture/tenant.md) |
| 📁 `services` | Plugin system — бизнес-логика как подключаемые модули | [`docs/architecture/services.md`](./architecture/services.md) |
| 📁 `frontend` | Фронтенд — Admin Dashboard + Client Workspace (раздельные SPA) | [`docs/architecture/frontend.md`](./architecture/frontend.md) |
| 📁 `devops` | Инфраструктура — Docker, CI/CD, миграции, мониторинг | [`docs/architecture/devops.md`](./architecture/devops.md) |
| 📁 `tests` | Тесты — unit, integration, contract, e2e | [`docs/architecture/tests.md`](./architecture/tests.md) |
| 📋 `audit` | Аудит архитектуры — 28 проблем (5 critical, 8 high, 8 medium, 7 low) | [`docs/AUDIT.md`](../AUDIT.md) |

---

## 🎯 Архитектурные принципы

### 1. Zero Hardcode
- Channel types — enum из БД, не if/else
- Service plugins — dynamic registry, не switch-case
- AI models — driver-based, конфигурируются per tenant
- Feature flags — database-driven, не #ifdef

### 2. Contract-First API
- OpenAPI 3.1 спека → генерация Pydantic моделей
- JSON Schema для всех входов/выходов
- End-to-end type safety: Python ↔ TypeScript через OpenAPI

### 3. Security by Design
- Row-Level Security (PostgreSQL RLS)
- Tenant isolation: ContextVar + RLS + Redis prefix
- Auth rate limiting: IP-based + tenant-based
- Credentials encrypted at rest (AES-256-GCM)

### 4. Tenant Isolation (Row-Level Security)
- Каждая таблица имеет `tenant_id UUID NOT NULL`
- PostgreSQL RLS: `CREATE POLICY tenant_isolation USING (tenant_id = current_setting('app.current_tenant_id')::UUID)`
- Application-level: `ContextVar[TenantContext]` + проверка в каждом сервисе
- Redis keys: `tenant:{tenant_id}:*`
- File storage: `{tenant_id}/...`

### 5. Channel Abstraction
- Все каналы реализуют `BaseChannel` (ABC)
- `ChannelRouter` маршрутизирует сообщения независимо от канала
- Добавление нового канала = новый adapter + запись в БД, без изменения core

### 6. Plugin Architecture
- Бизнес-логика живёт в плагинах, НЕ в ядре
- `BaseServicePlugin` (ABC) — контракт для всех плагинов
- `PluginRegistry` — динамическая дискавери и загрузка
- Prompt-driven плагины для non-code конфигурации (Stage 1)
- Custom Python плагины для enterprise (Stage 3)

### 7. AI Core — Multi-Driver
- Драйверный слой как в ai-ops: Ollama, LlamaCpp, OpenAI, vLLM
- Smart routing: выбор модели по стоимости/латентности/приватности
- Tenant-specific model routing: локально для приватности, облачно для overflow

### 8. Admin Dashboard ≠ Client Workspace
- **Admin Cabinet** (`/aether/admin/`) — управление платформой: tenants, subscriptions, плагины, drivers, аудит. Доступен только superadmin роли.
- **Client Workspace** (`/aether/{tenant-slug}/`) — email-client layout (трёхпанельный inbox). Управление СВОИМ бизнесом: каналы, AI-настройки, сервисы, пользователи, аналитика.
- **Никакого mixing:** вкладки клиента не содержат платформенных настроек. Одна форма ≠ целая страница.
- **Принцип:** если клиенту нужна 1 форма → она на той же странице, не отдельный route. Сгруппировано по смыслу, не по типу данных.

### 9. Organisation Model — ролевая модель организации
- **Регистрация компании** → Owner приглашает сотрудников по email → роли (Admin/Member/Viewer)
- **Membership** связывает User с Organisation через роль
- **Permission matrix:** owner/admin управляют каналами и сервисами, members работают с диалогами
- **Invitation flow:** email с ссылкой → принятие → сразу в Workspace

### 10. Auth — Passwordless-First (2025+ стандарт)
- **Single-field signup:** только email + название компании → magic link
- **Smart login:** email → система определяет доступные методы (passkey/password/magic link)
- **Passkeys (WebAuthn):** биометрия для returning users
- **OAuth:** Google, Яндекс ID, VK ID
- **MFA:** TOTP + hardware keys (обязательно для admin/owner)
- **SSO:** OIDC/SAML для enterprise (Stage 3)

### 11. API Versioning
- Мажорные версии: `/api/v1/`, `/api/v2/`
- Deprecation: `Sunset` header, 6 месяцев поддержка v1 после v2
- Webhook-first для асинхронных событий
- SDK-генерация из OpenAPI спеки

---

## 🔄 Data Flow (полный цикл воронки)

```
┌──────────────────────────────────────────────────────────────────┐
│                        INCOMING (Channel)                        │
│                                                                  │
│  Telegram Msg ─┐                                                 │
│  Web Widget ───┼──► ChannelRouter ──► MessageNormalizer          │
│  Email ────────┘        │                  │                     │
│                         │                  ▼                     │
│                         │        NormalizedMessage               │
│                         │        {tenant_id, channel, text,      │
│                         │         attachments, metadata}         │
└─────────────────────────┼───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                       AI CORE                                    │
│                                                                  │
│  ┌────────────────┐    ┌──────────────┐    ┌──────────────────┐ │
│  │ Intent         │───►│ Entity       │───►│ Service Router   │ │
│  │ Classifier     │    │ Extractor    │    │ (Intent→Plugin)  │ │
│  └────────────────┘    └──────────────┘    └────────┬─────────┘ │
│                                                     │           │
│  ┌──────────────────────────────────────────────────▼─────────┐ │
│  │              Inference Pool (Multi-Driver)                  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │ │
│  │  │  Llama   │  │  vLLM    │  │  OpenAI  │  ...             │ │
│  │  │  Driver  │  │  Driver  │  │  Driver  │                  │ │
│  │  └──────────┘  └──────────┘  └──────────┘                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                     SERVICE LAYER                                │
│                                                                  │
│  PluginRegistry ──► Matched Plugin ──► handle_intent()           │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                  │
│  │ Logistics  │  │  FAQ       │  │  Scheduler │  ...            │
│  │ PluginPack │  │  Plugin    │  │  Plugin    │                  │
│  └────────────┘  └────────────┘  └────────────┘                  │
│       │                                                            │
│       ▼                                                            │
│  ActionExecutor.execute(actions)                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ send_message | call_api | wait_for_input | schedule_task   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      OUTGOING (Channel)                          │
│                                                                  │
│  Response ──► ChannelRouter ──► Telegram / Web / Email           │
│                                                                  │
│  Delivery tracking: status, timestamp, channel confirmation      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 Сводка компонентов

| Компонент | Файлов | Классов | Функций | Ответственность |
|-----------|--------|---------|---------|----------------|
| Backend Core | ~15 | ~25 | ~40 | FastAPI entry, config, security, middleware |
| Models (ORM) | ~10 | ~35 | ~5 | PostgreSQL модели, миграции |
| API (v1) | ~12 | ~0 | ~80 | REST endpoints, webhooks |
| Channels | ~8 | ~12 | ~30 | Channel adapters, router |
| AI Core | ~10 | ~18 | ~25 | Inference, NLP, embedding |
| Plugins | ~15 | ~20 | ~35 | Service plugins, registry, builtins |
| Tenant | ~6 | ~12 | ~25 | Multi-tenancy, billing, rate limits |
| Frontend | ~25 | ~15 | ~40 | Vue 3 dashboard, components |
| DevOps | ~8 | ~0 | ~5 | Docker, CI/CD, monitoring |
| Tests | ~20 | ~0 | ~200+ | Unit, integration, contract |

---

## 🤖 Для агентов

При планировании задач:
1. Открой нужный модуль: `docs/architecture/<module>.md`
2. Найди директорию с кодом, который нужно изменить
3. Посмотри классы/методы в Python, компоненты/функции в Vue/TS
4. Учитывай зависимости между модулями (AI Core зависит от Channels, Services зависит от AI Core)

### Порядок имплементации

```
Stage 1: Foundation
  1. backend/app/core/      (config, security, deps, tenant_context)
  2. backend/app/models/    (все модели БД)
  3. backend/alembic/       (миграции)
  4. backend/app/middleware/ (tenant, rate_limit, audit)

Stage 2: Channels + Frontend
  5. backend/app/services/channels/ (BaseChannel + Telegram + Web Widget)
  6. frontend/admin/              (Admin Dashboard)
  7. frontend/client/             (Client Workspace — бизнес-кабинеты)
  8. frontend/shared/             (UI kit, composables, types)

Stage 3: Integration
  9. backend/app/services/ai/       (drivers, classifier, extractor — AI core)
  10. backend/app/services/plugins/  (BasePlugin, registry, builtins)
  11. backend/app/api/              (REST endpoints)
  12. backend/app/services/         (orchestration: router, executor)
  13. backend/app/tasks/           (Celery tasks, notifications)

Stage 4: Production
  12. infra/                       (Docker, CI/CD, monitoring)
  13. backend/tests/               (полное покрытие)
  14. Логистический service-pack   (GU12, ETRAN, Calculator)
```
