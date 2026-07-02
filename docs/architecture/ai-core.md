# 📁 AI Core

AI-ядро Aether — multi-driver inference, intent classification, entity extraction, response generation, embeddings.

**Принцип:** драйверный слой (как ai-ops) + tenant-aware routing + queue-based async execution.  
**Стек:** FastAPI + Redis + Celery + локальные модели (llama.cpp, Ollama) + внешние API (OpenAI) как fallback.  
**Целевое состояние:** Stage 1 — собственный router с локальными моделями. Stage 3 — гибрид (локальные GPU + внешние API + smart routing).

---

## 📊 Обзор

```
backend/app/services/ai/
├── 📁 drivers/
│   ├── base.py
│   │   ⚡ 1 класс: BaseDriver (ABC)
│   │   ⚡ 0 функций
│   ├── ollama_driver.py
│   │   ⚡ 1 класс: OllamaDriver(BaseDriver)
│   ├── llama_driver.py
│   │   ⚡ 1 класс: LlamaCppDriver(BaseDriver)
│   ├── openai_driver.py
│   │   ⚡ 1 класс: OpenAIDriver(BaseDriver)
│   ├── vllm_driver.py              # Stage 2
│   │   ⚡ 1 класс: VLLMDriver(BaseDriver)
│   ├── anthropic_driver.py         # Stage 2
│   │   ⚡ 1 класс: AnthropicDriver(BaseDriver)
│   ├── grok_driver.py              # Stage 3
│   │   ⚡ 1 класс: GrokDriver(BaseDriver)
│   └── deepseek_driver.py          # Stage 2
│       ⚡ 1 класс: DeepSeekDriver(BaseDriver)
│
├── inference_pool.py
│   ⚡ 1 класс: InferencePool
│   ⚡ 0 функций
│
├── intent_classifier.py
│   ⚡ 1 класс: IntentClassifier
│   ⚡ 0 функций
│
├── entity_extractor.py
│   ⚡ 1 класс: EntityExtractor
│   ⚡ 0 функций
│
├── response_generator.py
│   ⚡ 1 класс: ResponseGenerator
│   ⚡ 0 функций
│
├── context_manager.py
│   ⚡ 1 класс: ContextManager
│   ⚡ 0 функций
│
├── embedding_service.py
│   ⚡ 1 класс: EmbeddingService
│   ⚡ 0 функций
│
├── smart_router.py                 # Stage 2
│   ⚡ 1 класс: SmartRouter
│   ⚡ 0 функций
│
└── model_registry.py
    ⚡ 1 класс: ModelRegistry
    ⚡ 0 функций
```

---

## 1. `drivers/base.py` — BaseDriver (ABC)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator
from uuid import UUID

class DriverType(str, Enum):
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    VLLM = "vllm"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROK = "grok"
    DEEPSEEK = "deepseek"

class DriverStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"       # работает но latency > threshold
    RATE_LIMITED = "rate_limited"

@dataclass
class DriverMetrics:
    driver_type: DriverType
    status: DriverStatus
    total_requests: int
    total_tokens: int
    total_errors: int
    avg_latency_ms: float
    p99_latency_ms: float
    last_health_check: float    # unix timestamp
    gpu_utilization: float | None  # только для локальных
    vram_used_mb: int | None       # только для локальных

@dataclass
class InferenceRequest:
    """Унифицированный запрос на инференс — не зависит от драйвера."""
    messages: list[dict[str, str]]       # [{"role": "user", "content": "..."}]
    tenant_id: UUID
    model: str | None = None             # override model per request
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stop: list[str] | None = None
    stream: bool = False
    timeout_seconds: int = 120
    priority: int = 0                    # 0=normal, 1=high, -1=low (batch)
    metadata: dict = field(default_factory=dict)  # tracing, logging

@dataclass
class InferenceResponse:
    """Унифицированный ответ — не зависит от драйвера."""
    text: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    finish_reason: str              # "stop", "length", "error"
    latency_ms: float
    driver_type: DriverType
    cost_estimate_usd: float        # 0 для локальных моделей

@dataclass
class EmbeddingRequest:
    texts: list[str]
    tenant_id: UUID
    model: str | None = None

@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    dimensions: int
    latency_ms: float

