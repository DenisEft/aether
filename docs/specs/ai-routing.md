# AI Smart Router — Спецификация

**Статус:** Stage 2 (частично реализован в InferencePool, SmartRouter — в разработке)
**Модуль:** `backend/app/services/ai/`

---

## 1. Multi-Driver Architecture

### Принцип

Aether использует драйверную архитектуру: каждый AI-провайдер (локальная модель, OpenAI API, DeepSeek API и т.д.) реализует `BaseDriver` (ABC). InferencePool управляет пулом драйверов, SmartRouter выбирает оптимальный драйвер для каждого запроса.

```
Request → SmartRouter → InferencePool → BaseDriver → Model
                           │
                           ├── LlamaCppDriver (GPU0: 3080 Ti, GPU1: 3090)
                           ├── OllamaDriver (CPU fallback)
                           ├── OpenAIDriver (gpt-4o-mini, gpt-4o)
                           ├── DeepSeekDriver (deepseek-v4-pro)
                           ├── AnthropicDriver (Stage 2)
                           └── VLLMDriver (Stage 2)
```

### Регистрация драйвера

```python
# При старте приложения (lifespan)
pool = InferencePool()

# Регистрация драйверов
llama = LlamaCppDriver(
    base_url="http://localhost:8085",
    default_model="Qwen3.6-35B-A3B-APEX-I-Quality",
    supported_models=["Qwen3.6-35B-A3B-APEX-I-Quality"]
)
await pool.register_driver(llama)
# → вызывает llama.initialize() → health_check() → driver status = ONLINE

openai = OpenAIDriver(
    api_key=settings.OPENAI_API_KEY,
    default_model="gpt-4o-mini",
    supported_models=["gpt-4o-mini", "gpt-4o"]
)
await pool.register_driver(openai)
```

### Статусы драйвера

| Статус | Описание | Поведение |
|--------|----------|-----------|
| `ONLINE` | Здоров, отвечает < 500ms | Принимает запросы |
| `DEGRADED` | Отвечает но latency > threshold | Пониженный приоритет |
| `RATE_LIMITED` | Исчерпан лимит запросов | Не принимать до reset |
| `OFFLINE` | Недоступен | Исключён из routing |

---

## 2. SmartRouter — Алгоритм выбора модели

### Стратегии роутинга

```python
class RoutingStrategy(str, Enum):
    COST_OPTIMAL = "cost_optimal"       # Самый дешёвый (предпочитает локальные)
    LATENCY_OPTIMAL = "latency_optimal" # Самый быстрый (предпочитает маленькие модели)
    PRIVACY_FIRST = "privacy_first"     # Только локальные драйверы
    QUALITY_FIRST = "quality_first"     # Самая качественная модель (игнорирует цену)
    HYBRID = "hybrid"                   # Weighted scoring (по умолчанию)
```

### Weighted Scoring (HYBRID)

```python
async def score_driver(driver: BaseDriver, request: InferenceRequest, strategy: RoutingStrategy) -> float:
    metrics = await driver.health_check()
    model_info = registry.get_model(request.model or driver.default_model)

    # Базовые веса
    weights = {
        "cost": 0.3,        # Чем дешевле, тем лучше
        "latency": 0.2,     # Чем быстрее, тем лучше
        "quality": 0.3,     # Чем качественнее модель, тем лучше
        "availability": 0.2 # Uptime driver'а
    }

    # Корректировка весов под стратегию
    if strategy == RoutingStrategy.COST_OPTIMAL:
        weights = {"cost": 0.5, "latency": 0.15, "quality": 0.15, "availability": 0.2}
    elif strategy == RoutingStrategy.PRIVACY_FIRST:
        # Только локальные драйверы
        if not model_info.is_local:
            return -1.0  # Исключён

    score = (
        weights["cost"] * normalize_cost(model_info.cost_per_1k_tokens) +
        weights["latency"] * normalize_latency(metrics.avg_latency_ms) +
        weights["quality"] * model_quality_score(model_info.model_id) +
        weights["availability"] * (1.0 - metrics.total_errors / max(metrics.total_requests, 1))
    )

    return score
```

### Fallback Chain

```yaml
# Конфигурация fallback (per model → fallback models)
fallback_chains:
  "Qwen3.6-35B-A3B":
    - "gpt-4o-mini"           # Если локальная упала → OpenAI
    - "deepseek-v4-pro"       # Если OpenAI недоступен → DeepSeek
  "gpt-4o":
    - "gpt-4o-mini"           # Если gpt-4o rate limited → cheaper
    - "deepseek-v4-pro"
  "deepseek-v4-pro":
    - "gpt-4o-mini"           # Если DeepSeek упал → OpenAI
    - "Qwen3.6-35B-A3B"       # → локальная
```

