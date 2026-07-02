# Plugin SDK Specification for Aether SaaS Platform

## Overview

This specification defines the Plugin Software Development Kit (SDK) for Aether SaaS platform, which implements a plugin architecture where business logic lives in plugins, not in the core system.

## Plugin Architecture Principles

1. **Plugin Architecture**: Business logic is implemented as plug-ins, not in the core
2. **Dynamic Discovery**: Plugins are discovered and loaded dynamically at runtime
3. **Tenant Isolation**: Each tenant can have their own plugin configurations
4. **Service Contract**: All plugins must implement the `BaseServicePlugin` contract

## 1. BaseServicePlugin Contract

The `BaseServicePlugin` is an abstract base class (ABC) that defines the core interface that all plugins must implement.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID
from enum import Enum
from typing import List, Dict, Any, Optional
```

### 1.1 Data Classes

#### Capability

```python
@dataclass
class Capability:
    """Что плагин умеет делать."""
    name: str                          # "document_generation", "calculation"
    display_name: str
    description: str
    input_schema: dict                 # JSON Schema — что плагин принимает
    output_schema: dict                # JSON Schema — что возвращает
    examples: List[Dict] = field(default_factory=list)
```

#### Intent

```python
@dataclass
class Intent:
    """Интент — что хочет пользователь."""
    intent_type: str                   # "document_submission", "price_calculation"
    entities: Dict[str, Any]           # извлечённые сущности
    confidence: float                  # 0.0 - 1.0
    raw_message: str                   # исходный текст
    language: str = "ru"
```

#### ConversationContext

```python
@dataclass
class ConversationContext:
    """Контекст разговора — что было до этого."""
    conversation_id: UUID
    tenant_id: UUID
    user_id: UUID | None
    channel_type: str
    messages: List[Dict]               # последние N сообщений [{"role":"user","content":"..."}]
    external_user_id: str | None       # Telegram user_id, email
    metadata: Dict = field(default_factory=dict)
```

#### ActionType Enum

```python
class ActionType(str, Enum):
    SEND_MESSAGE = "send_message"
    CALL_API = "call_api"
    WAIT_FOR_INPUT = "wait_for_input"
    TRANSFER_TO_HUMAN = "transfer_to_human"
    SCHEDULE_TASK = "schedule_task"
    UPDATE_STATE = "update_state"
```

#### Action

```python
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
```

#### ServiceResult

```python
@dataclass
class ServiceResult:
    """Результат выполнения плагина."""
    success: bool
    response_text: str | None          # текст для пользователя (может быть None если только action)
    structured_data: dict | None       # структурированные данные (например рассчитанная цена)
    actions: list[Action]              # действия которые нужно выполнить
    continue_conversation: bool = True # продолжить диалог или закрыть
    confidence: float = 1.0            # уверенность плагина в ответе (для эскалации)
```

#### PluginHealth

```python
@dataclass
class PluginHealth:
    status: str                        # "healthy", "degraded", "unhealthy"
    last_error: str | None
    total_executions: int
    success_rate: float
    avg_duration_ms: float
```

#### ToolDefinition

```python
@dataclass
class ToolDefinition:
    """API endpoint который PromptDrivenPlugin может вызывать."""
    name: str                          # "check_wagon_status"
    description: str                   # "Проверяет статус вагона по номеру"
    endpoint: str                      # "https://api.logistics.ru/v1/wagons/{wagon_number}"
    method: str                        # "GET", "POST"
    input_schema: dict                 # JSON Schema
    auth_type: str                     # "none", "api_key", "bearer", "basic"
```

#### ExampleConversation

```python
@dataclass
class ExampleConversation:
    """Пример диалога для few-shot обучения плагина."""
    user_message: str
    assistant_response: str
    intent: str | None
    entities: dict | None
```

### 1.2 Abstract Methods

```python
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
    async def get_capabilities(self) -> List[Capability]:
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
    async def validate_config(self, config: Dict) -> bool:
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

## 2. Plugin Lifecycle

The lifecycle of a plugin is as follows:

