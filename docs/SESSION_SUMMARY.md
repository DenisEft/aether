# Aether Session Summary — 2026-07-02

> Сгенерировано Лорой, компактификация контекста аезер-треда
> Исходные сессии: `cf7b9787`, `473b18ca` (родитель), `b5401fdb` (дед)
> Суммарный объём логов: ~4.2 MB

## Контекст

Денис обнаружил, что в aether (общая SaaS-платформа) просочилась логистическая/морская доменная логика из logicore. Задача: вычистить логистику, сделать aether чисто SaaS-платформой, написать независимые спецификации.

## Что сделано (4 коммита в master)

### 1. Спецификации (fffc762)
Создано 8 спецификаций + 2 архитектурных документа (5,695 строк):
- `auth-spec.md` — Auth flow (signup, login, magic link, MFA, passkeys, OAuth, JWT, refresh rotation)
- `plugin-sdk.md` — Plugin SDK контракт (BaseServicePlugin, Capability, Intent, Action, ServiceResult)
- `ai-routing.md` — AI Smart Router (Multi-Driver, SmartRouter, InferencePool, Driver Interface)
- `channel-protocol.md` — Канальный протокол (NormalizedMessage, DeliveryResult, ChannelCapability)
- `tenant-provisioning.md` — Tenant provisioning (lifecycle, RLS, white-label, feature flags)
- `celery-tasks.md` — Celery task definitions
- `websocket-protocol.md` — WebSocket протокол
- `openapi.yaml` — OpenAPI спецификация
- `schema.sql` — Схема БД
- Архитектурные документы: `backend.md`, `overview.md`

### 2. Plugin SDK (b888d6c)
14 файлов, 23 теста, 7 builtin плагинов:
- **Base SDK:** `base.py` (BaseServicePlugin, Intent, PluginManifest, Action, PluginResult, PluginContext, PluginHealth, PluginStatus)
- **Prompt-driven:** `prompt_driver.py` (PromptDrivenPlugin — конфигурация через prompt + examples)
- **Registry:** `registry.py` (PluginRegistry — register, get, list, unregister)
- **Loader:** `loader.py` (PluginLoader — авто-загрузка из builtin/)
- **Builtin плагины:**
  - `echo.py` — EchoPlugin (эхо-ответ)
  - `classifier.py` — ClassifierPlugin (интент-классификация)
  - `faq.py` — FaqPlugin (prompt-driven FAQ)
  - `escalation.py` — EscalationPlugin (transfer_to_human)
  - `form.py` — FormPlugin (state-machine для многошаговых форм)
  - `scheduler.py` — SchedulerPlugin (prompt-driven, бронирования)
  - `knowledge_base.py` — KnowledgeBasePlugin (поиск по базе знаний)
- **Тесты:** `test_base.py`, `test_registry.py`, `test_prompt_driver.py`, `test_builtins.py`

### 3. AI Smart Router (3e3ea59)
- `drivers/base.py` — BaseDriver, InferenceRequest, InferenceResponse, DriverCapability, DriverStatus
- `smart_router.py` — SmartRouter с RoutingStrategy (cost, latency, quality, fallback)
- `inference_pool.py` — InferencePool (health check, load balancing)
- `model_registry.py` — ModelRegistry, ModelInfo
- `embedding_service.py` — EmbeddingService

### 4. CircuitBreaker + ContextManager (294b06c)
- `circuit_breaker.py` — CircuitBreaker (open/half-open/closed states)
- `context_manager.py` — ContextManager (tenant context via ContextVar)

### 5. Дополнительно (субагенты)
- **Auth:** Passkey модель (поля в models/auth.py), MFA утилиты (security.py), OAuth stub
- **Аудит:** Вычищена логистическая лексика (ETRN, waybill, wagon_number, cargo_type, vessel_name, port_name, customs_declaration)
- **DocumentType enum:** Убраны "etrn" и "waybill", оставлены: order, invoice, contract, custom

## Статус тестов
- **129 тестов green** (106 старых + 23 новых плагин-тестов)

## Состояние на момент остановки

### Готово ✅
- Все спецификации написаны
- Plugin SDK полностью реализован и протестирован
- AI Smart Router: базовая архитектура готова
- CircuitBreaker + ContextManager готовы
- Логистическая лексика вычищена из документации и кода

### Осталось ❌
- **Auth:** Passkeys API endpoints, MFA endpoints, OAuth callback'и
- **Tenant:** TenantService lifecycle, provisioning (схема готова в спеке)
- **Channels:** MessageNormalizer, DeliveryResult, EmailChannel доработка
- **Интеграция:** AI routing → ws.py

### Проблемы
- Два субагента (98bd94b4 и 8b333b20) зависли в статусе running — вероятно бесконечный цикл
- Сессия переполнилась (context too large), потребовался /new

## Файловая структура (ключевые файлы)

```
aether/
├── backend/
│   ├── app/
│   │   ├── plugins/
│   │   │   ├── base.py              ← Plugin SDK основа
│   │   │   ├── prompt_driver.py     ← PromptDrivenPlugin
│   │   │   ├── registry.py
│   │   │   ├── loader.py
│   │   │   └── builtin/
│   │   │       ├── echo.py, classifier.py, faq.py
│   │   │       ├── escalation.py, form.py
│   │   │       ├── scheduler.py, knowledge_base.py
│   │   ├── ai/
│   │   │   ├── drivers/base.py
│   │   │   ├── smart_router.py
│   │   │   ├── inference_pool.py
│   │   │   ├── model_registry.py
│   │   │   ├── embedding_service.py
│   │   │   ├── circuit_breaker.py
│   │   │   └── context_manager.py
│   │   └── models/
│   │       ├── auth.py              ← Passkey поля добавлены
│   │       └── enums.py             ← DocumentType очищен
│   └── tests/
│       └── plugins/
│           ├── test_base.py, test_registry.py
│           ├── test_prompt_driver.py, test_builtins.py
└── docs/
    ├── specs/
    │   ├── auth-spec.md, plugin-sdk.md, ai-routing.md
    │   ├── channel-protocol.md, tenant-provisioning.md
    │   ├── celery-tasks.md, websocket-protocol.md
    │   ├── openapi.yaml, schema.sql
    └── architecture/
        ├── overview.md, backend.md
```

## Следующие шаги (для продолжения)
1. Убить зависшие субагенты (98bd94b4, 8b333b20)
2. Passkeys API endpoints + тесты
3. MFA endpoints (TOTP setup/verify)
4. TenantService с provisioning flow
5. MessageNormalizer для каналов
6. Интеграция AI routing в WebSocket handler