### Circuit Breaker

```python
class CircuitBreaker:
    """Предотвращает каскадные отказы."""

    failure_threshold: int = 5      # Ошибок подряд → OPEN
    recovery_timeout: int = 30      # Секунд ожидания до HALF_OPEN
    half_open_max: int = 2          # Запросов в HALF_OPEN

    # Состояния:
    # CLOSED → нормально
    # OPEN   → все запросы сразу fail (без реального вызова)
    # HALF_OPEN → пробные запросы, если ОК → CLOSED, если ошибка → OPEN
```

---

## 3. InferencePool — Пул драйверов

### Health Check

Периодический (каждые 30s) параллельный health check всех драйверов:

```python
async def health_check_all(self) -> dict[DriverType, DriverMetrics]:
    tasks = [driver.health_check() for driver in self._drivers.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for driver_type, result in zip(self._drivers.keys(), results):
        if isinstance(result, Exception):
            self._driver_metrics[driver_type].status = DriverStatus.OFFLINE
        else:
            self._driver_metrics[driver_type] = result
            # Обновить circuit breaker
            if result.status == DriverStatus.ONLINE:
                self._circuit_breakers[driver_type].on_success()
            else:
                self._circuit_breakers[driver_type].on_failure()
```

### Load Balancing

Для драйверов с несколькими моделями:

```python
# Least-latency: отправляем запрос тому драйверу у которого p50 latency меньше
# Для локальных моделей: учитываем загрузку GPU
```

---

## 4. BaseDriver — Интерфейс драйвера

### Полный контракт

```python
class BaseDriver(ABC):
    driver_type: DriverType
    supported_models: list[str]
    default_model: str
    status: DriverStatus = DriverStatus.OFFLINE

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse: ...

    @abstractmethod
    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[str]: ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...

    @abstractmethod
    async def health_check(self) -> DriverMetrics: ...

    @abstractmethod
    async def get_available_models(self) -> list[str]: ...

    @abstractmethod
    async def shutdown(self) -> None: ...
```

### InferenceRequest (унифицированный)

```json
{
  "messages": [
    {"role": "system", "content": "Ты — AI-ассистент компании."},
    {"role": "user", "content": "Где мой заказ?"}
  ],
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false,
  "timeout_seconds": 120,
  "priority": 0,
  "metadata": {
    "conversation_id": "...",
    "intent": "order_status",
    "channel": "telegram"
  }
}
```

### InferenceResponse (унифицированный)

```json
{
  "text": "Ваш заказ #12345 находится в пути. Ожидаемая дата доставки: 05.07.2026.",
  "model": "gpt-4o-mini",
  "tokens_prompt": 150,
  "tokens_completion": 42,
  "tokens_total": 192,
  "finish_reason": "stop",
  "latency_ms": 850,
  "driver_type": "openai",
  "cost_estimate_usd": 0.00048
}
```

---

## 5. Intent Classification

### Pipeline

```
Текст сообщения
  │
  ├── 1. Regex Fast Path (< 1ms)
  │     Паттерны: "привет", "пока", "где заказ №...", "документы по вагону..."
  │     Если match → сразу ClassificationResult (confidence 0.95+)
  │
  ├── 2. Embedding Similarity (< 50ms)
  │     Вычисляем embedding сообщения → cosine similarity с FAQ базой
  │     Если similarity > 0.85 → FAQ intent
  │
  └── 3. LLM Classification (~200-500ms)
        Полный NLU-анализ: текст + контекст диалога
        Возвращает intent + sub_intent + confidence + suggested_plugins
```

### LLM Classification Prompt

```
Ты — классификатор интентов. Определи намерение пользователя.

Контекст диалога:
{history}

Доступные интенты:
{available_intents_json}

Сообщение пользователя:
{message}

Ответь JSON:
{
  "intent": "order_status",
  "sub_intent": "tracking.location",
  "confidence": 0.92,
  "entities": {
    "order_id": "12345"
  },
  "needs_clarification": false
}
```

---

## 6. Entity Extraction

### Pipeline

```
Текст сообщения + ClassificationResult
  │
  ├── 1. Regex Extraction (< 1ms)
  │     - Номера вагонов: \d{8}
  │     - Даты: \d{2}\.\d{2}\.\d{4}
  │     - Email: RFC 5322
  │     - Телефоны: \+7\d{10}
  │     - ИНН: \d{10}|\d{12}
  │     - Номера заказов: заказ №(\d+)
  │
  ├── 2. LLM NER (~100-300ms)
  │     - Имена людей, организаций
  │     - Адреса, города
  │     - Номера контрактов, ГУ-12
  │
  └── 3. Lookup Validation (если применимо)
        Проверка существования в БД: вагон 12345678 существует?
```

