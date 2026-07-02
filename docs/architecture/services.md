# 📁 Services — Plugin System & Service Layer

Плагинная архитектура бизнес-логики Aether. У каждого клиента разная бизнес-логика — она живёт в плагинах, не в core.

**Принцип:** Plugin Architecture. Бизнес-логика = подключаемые модули через общий контракт `BaseServicePlugin`.

---

## 📊 Обзор

```
backend/app/services/plugins/
├── base.py
│   ⚡ 1 класс: BaseServicePlugin (ABC)
│   ⚡ 5 dataclass: Capability, Intent, ServiceResult, Action, PluginHealth
│
├── registry.py
│   ⚡ 1 класс: PluginRegistry
│
├── loader.py
│   ⚡ 1 класс: PluginLoader
│
├── prompt_driver.py
│   ⚡ 1 класс: PromptDrivenPlugin(BaseServicePlugin)
│   ⚡ 1 dataclass: ToolDefinition, ExampleConversation
│
├── 📁 builtin/
│   ├── echo.py
│   │   ⚡ 1 класс: EchoPlugin
│   ├── faq.py
│   │   ⚡ 1 класс: FaqPlugin
│   ├── scheduler.py
│   │   ⚡ 1 класс: SchedulerPlugin
│   ├── form.py
│   │   ⚡ 1 класс: FormPlugin
│   ├── classifier.py
│   │   ⚡ 1 класс: ClassifierPlugin
│   ├── escalation.py
│   │   ⚡ 1 класс: EscalationPlugin
│   └── knowledge_base.py
│       ⚡ 1 класс: KnowledgeBasePlugin
│
├── 📁 logistics/
│   ├── gu12.py
│   │   ⚡ 1 класс: GU12Plugin(BaseServicePlugin)
│   ├── etran.py
│   │   ⚡ 1 класс: ETRANPlugin(BaseServicePlugin)
│   ├── calculator.py
│   │   ⚡ 1 класс: CalculatorPlugin(BaseServicePlugin)
│   ├── tracking.py
│   │   ⚡ 1 класс: TrackingPlugin(BaseServicePlugin)
│   └── documents.py
│       ⚡ 1 класс: DocumentsPlugin(BaseServicePlugin)
│
backend/app/services/
├── intent_router.py
│   ⚡ 1 класс: IntentRouter
│
├── action_executor.py
│   ⚡ 1 класс: ActionExecutor
│
└── service_registry.py
    ⚡ 1 класс: ServiceRegistry (бизнес-логика управления плагинами)
```

---

## 1. `plugins/base.py` — BaseServicePlugin (ABC)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID
from enum import Enum

@dataclass
class Capability:
    """Что плагин умеет делать."""
    name: str                          # "document_generation", "calculation"
    display_name: str
    description: str
    input_schema: dict                 # JSON Schema — что плагин принимает
    output_schema: dict                # JSON Schema — что возвращает
    examples: list[dict] = field(default_factory=list)

@dataclass
class Intent:
    """Интент — что хочет пользователь."""
    intent_type: str                   # "document_submission", "price_calculation"
    entities: dict[str, any]           # извлечённые сущности
    confidence: float                  # 0.0 - 1.0
    raw_message: str                   # исходный текст
    language: str = "ru"

@dataclass
class ConversationContext:
    """Контекст разговора — что было до этого."""
    conversation_id: UUID
    tenant_id: UUID
    user_id: UUID | None
    channel_type: str
    messages: list[dict]               # последние N сообщений [{"role":"user","content":"..."}]
    external_user_id: str | None       # Telegram user_id, email
    metadata: dict = field(default_factory=dict)

class ActionType(str, Enum):
    SEND_MESSAGE = "send_message"
    CALL_API = "call_api"
    WAIT_FOR_INPUT = "wait_for_input"
    TRANSFER_TO_HUMAN = "transfer_to_human"
    SCHEDULE_TASK = "schedule_task"
    UPDATE_STATE = "update_state"