1. **Register** - Plugin is registered with the PluginRegistry
2. **Validate** - Configuration is validated using `validate_config()`
3. **Activate** - Plugin is activated for a specific tenant using `on_install()`
4. **Deactivate** - Plugin is deactivated for a tenant using `on_uninstall()`
5. **Uninstall** - Plugin is completely uninstalled using `on_uninstall()`

### 2.1 Register

```python
async def register(self, plugin: BaseServicePlugin) -> None:
    """Зарегистрировать плагин в реестре.
    Индексирует capabilities для быстрого поиска."""
```

### 2.2 Validate

```python
async def validate_config(self, config: Dict) -> bool:
    """Валидировать per-tenant конфигурацию плагина.
    Вызывается при установке/обновлении плагина tenant'ом."""
```

### 2.3 Activate

```python
async def on_install(self, tenant_id: UUID) -> None:
    """Вызывается когда tenant устанавливает плагин.
    Создаёт ресурсы, БД-записи, подготавливает окружение."""
```

### 2.4 Deactivate

```python
async def on_uninstall(self, tenant_id: UUID) -> None:
    """Вызывается когда tenant удаляет плагин.
    Очищает ресурсы, удаляет БД-записи."""
```

## 3. Capability

A plugin declares its capabilities using the `Capability` data class. Each capability represents a specific function or feature that the plugin can perform.

```python
@dataclass
class Capability:
    name: str                          # Имя capability (например "document_generation")
    display_name: str                     # Отображаемое имя
    description: str           # Описание
    input_schema: dict                 # JSON Schema — что плагин принимает
    output_schema: dict            # JSON Schema — что возвращает
    examples: List[Dict] = field(default_factory=list)  # Примеры использования
```

### 3.1 Capability JSON Schema

The `input_schema` and `output_schema` should follow JSON Schema specification for validation and documentation purposes.

Example:
```json
{
  "type": "object",
  "properties": {
    "wagon_number": {
      "type": "string",
      "description": "Номер вагона"
    },
    "cargo_type": {
      "type": "string",
      "description": "Тип груза",
      "enum": ["dry_goods", "liquid", "bulk"]
    }
  },
  "required": ["wagon_number"]
}
```

## 4. Intent

The `Intent` data class represents what a user wants to do, extracted from their message.

```python
@dataclass
class Intent:
    intent_type: str                   # Тип интента (например "document_submission")
    entities: Dict[str, Any]               # Извлечённые сущности
    confidence: float                  # Уверенность в интенте (от 0.0 до 1.0)
    raw_message: str                     # Исходное сообщение пользователя
    language: str = "ru"               # Язык сообщения
```

## 5. Action

Plugins can request various actions to be performed by the system.

### 5.1 Action Types

The following action types are supported:

- `SEND_MESSAGE` - Send a message to the user
- `CALL_API` - Call an external API endpoint
- `WAIT_FOR_INPUT` - Wait for additional user input
- `TRANSFER_TO_HUMAN` - Transfer conversation to human agent
- `SCHEDULE_TASK` - Schedule a task for later execution
- `UPDATE_STATE` - Update conversation state

### 5.2 Action Payload Examples

#### SEND_MESSAGE
```json
{
  "text": "Ваш запрос обработан",
  "buttons": ["Да", "Нет"],
  "attachments": [
    {
      "file_type": "document",
      "file_url": "https://example.com/document.pdf"
    }
  ]
}
```

#### CALL_API
```json
{
  "url": "https://api.logistics.ru/v1/wagons/12345",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer token123"
  }
}
```

#### WAIT_FOR_INPUT
```json
{
  "prompt": "Пожалуйста, укажите номер вагона",
  "entity": "wagon_number",
  "timeout_sec": 300
}
```

#### TRANSFER_TO_HUMAN
```json
{
  "reason": "low_confidence",
  "department": "support"
}
```

#### SCHEDULE_TASK
```json
{
  "task_name": "check_status",
  "execute_at": "2026-07-02T15:00:00Z",
  "payload": {
    "conversation_id": "uuid-123"
  }
}
```

