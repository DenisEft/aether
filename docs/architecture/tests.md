# 📁 Tests — Тестовая стратегия Aether

Комплексное тестирование всех слоёв: unit → integration → contract → e2e.

**Принцип:** Каждый слой тестируется изолированно. Интеграционные тесты проверяют швы между слоями. E2E — полный путь пользователя.

---

## 📊 Обзор

```
backend/tests/
├── conftest.py                      # Глобальные фикстуры (246 строк)
├── test_security.py                 # Безопасность: пароли, токены, шифрование
├── api/
│   └── v1/
│       ├── test_auth.py             # Auth flow (201 строка)
│       ├── test_billing.py          # Billing + usage (66 строк)
│       ├── test_health.py           # Health endpoint
│       ├── test_infer_billing.py    # Интеграция billing в /infer
│       └── test_tenants.py          # Tenant CRUD + миграции
└── services/
    ├── conftest.py                  # Сервисные фикстуры
    ├── test_ai_pipeline.py          # AI pipeline: intent + entity + response (163 строки)
    ├── test_billing_service.py      # BillingService unit
    ├── test_document_service.py     # DocumentService
    └── test_template_service.py     # TemplateService
```

**Текущее покрытие:** 103 теста, все зелёные ✅

---

## 1. Тестовая инфраструктура

### База данных

- **Dev/CI:** PostgreSQL 16 (Docker service container)
- **Локально:** SQLite in-memory (`sqlite+aiosqlite:///file:aether_test.db?mode=memory&cache=shared`)
- **Патчинг типов:** JSONB → JSON, ARRAY → JSON, BYTEA → BINARY (для SQLite совместимости)

### Фикстуры (`conftest.py`)

| Фикстура | Scope | Назначение |
|----------|-------|------------|
| `async_client` | session | httpx AsyncClient с ASGITransport (тесты без реального HTTP) |
| `db_session` | function | Изолированная транзакция (rollback после теста) |
| `test_tenant` | function | Тестовый tenant с feature flags |
| `test_user` | function | Пользователь с ролью owner в тестовом tenant'е |
| `auth_headers` | function | JWT Authorization заголовок для test_user |
| `admin_headers` | function | JWT для superadmin |
| `mock_inference_pool` | function | Мок InferencePool (возвращает предсказуемые ответы AI) |

### Тестовое окружение

```python
# Автоматически выставляется перед импортом приложения
os.environ["AETHER_ENVIRONMENT"] = "test"
os.environ["AETHER_DATABASE_URL"] = "sqlite+aiosqlite:///file:aether_test.db?mode=memory&cache=shared"
os.environ["AETHER_JWT_SECRET_KEY"] = "test-secret-key-do-not-use-in-prod-12345"
```

---

## 2. Уровни тестирования

### Unit Tests

**Что тестируем:** отдельные сервисы, утилиты, хелперы. Все зависимости — моки.

```
tests/services/
├── test_billing_service.py    # BillingService: token accounting, plan enforcement
├── test_document_service.py   # DocumentService: CRUD, пагинация
├── test_template_service.py   # TemplateService: resolve, render
└── test_security.py           # hash_password, verify_password, create_access_token
```

**Паттерн:**
```python
@pytest.mark.asyncio
async def test_charge_tokens_sufficient_balance(db_session):
    service = BillingService(db_session)
    result = await service.charge_tokens(tenant_id, user_id, tokens=500)
    assert result.success is True
    assert result.remaining_tokens > 0
```

### Integration Tests

**Что тестируем:** API endpoint'ы с реальной БД (SQLite/PostgreSQL), без моков на ORM.

```
tests/api/v1/
├── test_auth.py       # signup → login → refresh → logout → revoked token rejected
├── test_tenants.py    # CRUD + tenant isolation
├── test_billing.py    # plans, usage, subscription lifecycle
├── test_health.py     # health check (DB + Redis)
└── test_infer_billing.py  # /infer endpoint auto-charges tokens
```