---

## 7. Response Generation

### Prompt Assembly

```python
messages = [
    {
        "role": "system",
        "content": f"""Ты — {config.brand_name}, AI-ассистент в сфере логистики.
Тон: {config.tone}. Язык: {config.language}.
Контекст: работаешь с данными компании клиента, не выдумывай факты.
Если не знаешь ответ — предложи связаться с оператором.
Сегодня: {datetime.now().strftime('%d.%m.%Y')}."""
    },
    # История диалога (последние N сообщений, умещающиеся в context window)
    *history_messages,
    # Результат работы плагина (если есть)
    {"role": "system", "content": f"Данные из системы: {json.dumps(service_result)}"},
    # Текущее сообщение с извлечёнными сущностями
    {"role": "user", "content": formatted_user_message}
]
```

### Context Window Management

```python
def trim_history(messages: list[dict], max_tokens: int, model_context: int) -> list[dict]:
    """
    Обрезает историю чтобы влезть в context window модели.
    - Оставляет system prompt всегда
    - Оставляет последние N сообщений
    - Если всё равно не влезает → summarise старые сообщения
    """
    available = model_context - max_tokens - 500  # 500 токенов запас

    result = [messages[0]]  # system prompt
    remaining = available - estimate_tokens(messages[0])

    # Keep последние сообщения, обрезать старые
    for msg in reversed(messages[1:]):
        tokens = estimate_tokens(msg)
        if remaining - tokens < 0:
            break
        result.append(msg)
        remaining -= tokens

    # Если обрезали → вставить summary
    if len(result) < len(messages) - 1:
        summary = "Предыдущий контекст диалога был суммаризирован..."
        result.insert(1, {"role": "system", "content": summary})

    return result
```

---

## 8. Embedding Pipeline