@dataclass
class Action:
    """Действие которое плагин просит выполнить."""
    action_type: ActionType
    payload: dict
    # Примеры payload:
    # SEND_MESSAGE: {"text": "...", "buttons": [...], "attachments": [...]}
    # CALL_API: {"url": "https://...", "method": "POST", "body": {...}, "headers": {...}}
    # WAIT_FOR_INPUT: {"prompt": "Укажите номер вагона", "entity": "wagon_number", "timeout_sec": 300}
    # TRANSFER_TO_HUMAN: {"reason": "low_confidence", "department": "support"}
    # SCHEDULE_TASK: {"task_name": "check_status", "execute_at": "ISO8601", "payload": {...}}

@dataclass
class ServiceResult:
    """Результат выполнения плагина."""
    success: bool
    response_text: str | None          # текст для пользователя (может быть None если только action)
    structured_data: dict | None       # структурированные данные (например рассчитанная цена)
    actions: list[Action]              # действия которые нужно выполнить
    continue_conversation: bool = True # продолжить диалог или закрыть
    confidence: float = 1.0            # уверенность плагина в ответе (для эскалации)

@dataclass
class PluginHealth:
    status: str                        # "healthy", "degraded", "unhealthy"
    last_error: str | None
    total_executions: int
    success_rate: float
    avg_duration_ms: float

@dataclass
class ToolDefinition:
    """API endpoint который PromptDrivenPlugin может вызывать."""
    name: str                          # "check_wagon_status"
    description: str                   # "Проверяет статус вагона по номеру"
    endpoint: str                      # "https://api.logistics.ru/v1/wagons/{wagon_number}"
    method: str                        # "GET", "POST"
    input_schema: dict                 # JSON Schema
    auth_type: str                     # "none", "api_key", "bearer", "basic"

@dataclass
class ExampleConversation:
    """Пример диалога для few-shot обучения плагина."""
    user_message: str
    assistant_response: str
    intent: str | None
    entities: dict | None

class BaseServicePlugin(ABC):
    """Абстрактный контракт для всех сервисных плагинов.
    
    Каждый плагин реализует этот интерфейс.
    PluginRegistry загружает плагины динамически — 
    новый плагин = новый файл + запись в БД, без изменения core.
    """
    
    plugin_id: str                     # "gu12", "faq", "scheduler"
    display_name: str
    description: str
    version: str
    
    @abstractmethod
    async def get_capabilities(self) -> list[Capability]:
        """Возвращает список того что плагин умеет.
        Используется IntentRouter для выбора плагина под интент."""
        ...
    
    @abstractmethod
    async def handle_intent(
        self,
        intent: Intent,
        context: ConversationContext,
    ) -> ServiceResult:
        """Обработать интент — главный метод плагина.
        
        Args:
            intent: что хочет пользователь
            context: контекст разговора, tenant, история
        
        Returns:
            ServiceResult с ответом и/или действиями
        """
        ...
    
    @abstractmethod
    async def validate_config(self, config: dict) -> bool:
        """Валидировать per-tenant конфигурацию плагина.
        Вызывается при установке/обновлении плагина tenant'ом."""
        ...
    
    @abstractmethod
    async def on_install(self, tenant_id: UUID) -> None:
        """Вызывается когда tenant устанавливает плагин.
        Создаёт ресурсы, БД-записи, подготавливает окружение."""
        ...
    
    @abstractmethod
    async def on_uninstall(self, tenant_id: UUID) -> None:
        """Вызывается когда tenant удаляет плагин.
        Очищает ресурсы, удаляет БД-записи."""
        ...
    
    @abstractmethod
    async def health_check(self) -> PluginHealth:
        """Проверка здоровья плагина — работает ли, метрики."""
        ...