**Паттерн:**
```python
@pytest.mark.asyncio
async def test_signup_login_refresh(async_client):
    # 1. Signup
    resp = await async_client.post("/api/v1/auth/signup", json={...})
    assert resp.status_code == 201
    tokens = resp.json()
    access, refresh = tokens["access_token"], tokens["refresh_token"]

    # 2. Access protected endpoint
    resp = await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200

    # 3. Refresh token
    resp = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]

    # 4. Old access token rejected
    resp = await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 401
```

### Contract Tests (Stage 3)

**Что тестируем:** OpenAPI спека соответствует реальным ответам API.

```python
# schemathesis run http://localhost:8799/openapi.json
# Проверяет все эндпоинты на соответствие схемам ответов
```

### E2E Tests (Stage 4)

**Что тестируем:** Полный путь пользователя в Docker Compose окружении.

```
tests/e2e/
├── test_tenant_onboarding.py    # Регистрация → создание канала → первый диалог
├── test_magic_link_flow.py      # Email → magic link → login → workspace
├── test_ai_response.py          # Отправка сообщения → intent → entity → response → доставка
└── test_billing_cycle.py        # Регистрация → trial → апгрейд → списание токенов → invoice
```

---

## 3. Тестовые данные

### Faker

Используется `faker` для генерации реалистичных данных:
- `fake.email()` — уникальные email
- `fake.company()` — названия компаний
- `fake.uuid4()` — уникальные ID
- `fake.text()` — содержимое сообщений

### Seed Data (демо)

```bash
make seed    # Наполняет БД демо-данными:
             # 3 плана (Free/Starter/Pro)
             # 5 тестовых tenant'ов
             # Примеры интентов и сервисов
```

---

## 4. CI интеграция

### GitHub Actions

```yaml
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_USER: aether
        POSTGRES_PASSWORD: aether_test
        POSTGRES_DB: aether_test
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: pip install -e ".[dev]"
    - run: python -m pytest tests/ -v --tb=short
```

### Pre-commit

```bash
pre-commit run --all-files
# ruff lint → ruff format → mypy
```

---

## 5. Тестовая матрица (целевое покрытие)

| Слой | Сейчас | Цель Stage 3 | Цель Stage 4 |
|------|--------|-------------|-------------|
| Unit tests | 50+ | 100+ | 200+ |
| API integration | 37+ | 80+ | 120+ |
| Service integration | 16+ | 40+ | 60+ |
| Contract (OpenAPI) | 0 | schemathesis | CI nightly |
| E2E | 0 | 5 critical paths | 20+ |
| Tenant isolation | 4+ | 10+ | 15+ |
| **Итого** | **103** | **250+** | **400+** |

---

## 6. Tenant Isolation Tests

Критичный набор тестов для мультитенантности:

```python
async def test_tenant_a_cannot_see_tenant_b_channels():
    """Tenant A не видит каналы Tenant B."""

async def test_tenant_context_propagated_to_services():
    """TenantContext из middleware доступен во всех сервисах."""

async def test_cross_tenant_access_returns_404():
    """Попытка доступа к ресурсу чужого tenant'а → 404 (не 403)."""

async def test_tenant_suspension_blocks_all_endpoints():
    """Suspended tenant получает 403 на все endpoints."""

async def test_rls_enforced_on_direct_queries():
    """Даже прямые SQL-запросы через сессию не видят чужие данные."""
```

---

## 7. Performance Tests (Stage 4)

```
tests/performance/
├── locustfile.py          # Нагрузочное тестирование через Locust
├── test_concurrent_ws.py  # 100 одновременных WebSocket соединений
└── test_ai_latency.py     # P50/P95/P99 latency для /infer
```

**Пороговые значения:**
- API response P95 < 200ms (без AI)
- AI inference P95 < 2s (локальные модели)
- WebSocket message delivery < 100ms
- 100 concurrent users без деградации

---

## 🤖 Для агентов

При написании тестов:
1. Каждый новый endpoint → минимум 2 теста (happy path + error case)
2. Каждый новый сервис → unit тесты всех публичных методов
3. Tenant isolation — всегда проверять что tenant A не видит данные tenant B
4. Использовать `db_session` фикстуру — она делает rollback после каждого теста
5. Auth тесты: полный цикл (signup → login → refresh → logout → rejected)
6. Имена тестов: `test_<subject>_<scenario>_<expected_result>()`