### Chunking Strategy

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Разбивает документ на чанки для векторизации.
    - chunk_size: 500 токенов (~1500 символов для русского)
    - overlap: 50 токенов перекрытия для сохранения контекста
    - Split by: параграфы, затем предложения, затем фиксированный размер
    """
```

### Embedding Models (per environment)

| Среда | Модель | Размерность | Локально? |
|-------|--------|-------------|-----------|
| Dev | `intfloat/multilingual-e5-large` | 1024 | Да (Ollama) |
| Prod | `intfloat/multilingual-e5-large` | 1024 | Да (GPU) |
| Fallback | `text-embedding-3-small` | 1536 | Нет (OpenAI) |

### Qdrant Collections

```
Коллекция: tenant_{tenant_id}_{collection_name}
├── knowledge_base    — FAQ, инструкции, документация
├── faq               — частые вопросы клиентов
├── documents         — пользовательские документы
└── intents           — examples для intent matching
```

---

## 9. Tenant Routing Rules

Каждый tenant может настроить правила маршрутизации:

```json
{
  "tenant_id": "550e8400-...",
  "routing": {
    "strategy": "privacy_first",
    "rules": [
      {
        "task": "classification",
        "model": "Qwen3.6-35B-A3B-APEX-I-Quality",
        "priority": 100
      },
      {
        "task": "generation",
        "model": "gpt-4o-mini",
        "condition": "complexity > 0.7",
        "priority": 50
      },
      {
        "task": "generation",
        "model": "Qwen3.6-35B-A3B-APEX-I-Quality",
        "priority": 10
      }
    ],
    "fallback": {
      "enabled": true,
      "chain": ["gpt-4o-mini", "deepseek-v4-pro"]
    },
    "budget": {
      "monthly_limit_usd": 100,
      "alert_at_percent": 80
    }
  }
}
```

---

## 10. Billing Integration

SmartRouter передаёт стоимость каждого запроса в BillingService:

```python
# После каждого generate() вызова
billing_result = await billing_service.charge_tokens(
    tenant_id=request.tenant_id,
    user_id=request.metadata.get("user_id"),
    tokens=response.tokens_total,
    driver_type=response.driver_type,
    cost_usd=response.cost_estimate_usd,
    model=response.model
)

if not billing_result.success:
    # Если бюджет исчерпан → SmartRouter выбирает только бесплатные драйверы
    # (локальные модели) или возвращает 429
    raise QuotaExceededError(billing_result.message)
```

**Стоимость по моделям (Stage 2, конфигурируется):**

| Модель | $ / 1M input токенов | $ / 1M output токенов | Локальная? |
|--------|----------------------|------------------------|------------|
| Qwen3.6-35B-A3B | $0 | $0 | Да |
| gpt-4o-mini | $0.15 | $0.60 | Нет |
| gpt-4o | $2.50 | $10.00 | Нет |
| deepseek-v4-pro | $0.14 | $0.28 | Нет |
| claude-3-haiku | $0.25 | $1.25 | Нет |

---

## 11. Схема БД

```sql
-- AI Models
CREATE TABLE ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    driver_type VARCHAR(50) NOT NULL,
    context_length INT NOT NULL,
    cost_per_1k_tokens_input DECIMAL(10,6) DEFAULT 0,
    cost_per_1k_tokens_output DECIMAL(10,6) DEFAULT 0,
    capabilities JSONB DEFAULT '["chat"]',
    languages JSONB DEFAULT '["ru","en"]',
    is_local BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    min_vram_mb INT,
    recommended_for JSONB DEFAULT '["generation"]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI Drivers
CREATE TABLE ai_drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_type VARCHAR(50) UNIQUE NOT NULL,
    base_url VARCHAR(500),
    api_key_encrypted TEXT,
    status VARCHAR(20) DEFAULT 'offline',
    last_health_check TIMESTAMPTZ,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Intents
CREATE TABLE ai_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    category VARCHAR(50),  -- greeting, question, order_status, etc.
    examples JSONB DEFAULT '[]',
    regex_patterns JSONB DEFAULT '[]',
    suggested_plugins JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Entities
CREATE TABLE ai_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    entity_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    entity_type VARCHAR(50),  -- string, number, date, email, phone
    description TEXT,
    examples JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '[]',  -- regex patterns
    lookup_source VARCHAR(100),   -- db.users, api.orders
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, entity_name)
);

-- Prompt Templates
CREATE TABLE ai_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    template_type VARCHAR(50),  -- system_prompt, intent_classification, ner, response
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Knowledge Bases
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    document_count INT DEFAULT 0,
    total_chunks INT DEFAULT 0,
    qdrant_collection VARCHAR(255),
    embedding_model VARCHAR(100) DEFAULT 'multilingual-e5-large',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documents (для RAG)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    title VARCHAR(500),
    content TEXT,
    content_hash VARCHAR(64),
    chunk_count INT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',  -- pending, indexing, ready, error
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 12. Метрики и мониторинг

### Prometheus метрики

```
# Per driver
aether_ai_requests_total{driver="llama_cpp",model="qwen3.6-35b",status="success"} 1234
aether_ai_requests_total{driver="openai",model="gpt-4o-mini",status="error"} 5

# Latency histogram
aether_ai_latency_seconds{driver="llama_cpp",quantile="0.5"} 0.45
aether_ai_latency_seconds{driver="llama_cpp",quantile="0.95"} 1.2
aether_ai_latency_seconds{driver="llama_cpp",quantile="0.99"} 2.8

# Token usage (per tenant)
aether_ai_tokens_total{tenant_id="...",driver="openai",type="input"} 500000
aether_ai_tokens_total{tenant_id="...",driver="openai",type="output"} 120000

# Cost tracking
aether_ai_cost_usd_total{tenant_id="...",driver="openai"} 15.42

# Circuit breaker state
aether_ai_circuit_breaker_state{driver="openai"} 0  # 0=closed, 1=open, 2=half_open

# SmartRouter decisions
aether_ai_routing_decision_total{strategy="cost_optimal",driver_selected="llama_cpp"} 567
```

### Алерты

| Условие | Severity | Действие |
|---------|----------|----------|
| Circuit breaker OPEN > 5 min | CRITICAL | Telegram alert |
| P95 latency > 5s (облачные) | WARNING | Telegram + переключить трафик |
| VRAM < 10% free (локальные) | WARNING | Telegram + не загружать новые модели |
| Tenant budget > 80% | INFO | Email tenant admin |
| Tenant budget исчерпан | WARNING | Авто-переключение на local-only |
| Error rate > 10% за 5 min | CRITICAL | Telegram + проверка драйверов |

---

## 🤖 Для агентов

При изменении AI Core:
1. Любой новый драйвер → реализуй `BaseDriver` полностью (все 7 методов)
2. Добавил драйвер → обнови `ModelRegistry` и `SmartRouter.routing_weights`
3. Изменил prompt template → добавь тест с конкретным expected output
4. Новая модель → запись в `ai_models` таблицу + обнови fallback chains
5. Всегда проверяй billing integration: каждый generate() должен заряжать токены