```

---

## 2. `plugins/registry.py` — PluginRegistry

```python
class PluginRegistry:
    """Динамический реестр всех плагинов.
    
    Плагины регистрируются при старте приложения (builtin)
    и динамически при установке tenant-specific плагинов.
    """
    
    def __init__(self) -> None:
        self._plugins: dict[str, BaseServicePlugin] = {}         # plugin_id → plugin
        self._capability_index: dict[str, set[str]] = {}         # capability → set[plugin_id]
        self._tenant_plugins: dict[UUID, set[str]] = {}          # tenant_id → set[plugin_id]
        self._lock = asyncio.Lock()
    
    async def register(self, plugin: BaseServicePlugin) -> None:
        """Зарегистрировать плагин в реестре.
        Индексирует capabilities для быстрого поиска."""
        ...
    
    async def unregister(self, plugin_id: str) -> None:
        """Удалить плагин из реестра."""
        ...
    
    async def get_plugin(self, plugin_id: str) -> BaseServicePlugin:
        """Получить плагин по ID. Бросает PluginNotFoundError."""
        ...
    
    async def list_plugins(self, tenant_id: UUID | None = None) -> list[BaseServicePlugin]:
        """Список плагинов — все или для конкретного tenant."""
        ...
    
    async def get_plugins_by_capability(self, capability: str) -> list[BaseServicePlugin]:
        """Найти плагины по capability. O(1) по индексу."""
        ...
    
    async def install_for_tenant(self, tenant_id: UUID, plugin_id: str, config: dict = None) -> None:
        """Установить плагин для tenant.
        1. Проверить что плагин существует
        2. Вызвать plugin.validate_config()
        3. Создать ServiceInstance в БД
        4. Вызвать plugin.on_install()
        5. Добавить tenant в _tenant_plugins"""
        ...
    
    async def uninstall_for_tenant(self, tenant_id: UUID, plugin_id: str) -> None:
        """Удалить плагин у tenant.
        1. Вызвать plugin.on_uninstall()
        2. Удалить ServiceInstance из БД
        3. Убрать tenant из _tenant_plugins"""
        ...
    
    async def get_tenant_plugins(self, tenant_id: UUID) -> list[BaseServicePlugin]:
        """Плагины установленные у конкретного tenant."""
        ...
    
    async def discover_plugins(self) -> list[str]:
        """Сканирует builtin/ и tenant-specific директории.
        Возвращает список найденных plugin_id."""
        ...
    
    async def reload_plugin(self, plugin_id: str) -> None:
        """Hot-reload плагина (для разработки)."""
        ...
```

---

## 3. `plugins/loader.py` — PluginLoader

```python
class PluginLoader:
    """Загрузчик плагинов — импорт, валидация, sandboxing."""
    
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry
    
    async def load_builtin_plugins(self) -> list[BaseServicePlugin]:
        """Загрузить все builtin плагины из builtin/ директории.
        Сканирует *.py файлы, импортирует, проверяет BaseServicePlugin,
        регистрирует в registry."""
        ...
    
    async def load_plugin_from_path(self, path: str) -> BaseServicePlugin:
        """Загрузить плагин из произвольного пути.
        Использует importlib для динамического импорта.
        Валидирует что класс наследует BaseServicePlugin."""
        ...
    
    async def validate_plugin(self, plugin: BaseServicePlugin) -> bool:
        """Проверить плагин:
        1. Все abstract методы реализованы
        2. plugin_id уникален
        3. capabilities валидны (JSON Schema)
        4. Нет запрещённых импортов (os, subprocess, sys)
        """
        ...
    
    async def sandbox_check(self, plugin_module) -> list[str]:
        """Проверить модуль на запрещённые импорты.
        Возвращает список нарушений.
        Запрещено: os, subprocess, sys, shutil, socket (raw), ctypes."""
        ...