class BaseDriver(ABC):
    """Абстрактный драйвер инференса. Все драйверы реализуют этот контракт."""
    
    driver_type: DriverType
    supported_models: list[str]     # модели которые драйвер умеет
    default_model: str
    status: DriverStatus = DriverStatus.OFFLINE
    
    @abstractmethod
    async def initialize(self) -> None:
        """Загрузка модели, проверка соединения, прогрев."""
        ...
    
    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Нестриминговая генерация — возвращает полный ответ."""
        ...
    
    @abstractmethod
    async def generate_stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[str]:
        """Стриминговая генерация — yield токенов через Server-Sent Events."""
        ...
    
    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Генерация эмбеддингов для векторизации."""
        ...
    
    @abstractmethod
    async def health_check(self) -> DriverMetrics:
        """Проверка здоровья — latency, статус, потребление ресурсов."""
        ...
    
    @abstractmethod
    async def get_available_models(self) -> list[str]:
        """Список моделей доступных через этот драйвер."""
        ...
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение — выгрузка модели, закрытие соединений."""
        ...
```

---

## 2. `inference_pool.py` — InferencePool

```python
class InferencePool:
    """
    Пул драйверов инференса с маршрутизацией запросов.
    
    Управляет несколькими BaseDriver и направляет запросы 
    к подходящему драйверу на основе модели, tenant config, 
    доступности и метрик.
    """
    
    def __init__(self) -> None:
        self._drivers: dict[DriverType, BaseDriver] = {}
        self._driver_metrics: dict[DriverType, DriverMetrics] = {}
        self._model_routing: dict[str, DriverType] = {}  # model → driver
        self._lock = asyncio.Lock()
    
    async def register_driver(self, driver: BaseDriver) -> None:
        """Зарегистрировать драйвер в пуле. Вызывает driver.initialize()."""
        ...
    
    async def unregister_driver(self, driver_type: DriverType) -> None:
        """Удалить драйвер из пула. Вызывает driver.shutdown()."""
        ...
    
    async def get_driver_for_model(
        self, model: str, tenant_id: UUID | None = None
    ) -> BaseDriver:
        """
        Выбрать драйвер для модели. 
        Учитывает tenant routing rules (например tenant X всегда llama).
        """
        ...
    
    async def generate(
        self, request: InferenceRequest
    ) -> InferenceResponse:
        """
        Выполнить инференс:
        1. Выбрать драйвер через get_driver_for_model()
        2. Если драйвер offline — попробовать fallback модель
        3. Выполнить generate(), замерить метрики
        4. Обновить DriverMetrics
        """
        ...
    
    async def generate_stream(
        self, request: InferenceRequest
    ) -> AsyncIterator[str]:
        """Стриминговая генерация с выбором драйвера."""
        ...
    
    async def embed(
        self, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """Эмбеддинг с выбором драйвера."""
        ...
    
    async def health_check_all(self) -> dict[DriverType, DriverMetrics]:
        """Проверка здоровья всех драйверов. Параллельно."""
        ...
    
    async def get_status(self) -> dict:
        """
        Статус пула: активные драйверы, модели, метрики, 
        количество запросов в очереди, среднее latency.
        """
        ...
    
    async def add_fallback_chain(
        self, model: str, fallback_models: list[str]
    ) -> None:
        """
        Цепочка fallback: если model недоступна → пробуем по очереди.
        Пример: "llama-70b" → ["llama-8b", "gpt-4o-mini"]
        """
        ...
    
    async def shutdown_all(self) -> None:
        """Выключить все драйверы."""
        ...
```

---

## 3. `intent_classifier.py` — IntentClassifier

```python
from enum import Enum

class IntentCategory(str, Enum):
    """Базовые категории интентов — динамически расширяются через БД."""
    GREETING = "greeting"
    QUESTION = "question"              # общий вопрос
    FAQ = "faq"                        # вопрос из базы знаний
    ORDER_STATUS = "order_status"
    DOCUMENT_REQUEST = "document_request"
    DOCUMENT_SUBMISSION = "document_submission"
    CALCULATION = "calculation"
    BOOKING = "booking"
    COMPLAINT = "complaint"
    ESCALATION = "escalation"
    OTHER = "other"
    # Tenant-specific intents загружаются из IntentTemplate модели

@dataclass
class ClassificationResult:
    intent: str                       # intent identifier
    intent_display: str               # human-readable name
    confidence: float                 # 0.0 - 1.0
    sub_intent: str | None = None     # под-интент (например "tracking.status")
    entities: dict[str, any] = field(default_factory=dict)  # извлечённые сущности
    suggested_plugins: list[str] = field(default_factory=list)  # какие плагины обрабатывают
    needs_clarification: bool = False  # нужно уточнение
    clarification_question: str | None = None

class IntentClassifier:
    """
    Классификатор интентов — NLU-пайплайн.
    
    Использует:
    1. Regex-правила для детерминированных паттернов (быстро, дёшево)
    2. Embedding similarity для FAQ-style matching
    3. LLM classification для сложных/неоднозначных запросов
    
    Stage 1: встроенный LLM-классификатор (prompt-based)
    Stage 3: fine-tuned BERT-based classifier per tenant
    """
    
    def __init__(
        self,
        inference_pool: InferencePool,
        embedding_service: EmbeddingService,
    ) -> None:
        ...
    
    async def classify(
        self,
        message_text: str,
        tenant_id: UUID,
        conversation_history: list[Message] | None = None,
    ) -> ClassificationResult:
        """
        Классифицировать сообщение:
        1. Regex fast path (если match — сразу результат)
        2. Embedding similarity (если близко к FAQ — FAQ intent)
        3. LLM classification (полный анализ текста)
        Возвращает ClassificationResult с suggested_plugins.
        """
        ...
    
    async def classify_batch(
        self,
        messages: list[str],
        tenant_id: UUID,
    ) -> list[ClassificationResult]:
        """Классификация батча сообщений — для offline аналитики."""
        ...
    
    async def get_available_intents(
        self, tenant_id: UUID
    ) -> list[dict]:
        """
        Список интентов доступных для tenant.
        Базовые (IntentCategory) + tenant-specific из IntentTemplate.
        """
        ...
    
    async def register_intent(
        self,
        tenant_id: UUID,
        intent_name: str,
        description: str,
        examples: list[str],
        plugin_ids: list[str],
    ) -> None:
        """
        Зарегистрировать новый интент для tenant.
        Сохраняется в БД (IntentTemplate).
        """
        ...
    
    async def _regex_classify(self, text: str, tenant_id: UUID) -> ClassificationResult | None:
        """Быстрый regex-based классификатор. Детерминированные паттерны."""
        ...
    
    async def _similarity_classify(self, text: str, tenant_id: UUID) -> ClassificationResult | None:
        """Embedding-based similarity search по FAQ/examples."""
        ...
    
    async def _llm_classify(
        self,
        text: str,
        tenant_id: UUID,
        history: list[Message] | None,
    ) -> ClassificationResult:
        """LLM-based классификация — полный анализ текста с контекстом."""
        ...
```

---

## 4. `entity_extractor.py` — EntityExtractor

```python
@dataclass
class Entity:
    name: str                          # "wagon_number"
    value: str                         # "12345678"
    type: str                          # "string", "number", "date", "email", "phone"
    confidence: float
    start_pos: int | None = None       # позиция в тексте
    end_pos: int | None = None

@dataclass
class EntitySchema:
    """Схема сущностей которые могут быть извлечены — per tenant."""
    entity_name: str
    display_name: str
    type: str
    description: str
    examples: list[str]
    patterns: list[str]                # regex patterns
    lookup_source: str | None = None   # "db.users", "api.orders", etc.

class EntityExtractor:
    """
    Извлекает структурированные сущности из текста.
    
    Pipeline:
    1. Regex extraction (быстрые паттерны: номера телефонов, email, ИНН, номера вагонов)
    2. NER через LLM (имена, организации, даты, адреса)
    3. Lookup validation (проверка существования в БД: вагон X существует?)
    """
    
    def __init__(self, inference_pool: InferencePool) -> None:
        ...
    
    async def extract(
        self,
        text: str,
        tenant_id: UUID,
        entity_schemas: list[EntitySchema] | None = None,
    ) -> list[Entity]:
        """
        Извлечь сущности:
        1. Regex fast path по entity_schemas.patterns
        2. LLM NER для остальных
        3. Дедупликация и консолидация (merge overlapping matches)
        """
        ...
    
    async def extract_for_intent(
        self,
        text: str,
        intent: ClassificationResult,
        tenant_id: UUID,
    ) -> list[Entity]:
        """
        Извлечь сущности релевантные конкретному интенту.
        Например для intent="document_submission" нужны: doc_type, wagon_number, date.
        """
        ...
    
    async def register_entity_schema(
        self,
        tenant_id: UUID,
        schema: EntitySchema,
    ) -> None:
        """Зарегистрировать новую схему сущностей для tenant."""
        ...
    
    async def validate_entity(
        self,
        entity: Entity,
        tenant_id: UUID,
    ) -> bool:
        """
        Валидация сущности через lookup.
        Например: wagon_number "12345678" → проверить в БД что вагон существует.
        """
        ...
```

---

## 5. `response_generator.py` — ResponseGenerator

```python
@dataclass
class GenerationConfig:
    """Per-tenant конфигурация генерации ответов."""
    system_prompt: str                 # системный промпт AI
    tone: str = "professional"        # professional, friendly, formal
    language: str = "ru"              # ru, en, auto-detect
    max_response_length: int = 2000
    include_sources: bool = False     # показывать источники (FAQ source)
    fallback_message: str = "Извините, я не могу обработать этот запрос. Оператор свяжется с вами."

class ResponseGenerator:
    """
    Генератор ответов. Собирает промпт, вызывает инференс, форматирует результат.
    
    Шаблоны ответов:
    - PromptTemplate (Jinja2): system + history + user message
    - ResponseTemplate: оборачивает ответ в формат канала (inline buttons etc)
    """
    
    def __init__(
        self,
        inference_pool: InferencePool,
    ) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._response_templates: dict[str, ResponseTemplate] = {}
    
    async def generate(
        self,
        message: NormalizedMessage,
        intent: ClassificationResult,
        entities: list[Entity],
        context: ConversationContext,
        config: GenerationConfig,
        service_result: ServiceResult | None = None,
    ) -> GeneratedResponse:
        """
        Сгенерировать ответ:
        1. Собрать prompt из шаблона (system + history + intent context + user)
        2. Если есть service_result → включить его в промпт
        3. Вызвать inference_pool.generate()
        4. Применить response template (форматирование under channel)
        """
        ...
    
    async def generate_stream(
        self, ...
    ) -> AsyncIterator[str]:
        """Стриминговая генерация."""
        ...
    
    async def assemble_prompt(
        self,
        message: NormalizedMessage,
        intent: ClassificationResult,
        entities: list[Entity],
        context: ConversationContext,
        config: GenerationConfig,
    ) -> list[dict[str, str]]:
        """
        Собрать промпт в виде messages:
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "..."},   # история
            {"role": "assistant", "content": "..."},
            ...
            {"role": "user", "content": current_message_with_entities}
        ]
        """
        ...
    
    async def apply_response_template(
        self,
        raw_response: str,
        channel_type: str,
        tenant_id: UUID,
    ) -> dict:
        """
        Применить шаблон ответа под конкретный канал.
        Например для Telegram: добавить inline_keyboard.
        """
        ...
    
    async def register_prompt_template(
        self,
        name: str,
        template: str,
    ) -> None:
        """Зарегистрировать Jinja2 prompt template."""
        ...
```

---

## 6. `context_manager.py` — ContextManager

```python
@dataclass
class ConversationContext:
    conversation_id: UUID
    tenant_id: UUID
    user_id: UUID
    channel_type: str
    messages: list[Message]             # последние N сообщений
    summary: str | None                 # сжатый контекст для длинных диалогов
    active_intent: ClassificationResult | None
    collected_entities: dict[str, Entity]
    state: dict                         # state machine state (для form filling)
    started_at: float
    last_activity_at: float
    message_count: int
    token_count_estimate: int

class ContextManager:
    """
    Управление контекстом разговора.
    
    Задачи:
    - Хранение истории сообщений (Redis для скорости, PostgreSQL для долгосрочного)
    - Context window management: обрезка истории чтобы fit in model context
    - Авто-суммаризация длинных диалогов (чтобы AI не забыл начало)
    - State machine для multi-step процессов (заполнение форм)
    - Экспирация неактивных разговоров
    """
    
    def __init__(
        self,
        inference_pool: InferencePool,
        redis: Redis,
    ) -> None:
        ...
    
    async def get_context(
        self,
        conversation_id: UUID,
        tenant_id: UUID,
        max_tokens: int = 4096,
    ) -> ConversationContext:
        """Загрузить контекст разговора из Redis/PostgreSQL."""
        ...
    
    async def append_message(
        self,
        context: ConversationContext,
        message: Message,
        role: str,
    ) -> ConversationContext:
        """
        Добавить сообщение в контекст.
        Автоматически триммит историю если превышен лимит токенов.
        """
        ...
    
    async def summarize(
        self,
        context: ConversationContext,
        keep_last_n: int = 10,
    ) -> str:
        """
        Суммаризировать историю разговора.
        Сохраняет последние N сообщений + summary предыдущего.
        """
        ...
    
    async def save_context(
        self, context: ConversationContext
    ) -> None:
        """Сохранить контекст в Redis (быстро) + PostgreSQL (durably)."""
        ...
    
    async def expire_context(
        self, conversation_id: UUID, ttl_seconds: int = 3600
    ) -> None:
        """Установить TTL для неактивного разговора."""
        ...
    
    async def update_state(
        self,
        context: ConversationContext,
        state_update: dict,
    ) -> ConversationContext:
        """
        Обновить состояние state machine.
        Используется в FormPlugin для отслеживания заполнения полей.
        """
        ...
```

---

## 7. `embedding_service.py` — EmbeddingService

```python
class EmbeddingService:
    """
    Сервис эмбеддингов: векторизация текстов + similarity search.
    
    Используется для:
    - FAQ matching: найти ближайший вопрос в базе знаний
    - Intent classification: similarity-based fast path
    - Semantic search: поиск по документам клиента
    - Memory: поиск релевантного контекста в истории
    
    Хранилище: Qdrant (self-hosted) с коллекциями per tenant.
    """
    
    def __init__(
        self,
        inference_pool: InferencePool,
        qdrant_client: QdrantClient,
    ) -> None:
        ...
    
    async def embed_texts(
        self,
        texts: list[str],
        tenant_id: UUID,
    ) -> list[list[float]]:
        """Векторизовать тексты через InferencePool.embed()."""
        ...
    
    async def index_documents(
        self,
        documents: list[dict],          # [{"id": ..., "text": ..., "metadata": ...}]
        collection_name: str,
        tenant_id: UUID,
    ) -> None:
        """
        Проиндексировать документы в Qdrant.
        Создаёт коллекцию с tenant-scoped именем.
        """
        ...
    
    async def search(
        self,
        query: str,
        collection_name: str,
        tenant_id: UUID,
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> list[SearchResult]:
        """Semantic search по коллекции."""
        ...
    
    async def delete_collection(
        self,
        collection_name: str,
        tenant_id: UUID,
    ) -> None:
        """Удалить коллекцию (при удалении tenant)."""
        ...
    
    async def get_collection_stats(
        self,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """Статистика: количество векторов, размер коллекций."""
        ...
```

---

## 8. `smart_router.py` — SmartRouter (Stage 2)

```python
class RoutingStrategy(str, Enum):
    COST_OPTIMAL = "cost_optimal"        # самый дешёвый
    LATENCY_OPTIMAL = "latency_optimal"  # самый быстрый
    PRIVACY_FIRST = "privacy_first"      # только локальные модели
    QUALITY_FIRST = "quality_first"      # самая качественная модель
    HYBRID = "hybrid"                    # комбинированный (balance)

class SmartRouter:
    """
    Интеллектуальный роутер запросов к моделям.
    
    Stage 2+ функциональность. Выбирает оптимальный драйвер/модель
    на основе стратегии routing + метрик + tenant config + бюджет.
    """
    
    def __init__(self, inference_pool: InferencePool) -> None:
        ...
    
    async def route(
        self,
        request: InferenceRequest,
        strategy: RoutingStrategy = RoutingStrategy.HYBRID,
        tenant_budget_usd: float | None = None,
    ) -> tuple[BaseDriver, str]:
        """
        Выбрать драйвер и модель:
        - Cost optimal: отсортировать драйверы по cost per token
        - Latency optimal: по p50 latency
        - Privacy first: только локальные драйверы
        - Hybrid: weighted scoring
        """
        ...
    
    async def get_routing_metrics(self) -> dict[DriverType, dict]:
        """Метрики для routing decisions: cost, latency, availability."""
        ...
```

---

## 9. `model_registry.py` — ModelRegistry

```python
@dataclass
class ModelInfo:
    model_id: str
    display_name: str
    driver_type: DriverType
    context_length: int
    cost_per_1k_tokens: float          # 0 для локальных моделей
    capabilities: set[str]             # "chat", "embed", "vision", "code"
    languages: list[str]
    is_local: bool
    is_active: bool
    min_vram_mb: int | None
    recommended_for: list[str]         # ["classification", "generation", "embedding"]

class ModelRegistry:
    """
    Реестр всех доступных моделей — локальных и внешних.
    
    Per-tenant overrides: tenant может настроить свои модели
    (например "всегда использовать llama-70b для классификации").
    """
    
    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {}
        self._tenant_overrides: dict[UUID, dict] = {}
    
    async def register_model(self, model: ModelInfo) -> None:
        """Зарегистрировать модель."""
        ...
    
    async def get_available_models(
        self, tenant_id: UUID | None = None
    ) -> list[ModelInfo]:
        """Список доступных моделей с учётом tenant overrides."""
        ...
    
    async def get_model_for_task(
        self,
        task: str,                     # "classification", "generation", "embedding"
        tenant_id: UUID,
    ) -> ModelInfo:
        """Выбрать модель под задачу с учётом tenant preferences."""
        ...
    
    async def set_tenant_override(
        self,
        tenant_id: UUID,
        task: str,
        model_id: str,
    ) -> None:
        """Настроить tenant-specific привязку модели к задаче."""
        ...
```

---

## 10. `backend/app/tasks/inference.py` — Celery Tasks

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
async def process_intent_task(
    self,
    message_text: str,
    tenant_id: str,
    conversation_id: str,
) -> dict:
    """
    Async задача: полный AI pipeline обработки сообщения.
    
    1. ContextManager.get_context()
    2. IntentClassifier.classify()
    3. EntityExtractor.extract_for_intent()
    4. IntentRouter.route_to_plugin() → plugin.handle_intent()
    5. ResponseGenerator.generate()
    6. ChannelRouter.send_message()
    """
    ...

@celery_app.task(bind=True, max_retries=2)
async def generate_embedding_batch(
    self,
    texts: list[str],
    tenant_id: str,
    collection: str,
) -> None:
    """Async задача: индексация батча текстов в Qdrant."""
    ...

@celery_app.task(bind=True)
async def health_check_drivers(self) -> dict:
    """Периодическая проверка здоровья всех драйверов."""
    ...
```

---

## 📊 Статистика модуля

| Компонент | Файл | Классов | Методов |
|-----------|------|---------|---------|
| BaseDriver | `drivers/base.py` | 1 (ABC) | 6 abstract |
| OllamaDriver | `drivers/ollama_driver.py` | 1 | 6 |
| LlamaCppDriver | `drivers/llama_driver.py` | 1 | 6 |
| OpenAIDriver | `drivers/openai_driver.py` | 1 | 6 |
| InferencePool | `inference_pool.py` | 1 | 10 |
| IntentClassifier | `intent_classifier.py` | 1 | 6 (+3 private) |
| EntityExtractor | `entity_extractor.py` | 1 | 5 |
| ResponseGenerator | `response_generator.py` | 1 | 5 (+1 private) |
| ContextManager | `context_manager.py` | 1 | 6 |
| EmbeddingService | `embedding_service.py` | 1 | 6 |
| SmartRouter | `smart_router.py` | 1 | 3 |
| ModelRegistry | `model_registry.py` | 1 | 5 |
| **Итого** | **12 файлов** | **12 классов** | **~76 методов** |

---

## 🔗 Зависимости

```
AI Core зависит от:
├── core/config.py          — настройки моделей, endpoints
├── core/tenant_context.py  — tenant_id для изоляции
├── core/exceptions.py      — AetherInferenceError, DriverUnavailableError
├── models/conversation.py  — Message, Conversation модели
├── models/intent.py        — IntentTemplate, EntityType модели
└── services/plugins/base.py — ServiceResult для генерации ответа

AI Core используется:
├── api/v1/conversations.py — REST API разговоров
├── api/v1/webhooks.py      — webhook обработка
├── services/ai_router_service.py — оркестрация AI pipeline
└── tasks/inference.py      — Celery async tasks
```