## 6. ServiceResult

The `ServiceResult` represents the plugin's response to an intent.

```python
@dataclass
class ServiceResult:
    success: bool
    response_text: str | None          # текст для пользователя
    structured_data: dict | None   # структурированные данные
    actions: List[Action]              # действия которые нужно выполнить
    continue_conversation: bool = True # продолжить диалог или закрыть
    confidence: float = 1.0      # уверенность плагина
```

## 7. PluginHealth

The `PluginHealth` class represents the health status of a plugin.

```python
@dataclass
class PluginHealth:
    status: str                        # "healthy", "degraded", "unhealthy"
    last_error: str | None
    total_executions: int
    success_rate: float
    avg_duration_ms: float
```

## 8. PromptDrivenPlugin

Prompt-driven plugins are designed for non-code configuration where business logic is described through prompts, tools, and examples.

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

    def __init__(
        self,
        system_prompt: str,
        tools: List[ToolDefinition],
        response_template: str = "{{ response }}",
        examples: List[ExampleConversation] = None,
        inference_pool: InferencePool = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.tools = tools
        self.response_template = response_template
        self.examples = examples or []
        self._inference_pool = inference_pool
```

### 8.1 Prompt-Driven Plugin Configuration

#### ToolDefinition JSON Schema

```json
{
  "name": "check_wagon_status",
  "description": "Проверяет статус вагона по номеру",
  "endpoint": "https://api.logistics.ru/v1/wagons/{wagon_number}",
  "method": "GET",
  "input_schema": {
    "type": "object",
    "properties": {
      "wagon_number": {
        "type": "string"
      }
    },
    "required": ["wagon_number"]
  },
  "auth_type": "bearer"
}
```

## 9. Plugin Manifest

Each plugin must have a manifest file (`plugin.json`) that contains metadata about the plugin.

### 9.1 plugin.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "plugin_id",
    "display_name",
    "description",
    "version",
    "type"
  ],
  "properties": {
    "plugin_id": {
      "type": "string",
      "description": "Уникальный идентификатор плагина"
    },
    "display_name": {
      "type": "string",
      "description": "Отображаемое имя плагина"
    },
    "description": {
      "type": "string",
      "description": "Описание плагина"
    },
    "version": {
      "type": "string",
      "description": "Версия плагина"
    },
    "type": {
      "type": "string",
      "enum": ["builtin", "custom", "prompt_driven"],
      "description": "Тип плагина"
    },
    "is_builtin": {
      "type": "boolean",
      "description": "Является ли встроенным плагином"
    },
    "capabilities": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "config_schema": {
      "type": "object",
      "description": "JSON Schema для конфигурации плагина"
    },
    "required_permissions": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "dependencies": {
      "type": "object",
      "additionalProperties": {
        "type": "string"
      }
    }
  }
}
```

## 10. Tool Definitions

Plugins can declare external API calls they need to perform through Tool Definitions.

### 10.1 ToolDefinition Structure

```python
@dataclass
class ToolDefinition:
    name: str                          # Имя инструмента
    description: str                       # Описание
    endpoint: str                      # URL API endpoint
    method: str                         # HTTP метод
    input_schema: dict                           # JSON Schema для входных данных
    auth_type: str                     # Тип авторизации
```

## 11. Examples

### 11.1 Simple FAQ Plugin

```python
class FaqPlugin(BaseServicePlugin):
    """Simple FAQ plugin for knowledge base queries."""

    plugin_id = "faq"
    display_name = "Knowledge Base Q&A"
    description = "Searches knowledge base and answers FAQ questions"
    version = "1.0.0"

    async def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="faq_search",
                display_name="FAQ Search",
                description="Searches knowledge base for answers",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "confidence": {"type": "number"}
                    }
                }
            )
        ]

    async def handle_intent(self, intent: Intent, context: ConversationContext) -> ServiceResult:
        # Implementation of FAQ search logic
        pass

    async def validate_config(self, config: Dict) -> bool:
        # Validate FAQ configuration
        pass

    async def on_install(self, tenant_id: UUID) -> None:
        # Initialize FAQ resources
        pass

    async def on_uninstall(self, tenant_id: UUID) -> None:
        # Cleanup FAQ resources
        pass

    async def health_check(self) -> PluginHealth:
        # Health check implementation
        pass
```

### 11.2 Calculator Plugin with Tools

```python
class CalculatorPlugin(BaseServicePlugin):
    """Plugin for railway tariff calculations."""

    plugin_id = "calculator"
    display_name = "Railway Tariff Calculator"
    description = "Calculates railway freight tariffs"
    version = "1.0.0"

    def __init__(self):
        self.tools = [
            ToolDefinition(
                name="calculate_tariff",
                description="Calculate freight tariff",
                endpoint="https://api.logistics.ru/v1/calculate",
                method="POST",
                input_schema={
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                        "cargo_weight": {"type": "number"},
                        "cargo_type": {"type": "string"}
                    },
                    "required": ["origin", "destination", "cargo_weight"]
                },
                auth_type="bearer"
            )
        ]

    async def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="calculation",
                display_name="Tariff Calculation",
                description="Calculates railway freight tariffs",
                input_schema={
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                        "cargo_weight": {"type": "number"}
                    },
                    "required": ["origin", "destination", "cargo_weight"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "cost": {"type": "number"},
                        "currency": {"type": "string"},
                        "details": {"type": "object"}
                    }
                }
            )
        ]
```

## 12. Database Schema

### 12.1 Service Definitions

```sql
CREATE TABLE service_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    description TEXT,
    version VARCHAR DEFAULT '1.0.0',
    is_builtin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    capabilities TEXT[],
    config_schema JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 12.2 Service Instances

```sql
CREATE TABLE service_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_definition_id UUID NOT NULL REFERENCES service_definitions(id) ON DELETE CASCADE,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    installed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 12.3 Service Bindings

```sql
CREATE TABLE service_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_instance_id UUID NOT NULL REFERENCES service_instances(id) ON DELETE CASCADE,
    channel_id UUID REFERENCES channels(id) ON DELETE SET NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 12.4 Service Executions

```sql
CREATE TABLE service_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_instance_id UUID REFERENCES service_instances(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    intent VARCHAR,
    entities JSONB,
    result VARCHAR DEFAULT 'success',
    response_text TEXT,
    duration_ms INTEGER,
    tokens_used INTEGER,
    cost_usd NUMERIC,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 13. Versioning and Dependency Management

### 13.1 Plugin Versioning

Plugins should follow semantic versioning (MAJOR.MINOR.PATCH).

### 13.2 Dependency Management

Plugins may declare dependencies in their manifest:
```json
{
  "dependencies": {
    "aether-sdk": ">=1.0.0",
    "python": ">=3.9"
  }
}
```

## 14. Sandboxing and Security

### 14.1 Required Permissions

Plugins must declare required permissions in their manifest:
```json
{
  "required_permissions": [
    "read_messages",
    "write_conversations",
    "api_call"
  ]
}
```

### 14.2 Security Considerations

- Plugin execution environment must be sandboxed
- Plugins must not be allowed to access system resources directly
- All external API calls must be properly authenticated and validated
- Plugin code should not be allowed to execute system commands
- File system access should be restricted to specific directories
- Memory usage should be monitored and limited
- Network access should be restricted to allowed endpoints only

### 14.3 Sandboxed Execution

All plugins run in a restricted execution environment with:
- Limited system access
- Memory limits
- Network restrictions
- No direct file system access
- Controlled API call permissions

## 15. Plugin Development Best Practices

### 15.1 Error Handling

Plugins should handle errors gracefully and provide meaningful error messages to the system.

### 15.2 Performance

Plugins should be optimized for performance:
- Minimize external API calls
- Cache results when appropriate
- Handle timeouts properly
- Monitor execution time

### 15.3 Logging

Plugins should include appropriate logging for debugging and monitoring purposes.

### 15.4 Testing

All plugins should include unit tests and integration tests to ensure they work correctly.