```

---

## 4. `plugins/prompt_driver.py` — PromptDrivenPlugin

```python
class PromptDrivenPlugin(BaseServicePlugin):
    """
    Плагин где бизнес-логика описана в промпте AI.
    
    Tenant настраивает:
    - system_prompt: что AI должен делать
    - tools: какие API endpoints может вызывать
    - response_template: как форматировать ответ
    - examples: few-shot примеры
    
    AI сам принимает решения на основе промпта.
    Не требует кода — Stage 1 MVP для non-technical клиентов.
    """
    
    plugin_id: str = "prompt_driven"
    display_name: str = "Prompt-Driven Service"
    description: str = "Configurable AI service driven by prompts and tools"
    version: str = "1.0.0"
    
    def __init__(
        self,
        system_prompt: str,
        tools: list[ToolDefinition],
        response_template: str = "{{ response }}",
        examples: list[ExampleConversation] = None,
        inference_pool: InferencePool = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.tools = tools
        self.response_template = response_template
        self.examples = examples or []
        self._inference_pool = inference_pool
    
    async def get_capabilities(self) -> list[Capability]:
        """Генерирует capabilities из описаний tools."""
        ...
    
    async def handle_intent(
        self, intent: Intent, context: ConversationContext
    ) -> ServiceResult:
        """
        Обрабатывает интент через AI с промптом:
        1. Собирает промпт: system_prompt + examples + history + user message
        2. Вызывает inference_pool.generate()
        3. Парсит ответ AI на предмет tool_calls
        4. Если AI хочет вызвать tool → выполняет HTTP запрос
        5. Результат tool добавляет в контекст и переспрашивает AI
        6. Форматирует финальный ответ через response_template (Jinja2)
        """
        ...
    
    async def _execute_tool(self, tool_name: str, params: dict, tenant_id: UUID) -> dict:
        """Выполнить tool call — HTTP запрос к API endpoint."""
        ...
    
    async def _assemble_prompt(
        self, intent: Intent, context: ConversationContext
    ) -> list[dict]:
        """Собрать полный промпт: system + tools + examples + history + user."""
        ...
    
    async def validate_config(self, config: dict) -> bool:
        """Валидирует что system_prompt, tools, response_template корректны."""
        ...
    
    async def on_install(self, tenant_id: UUID) -> None:
        """Сохраняет конфигурацию в ServiceInstance.config."""
        ...
    
    async def on_uninstall(self, tenant_id: UUID) -> None:
        """Очищает конфигурацию."""
        ...
    
    async def health_check(self) -> PluginHealth:
        """Проверяет что inference_pool доступен."""
        ...
```

---

## 5. Builtin плагины

### `echo.py` — EchoPlugin
```python
class EchoPlugin(BaseServicePlugin):
    """Тестовый плагин — повторяет сообщение пользователя.
    Используется для проверки pipeline: Channel → AI Core → Plugin → Channel."""
    
    plugin_id = "echo"
    display_name = "Echo"
    description = "Test plugin — echoes user message back"
    version = "1.0.0"
    
    async def get_capabilities(self) -> list[Capability]:
        return [Capability(name="echo", display_name="Echo", ...)]
    
    async def handle_intent(self, intent, context) -> ServiceResult:
        return ServiceResult(
            success=True,
            response_text=f"Echo: {intent.raw_message}",
            actions=[Action(action_type=ActionType.SEND_MESSAGE, payload={"text": intent.raw_message})],
        )
    
    # validate_config, on_install, on_uninstall, health_check
```

### `faq.py` — FaqPlugin
```python
class FaqPlugin(BaseServicePlugin):
    """FAQ плагин — поиск по базе знаний + генерация ответа.
    
    Использует EmbeddingService для поиска релевантных статей
    и ResponseGenerator для формулирования ответа."""
    
    plugin_id = "faq"
    display_name = "Knowledge Base Q&A"
    version = "1.0.0"
    
    # get_capabilities: capability "faq_search"
    # handle_intent:
    #   1. Поиск по embedding similarity
    #   2. Если article found с высоким score → вернуть текст
    #   3. Если confidence низкая → передать LLM для генерации ответа
    #   4. Если неизвестно → предложить escalation
```

### `scheduler.py` — SchedulerPlugin
```python
class SchedulerPlugin(BaseServicePlugin):
    """Плагин записи на встречу.
    
    Проверяет доступные слоты, бронирует, отправляет подтверждение.
    Stage 1: простые слоты (фиксированное расписание).
    Stage 3: интеграция с Google Calendar / CalDAV."""
    
    plugin_id = "scheduler"
    display_name = "Appointment Booking"
    version = "1.0.0"
    
    # get_capabilities: capability "booking"
    # handle_intent:
    #   1. Извлечь дату/время из entities
    #   2. Проверить доступность слота
    #   3. Забронировать
    #   4. Вернуть подтверждение
```

### `form.py` — FormPlugin
```python
class FormPlugin(BaseServicePlugin):
    """Плагин структурированного сбора данных.
    
    Step-by-step форма: задаёт вопросы, валидирует ответы,
    собирает данные в структурированный dict.
    State хранится в ConversationContext.state."""
    
    plugin_id = "form"
    display_name = "Structured Data Collection"
    version = "1.0.0"
    
    # get_capabilities: capability "form_filling"
    # handle_intent: state-machine based form filling
```

### `classifier.py` — ClassifierPlugin
```python
class ClassifierPlugin(BaseServicePlugin):
    """Плагин классификации + routing.
    
    Принимает неклассифицированный запрос,
    определяет intent и перенаправляет другим плагинам.
    Используется как fallback когда IntentClassifier не уверен."""
    
    plugin_id = "classifier"
    display_name = "Intent Classifier & Router"
    version = "1.0.0"
    
    # get_capabilities: capability "classification"
    # handle_intent: classify → route to another plugin
```

### `escalation.py` — EscalationPlugin
```python
class EscalationPlugin(BaseServicePlugin):
    """Плагин эскалации на человека.
    
    Когда AI не может обработать запрос (низкая уверенность,
    пользователь просит оператора, критические запросы) —
    создаёт тикет и уведомляет ответственного."""
    
    plugin_id = "escalation"
    display_name = "Human Escalation"
    version = "1.0.0"
    
    # handle_intent: создаёт escalation ticket, уведомляет через канал
```

### `knowledge_base.py` — KnowledgeBasePlugin
```python
class KnowledgeBasePlugin(BaseServicePlugin):
    """Плагин управления базой знаний.
    
    Tenant может добавлять/редактировать статьи через чат.
    Интеграция с EmbeddingService для индексации."""
    
    plugin_id = "knowledge_base"
    display_name = "Knowledge Base Manager"
    version = "1.0.0"
    
    # handle_intent: CRUD статей через чат-команды
```

---

## 6. Логистический service-pack (Stage 1)

### `logistics/gu12.py` — GU12Plugin
```python
class GU12Plugin(BaseServicePlugin):
    """Формирование ГУ-12 (железнодорожная накладная).
    
    Извлекает данные из запроса пользователя:
    - Номер вагона, грузоотправитель, грузополучатель
    - Станция отправления/назначения
    - Груз, вес
    
    Заполняет форму ГУ-12, генерирует PDF.
    Stage 1: через PromptDrivenPlugin с настроенным промптом.
    Stage 3: прямая интеграция с ЭТРАН API."""
    
    plugin_id = "gu12"
    display_name = "ГУ-12 Формирование"
    version = "1.0.0"
    
    # get_capabilities: document_generation (ГУ-12)
    # handle_intent:
    #   1. Извлечь сущности (wagon_number, cargo, stations, weight)
    #   2. Если не хватает данных → запросить уточнение (WAIT_FOR_INPUT)
    #   3. Валидировать данные (wagon exists? station valid?)
    #   4. Заполнить форму ГУ-12
    #   5. Сгенерировать PDF
    #   6. Вернуть файл + сводку
    # validate_config: проверяет ЭТРАН credentials
    # on_install: создаёт таблицы/коллекции для ГУ-12 данных
```

### `logistics/etran.py` — ETRANPlugin
```python
class ETRANPlugin(BaseServicePlugin):
    """Интеграция с ЭТРАН (система РЖД).
    
    Stage 1: prompt-driven с API вызовами.
    Stage 3: полная интеграция."""
    
    plugin_id = "etran"
    display_name = "ЭТРАН Интеграция"
    version = "1.0.0"
    
    # get_capabilities: railway_booking, document_submission
    # handle_intent:
    #   1. Классифицировать тип запроса (booking, document, status)
    #   2. Собрать необходимые данные через form
    #   3. Вызвать ЭТРАН API
    #   4. Обработать ответ (успех/ошибка)
    #   5. Сгенерировать ответ пользователю
```

### `logistics/calculator.py` — CalculatorPlugin
```python
class CalculatorPlugin(BaseServicePlugin):
    """Расчёт ж/д тарифа.
    
    Stage 1: prompt-driven с API калькулятора.
    Stage 3: собственная модель расчёта (тарифные схемы, Прейскурант 10-01)."""
    
    plugin_id = "calculator"
    display_name = "Расчёт ж/д тарифа"
    version = "1.0.0"
    
    # get_capabilities: calculation
    # handle_intent:
    #   1. Извлечь параметры: станции, груз, вес, тип вагона
    #   2. Вызвать калькулятор (API или локальный расчёт)
    #   3. Вернуть рассчитанную стоимость
```

### `logistics/tracking.py` — TrackingPlugin
```python
class TrackingPlugin(BaseServicePlugin):
    """Отслеживание вагонов/контейнеров.
    
    Принимает номер вагона, возвращает текущий статус,
    местоположение, историю операций."""
    
    plugin_id = "tracking"
    display_name = "Отслеживание грузов"
    version = "1.0.0"
    
    # get_capabilities: tracking
    # handle_intent: поиск по номеру вагона → текущий статус
```

### `logistics/documents.py` — DocumentsPlugin
```python
class DocumentsPlugin(BaseServicePlugin):
    """Генерация транспортных документов.
    
    CMR (международная ТТН), ТТН, счёт-фактура, договор перевозки.
    Шаблоны документов в формате DOCX/HTML, заполняются из entities."""
    
    plugin_id = "documents"
    display_name = "Генерация документов"
    version = "1.0.0"
    
    # get_capabilities: document_generation (CMR, ТТН, invoice)
    # handle_intent:
    #   1. Определить тип документа
    #   2. Собрать данные через form
    #   3. Заполнить шаблон (Jinja2 + WeasyPrint для PDF)
    #   4. Вернуть документ
```

---

## 7. `intent_router.py` — IntentRouter

```python
class IntentRouter:
    """
    Маршрутизатор интентов к плагинам.
    
    Принимает ClassificationResult от IntentClassifier,
    находит подходящий плагин через PluginRegistry,
    возвращает ServiceResult.
    """
    
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry
    
    async def route(
        self,
        intent: ClassificationResult,
        context: ConversationContext,
    ) -> ServiceResult:
        """
        Найти плагин и выполнить интент:
        1. Если intent.suggested_plugins не пуст → использовать их
        2. Иначе найти плагины по intent_type через registry.get_plugins_by_capability()
        3. Если найден один плагин → выполнить
        4. Если несколько → приоритет по ServiceBinding.priority
        5. Если ни одного → PromptDrivenPlugin как fallback
        6. Если confidence < threshold → EscalationPlugin
        """
        ...
    
    async def route_pipeline(
        self,
        intent: ClassificationResult,
        context: ConversationContext,
        pipeline: list[str],  # последовательность plugin_id
    ) -> ServiceResult:
        """
        Выполнить цепочку плагинов.
        Результат первого передаётся как entities второму.
        """
        ...
```

---

## 8. `action_executor.py` — ActionExecutor

```python
class ActionExecutor:
    """
    Выполняет действия возвращённые плагином.
    
    ServiceResult.actions → исполнение каждого Action.
    """
    
    def __init__(
        self,
        channel_router: ChannelRouter,
        inference_pool: InferencePool,
    ) -> None:
        ...
    
    async def execute(
        self,
        actions: list[Action],
        context: ConversationContext,
    ) -> list[dict]:
        """
        Выполнить список действий последовательно.
        Для каждого Action:
        
        - SEND_MESSAGE: отправить через ChannelRouter
        - CALL_API: HTTP запрос с таймаутом и ретраями
        - WAIT_FOR_INPUT: обновить state в ContextManager
        - TRANSFER_TO_HUMAN: создать тикет + уведомить
        - SCHEDULE_TASK: создать Celery задачу
        - UPDATE_STATE: обновить ConversationContext.state
        
        Возвращает результаты каждого action.
        """
        ...
    
    async def _send_message(self, payload: dict, context: ConversationContext) -> dict:
        """Отправить сообщение через канал."""
        ...
    
    async def _call_api(self, payload: dict, context: ConversationContext) -> dict:
        """Выполнить HTTP запрос к внешнему API."""
        ...
    
    async def _wait_for_input(self, payload: dict, context: ConversationContext) -> dict:
        """Установить ожидание ввода от пользователя."""
        ...
    
    async def _transfer_to_human(self, payload: dict, context: ConversationContext) -> dict:
        """Эскалировать на человека-оператора."""
        ...
```

---

## 9. `service_registry.py` — ServiceRegistry (business logic)

```python
class ServiceRegistry:
    """
    Бизнес-логика управления плагинами.
    
    Работает с БД (ServiceDefinition, ServiceInstance, ServiceBinding),
    вызывает PluginRegistry для runtime операций.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        plugin_registry: PluginRegistry,
    ) -> None:
        ...
    
    async def get_service_catalog(
        self, tenant_id: UUID
    ) -> list[dict]:
        """Каталог доступных плагинов.
        Builtin + tenant-specific + (Stage 3) marketplace."""
        ...
    
    async def install_service(
        self, tenant_id: UUID, service_definition_id: UUID, config: dict
    ) -> ServiceInstance:
        """Установить плагин для tenant."""
        ...
    
    async def uninstall_service(
        self, tenant_id: UUID, service_instance_id: UUID
    ) -> None:
        """Удалить плагин у tenant."""
        ...
    
    async def update_service_config(
        self, tenant_id: UUID, service_instance_id: UUID, config: dict
    ) -> ServiceInstance:
        """Обновить конфигурацию плагина."""
        ...
    
    async def test_service(
        self, tenant_id: UUID, service_instance_id: UUID, test_message: str
    ) -> ServiceResult:
        """Тестовый вызов плагина с сообщением."""
        ...
    
    async def get_service_metrics(
        self, tenant_id: UUID, service_instance_id: UUID, period: str
    ) -> dict:
        """Метрики использования плагина."""
        ...
    
    async def bind_service_to_channel(
        self, tenant_id: UUID, service_instance_id: UUID, channel_id: UUID
    ) -> ServiceBinding:
        """Привязать плагин к каналу."""
        ...
```

---

## 📊 Статистика

| Компонент | Файл | Классов | Методов |
|-----------|------|---------|---------|
| BaseServicePlugin | base.py | 1 (ABC) + 7 dataclass | 6 abstract |
| PluginRegistry | registry.py | 1 | 10 |
| PluginLoader | loader.py | 1 | 4 |
| PromptDrivenPlugin | prompt_driver.py | 1 | 6 + 2 dataclass |
| Builtin plugins | 7 файлов | 7 | ~35 |
| Logistics plugins | 5 файлов | 5 | ~25 |
| IntentRouter | intent_router.py | 1 | 3 |
| ActionExecutor | action_executor.py | 1 | 7 |
| ServiceRegistry | service_registry.py | 1 | 7 |
| **Итого** | **~19 файлов** | **~18 классов** | **~103 методов** |

---

## 🔗 Зависимости

```
Services зависит от:
├── core/tenant_context.py      — tenant_id для изоляции
├── core/exceptions.py          — PluginNotFoundError, PluginExecutionError
├── models/service.py           — ServiceDefinition, ServiceInstance, ServiceBinding, ServiceExecution
├── services/ai/intent_classifier.py — ClassificationResult
├── services/ai/inference_pool.py    — для PromptDrivenPlugin
└── services/channels/base.py   — для ActionExecutor.send_message()

Services используется:
├── api/v1/services.py          — REST API управления плагинами
├── services/ai_router_service.py — полный pipeline
└── services/intent_router.py   — маршрутизация интентов
```
