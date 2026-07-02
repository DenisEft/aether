# 📁 Channels — Система каналов связи

Адаптеры каналов Aether. Каждый канал реализует `BaseChannel` (ABC) — channel-agnostic архитектура.

**MVP:** Telegram Bot, Web Widget, Email (SMTP/IMAP).
**Phase 2:** WhatsApp, VK Mini Apps, REST API.

**Принцип:** Channel Abstraction Layer — добавление нового канала = новый adapter + запись в БД, без изменения core.

---

## 📊 Обзор

```
backend/app/services/channels/
├── base.py
│   ⚡ 1 класс: BaseChannel (ABC)
│   ⚡ 3 dataclass: ChannelCapability, NormalizedMessage, DeliveryResult
│   ⚡ 1 enum: ChannelType
│
├── router.py
│   ⚡ 1 класс: ChannelRouter
│
├── normalizer.py
│   ⚡ 1 класс: MessageNormalizer
│
├── telegram.py
│   ⚡ 1 класс: TelegramChannel(BaseChannel)
│
├── web_widget.py
│   ⚡ 1 класс: WebWidgetChannel(BaseChannel)
│
├── email_channel.py
│   ⚡ 1 класс: EmailChannel(BaseChannel)
│
├── whatsapp.py              # Phase 2
│   ⚡ 1 класс: WhatsAppChannel(BaseChannel)
│
├── vk_miniapp.py             # Phase 2
│   ⚡ 1 класс: VKMiniAppChannel(BaseChannel)
│
└── rest_api.py
    ⚡ 1 класс: RestApiChannel(BaseChannel)

frontend/src/components/channels/
├── ChannelConfigForm.vue
├── ChannelStatusCard.vue
├── ChannelSelector.vue
├── WebWidget.vue
├── WebWidgetSettings.vue
├── TelegramConfigForm.vue
└── EmailConfigForm.vue
```

---

## 1. `base.py` — BaseChannel (ABC)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID
from enum import Enum

class ChannelType(str, Enum):
    """Типы каналов. Расширяется через БД (Channel.channel_type), 
    enum — для валидации на уровне приложения."""
    TELEGRAM = "telegram"
    WEB_WIDGET = "web_widget"
    EMAIL = "email"
    WHATSAPP = "whatsapp"        # Phase 2
    VK_MINIAPP = "vk_miniapp"    # Phase 2
    REST_API = "rest_api"

class MessageContentType(str, Enum):
    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"

@dataclass
class ChannelCapability:
    """Что канал умеет — динамически, не хардкод."""
    name: str                      # "send_text", "send_photo", "send_document"
    display_name: str
    content_types: list[str]       # поддерживаемые content types
    max_file_size_bytes: int | None
    supports_buttons: bool
    supports_carousel: bool
    supports_location: bool
    supports_payments: bool
    supports_push: bool            # может ли канал инициировать разговор

@dataclass
class NormalizedMessage:
    """Унифицированное сообщение — не зависит от канала."""
    tenant_id: UUID
    channel_type: ChannelType
    channel_id: UUID
    external_user_id: str           # Telegram user_id, email, widget session
    conversation_id: UUID | None
    content: str
    content_type: MessageContentType
    attachments: list[dict]         # [{"type":"photo","url":"...","file_id":"..."}]
    metadata: dict                  # raw payload, timestamp, locale
    raw_payload: dict               # оригинальный payload для отладки

@dataclass
class DeliveryResult:
    """Результат отправки сообщения в канал."""
    success: bool
    channel_message_id: str | None  # ID сообщения в канале
    error: str | None
    latency_ms: float
    channel_type: ChannelType

class BaseChannel(ABC):
    """Абстрактный адаптер канала связи.
    
    Все каналы (Telegram, WebWidget, Email, WhatsApp, REST API)
    реализуют этот контракт. ChannelRouter работает с BaseChannel,
    не зная конкретный тип канала."""
    
    channel_type: ChannelType
    
    @abstractmethod
    async def initialize(self) -> None:
        """Инициализация канала: подключение, проверка credentials."""
        ...
    
    @abstractmethod
    async def send_message(
        self,
        recipient: str,              # external_user_id или email или phone
        content: str,
        content_type: MessageContentType,
        attachments: list[dict] | None = None,
        buttons: list[dict] | None = None,   # [{"text":"...","callback":"..."}]
        metadata: dict | None = None,
    ) -> DeliveryResult:
        """Отправить сообщение через канал."""
        ...
    
    @abstractmethod
    async def receive_webhook(
        self,
        payload: dict,
        headers: dict,
    ) -> NormalizedMessage:
        """Обработать входящий webhook от провайдера канала.
        Возвращает NormalizedMessage — дальше через общий pipeline."""
        ...
    
    @abstractmethod
    async def get_capabilities(self) -> list[ChannelCapability]:
        """Возвращает что этот канал умеет.
        Используется для:
        - Выбора канала под тип сообщения (фото → Telegram, не Email)
        - Отображения в UI какие фичи доступны"""
        ...
    
    @abstractmethod
    async def validate_config(self, config: dict) -> bool:
        """Валидировать конфигурацию канала (токены, URL, ключи).
        Вызывается при создании/обновлении канала tenant'ом."""
        ...
    
    @abstractmethod
    async def health_check(self) -> dict:
        """Проверить что канал работает.
        Возвращает: {"status": "healthy", "latency_ms": 50, "last_error": None}"""
        ...
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение: закрытие соединений, WebSocket."""
        ...
```

---

## 2. `router.py` — ChannelRouter

```python
class ChannelRouter:
    """
    Маршрутизатор сообщений между каналами и AI Core.
    
    Incoming: принимает NormalizedMessage от канала, передаёт в pipeline.
    Outgoing: принимает ответ от AI/Plugins, выбирает канал для отправки.
    """
    
    def __init__(self) -> None:
        self._channels: dict[UUID, BaseChannel] = {}              # channel_id → channel
        self._tenant_channels: dict[UUID, dict[UUID, BaseChannel]] = {}  # tenant_id → {channel_id: channel}
        self._lock = asyncio.Lock()
    
    async def register_channel(
        self, channel_id: UUID, channel: BaseChannel, tenant_id: UUID
    ) -> None:
        """Зарегистрировать канал в роутере."""
        ...
    
    async def unregister_channel(self, channel_id: UUID) -> None:
        """Удалить канал из роутера."""
        ...
    
    async def route_incoming(
        self, message: NormalizedMessage
    ) -> NormalizedMessage:
        """
        Обработать входящее сообщение:
        1. Обогатить метаданными (tenant config, user profile)
        2. Передать в AI pipeline (через очередь Celery)
        """
        ...
    
    async def route_outgoing(
        self,
        tenant_id: UUID,
        recipient: str,
        content: str,
        preferred_channel_id: UUID | None = None,
        fallback_channel_types: list[ChannelType] | None = None,
    ) -> DeliveryResult:
        """
        Отправить ответ пользователю:
        1. Если preferred_channel_id задан → использовать его
        2. Иначе → канал из conversation context
        3. Если канал недоступен → пробовать fallback_channel_types
        4. Если все fallback недоступны → ошибка доставки
        """
        ...
    
    async def get_channel_for_recipient(
        self,
        tenant_id: UUID,
        external_user_id: str,
    ) -> BaseChannel | None:
        """Найти канал через который общается пользователь."""
        ...
    
    async def get_available_channels(
        self, tenant_id: UUID, capability: str | None = None
    ) -> list[BaseChannel]:
        """Список доступных каналов для tenant, опционально с фильтром по capability."""
        ...
    
    async def select_channel_by_capability(
        self,
        tenant_id: UUID,
        required_capability: str,
        preferred_channel_id: UUID | None = None,
    ) -> BaseChannel:
        """
        Выбрать канал подходящий по capability.
        Например: нужно отправить фото → исключаем Email.
        """
        ...
```

---

## 3. `normalizer.py` — MessageNormalizer

```python
class MessageNormalizer:
    """
    Нормализатор сообщений — приводит сообщения из разных каналов
    к единому формату NormalizedMessage перед передачей в AI pipeline.
    
    Каждый канал имеет свои особенности:
    - Telegram: callback_data в кнопках → text
    - Email: HTML → text (html2text)
    - WebWidget: rich metadata
    """
    
    async def normalize(
        self,
        channel_type: ChannelType,
        raw_payload: dict,
    ) -> NormalizedMessage:
        """Нормализовать сообщение из канала."""
        ...
    
    async def extract_attachments(
        self, channel_type: ChannelType, raw_payload: dict
    ) -> list[dict]:
        """Извлечь вложения из raw payload (фото, документы, аудио)."""
        ...
    
    async def convert_content_type(
        self, content: str, source_type: str, target_type: MessageContentType
    ) -> str:
        """Конвертировать контент между форматами (HTML→text, Markdown→HTML)."""
        ...
```

---

## 4. `telegram.py` — TelegramChannel

```python
class TelegramChannel(BaseChannel):
    """Адаптер Telegram Bot API через aiogram 3.x.
    
    Поддерживает:
    - Webhook и long polling режимы
    - Inline keyboards + callback обработка
    - File upload/download (до 50MB)
    - Telegram Web Apps интеграция
    - Payments (Telegram Stars)
    """
    
    channel_type = ChannelType.TELEGRAM
    
    def __init__(self) -> None:
        self._bot: Bot = None
        self._dispatcher: Dispatcher = None
        self._mode: str = "webhook"  # "webhook" или "polling"
    
    async def initialize(self) -> None:
        """Создать Bot, Dispatcher, зарегистрировать handlers."""
        ...
    
    async def send_message(
        self,
        recipient: str,
        content: str,
        content_type: MessageContentType,
        attachments: list[dict] | None = None,
        buttons: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> DeliveryResult:
        """
        Отправить сообщение в Telegram.
        Поддерживает: text, photo, document, media_group, inline_keyboard.
        """
        ...
    
    async def receive_webhook(
        self, payload: dict, headers: dict
    ) -> NormalizedMessage:
        """Обработать webhook от Telegram.
        
        Обрабатывает:
        - Обычные сообщения (text, photo, document, voice, video)
        - Callback queries (inline button clicks)
        - Команды (/start, /help)
        """
        ...
    
    async def get_capabilities(self) -> list[ChannelCapability]:
        """Telegram умеет: text, photo (до 10MB), document (до 50MB),
        audio, video, inline buttons, media groups, location, payments."""
        ...
    
    async def validate_config(self, config: dict) -> bool:
        """Проверить bot_token, webhook_url."""
        ...
    
    async def health_check(self) -> dict:
        """getMe() → статус бота."""
        ...
    
    async def shutdown(self) -> None:
        """Закрыть сессию бота."""
        ...
    
    # Приватные методы
    async def _build_inline_keyboard(self, buttons: list[dict]) -> InlineKeyboardMarkup:
        """Конвертировать универсальные buttons в Telegram InlineKeyboardMarkup."""
        ...
    
    async def _handle_callback(self, callback: CallbackQuery):
        """Обработчик inline button click."""
        ...
    
    async def _upload_file(self, file_path: str) -> InputFile:
        """Загрузить файл для отправки."""
        ...
```

---

## 5. `web_widget.py` — WebWidgetChannel

```python
class WebWidgetChannel(BaseChannel):
    """Адаптер Web Widget — встраиваемый чат на сайт клиента.
    
    WebSocket-based: FastAPI WebSocket endpoint.
    Клиентский JS виджет соединяется с сервером через WebSocket.
    """
    
    channel_type = ChannelType.WEB_WIDGET
    
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}   # session_id → WebSocket
        self._message_queue: dict[str, list[dict]] = {} # offline queue
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Запустить WebSocket manager."""
        ...
    
    async def handle_websocket(
        self,
        websocket: WebSocket,
        tenant_id: UUID,
        channel_id: UUID,
    ) -> None:
        """
        Основной WebSocket handler.
        FastAPI endpoint монтирует этот метод:
        
        @router.websocket("/ws/{channel_id}")
        async def ws_endpoint(websocket: WebSocket, channel_id: UUID):
            channel = get_channel(channel_id)
            await channel.handle_websocket(websocket, ...)
        
        Логика:
        1. Принять соединение
        2. Получить session_id из первого сообщения
        3. Зарегистрировать соединение
        4. Цикл: получать сообщения → нормализовать → в очередь pipeline
        5. Отправлять ответы из очереди
        6. При разрыве: сохранить в offline queue
        """
        ...
    
    async def send_message(
        self,
        recipient: str,              # session_id
        content: str,
        content_type: MessageContentType,
        attachments: list[dict] | None = None,
        buttons: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> DeliveryResult:
        """
        Отправить сообщение через WebSocket.
        Если соединение неактивно → сохранить в offline queue.
        """
        ...
    
    async def receive_webhook(
        self, payload: dict, headers: dict
    ) -> NormalizedMessage:
        """Не используется для WebSocket канала."""
        raise NotImplementedError("WebWidget использует WebSocket, не webhook")
    
    async def get_capabilities(self) -> list[ChannelCapability]:
        """Web Widget умеет всё: text, photo, document, buttons, carousel,
        location, payments — HTML/CSS/JS дают полный контроль."""
        ...
    
    async def validate_config(self, config: dict) -> bool:
        """Проверить настройки виджета: цвета, лого, позиция, greeting."""
        ...
    
    async def health_check(self) -> dict:
        """Проверить WebSocket endpoint доступен."""
        ...
    
    async def shutdown(self) -> None:
        """Закрыть все WebSocket соединения."""
        ...
```

---

## 6. `email_channel.py` — EmailChannel

```python
class EmailProvider(str, Enum):
    SMTP = "smtp"
    SES = "ses"
    POSTMARK = "postmark"
    RESEND = "resend"

class EmailChannel(BaseChannel):
    """Адаптер Email: SMTP/IMAP + ESP драйверы.
    
    Поддерживает:
    - SMTP отправка (aiosmtplib)
    - IMAP получение (aiosmtplib) + inbound webhook (Mailgun/SES/Postmark)
    - HTML шаблоны (Jinja2)
    - ESP провайдеры: Amazon SES, Postmark, Resend
    """
    
    channel_type = ChannelType.EMAIL
    
    def __init__(self) -> None:
        self._provider: EmailProvider = None
        self._template_engine: jinja2.Environment = None
    
    async def initialize(self) -> None:
        """Инициализировать SMTP/IMAP соединения, загрузить шаблоны."""
        ...
    
    async def send_message(
        self,
        recipient: str,              # email address
        content: str,
        content_type: MessageContentType,
        attachments: list[dict] | None = None,
        buttons: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> DeliveryResult:
        """
        Отправить email.
        content_type=HTML → отправить как HTML.
        content_type=TEXT → plain text.
        Jinja2 template: если metadata.template указан — рендерить шаблон.
        """
        ...
    
    async def receive_webhook(
        self, payload: dict, headers: dict
    ) -> NormalizedMessage:
        """Обработать входящий email:
        - Mailgun webhook: POST /webhooks/email/{channel_id}
        - SES inbound: SNS notification
        - Postmark inbound: webhook
        """
        ...
    
    async def receive_imap(self) -> list[NormalizedMessage]:
        """Альтернативный метод: IMAP polling для входящих писем."""
        ...
    
    async def get_capabilities(self) -> list[ChannelCapability]:
        """Email умеет: text, HTML, attachments (до 10-25MB depends on provider),
        НЕ умеет: buttons (только ссылки), carousel, location, push."""
        ...
    
    async def validate_config(self, config: dict) -> bool:
        """Проверить настройки: SMTP host/port/user/password, ESP API keys."""
        ...
    
    async def health_check(self) -> dict:
        """Проверить SMTP/IMAP соединение."""
        ...
    
    async def shutdown(self) -> None:
        """Закрыть SMTP/IMAP соединения."""
        ...
    
    # Приватные методы
    async def _render_template(
        self, template_name: str, context: dict
    ) -> str:
        """Рендерить Jinja2 шаблон письма."""
        ...
    
    async def _send_via_smtp(
        self, recipient: str, subject: str, html_body: str, attachments: list[dict]
    ) -> DeliveryResult:
        """Отправить через SMTP."""
        ...
    
    async def _send_via_ses(
        self, recipient: str, subject: str, html_body: str
    ) -> DeliveryResult:
        """Отправить через Amazon SES."""
        ...
```

---

## 7. `rest_api.py` — RestApiChannel

```python
class RestApiChannel(BaseChannel):
    """Адаптер REST API — для White-Label и headless интеграций.
    
    Клиент отправляет сообщения через REST API (POST /webhooks/generic/{channel_id}).
    Ответы доставляются через webhook клиента или polling.
    """
    
    channel_type = ChannelType.REST_API
    
    async def initialize(self) -> None:
        """Загрузить webhook endpoints из конфига."""
        ...
    
    async def send_message(
        self,
        recipient: str,              # client webhook URL или session_id
        content: str,
        content_type: MessageContentType,
        attachments: list[dict] | None = None,
        buttons: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> DeliveryResult:
        """
        Доставить ответ клиенту:
        1. Если recipient это URL → POST webhook
        2. Если recipient это session_id → сохранить в pending responses (клиент заберёт polling'ом)
        """
        ...
    
    async def receive_webhook(
        self, payload: dict, headers: dict
    ) -> NormalizedMessage:
        """Обработать входящий запрос от клиентского API."""
        ...
    
    async def get_capabilities(self) -> list[ChannelCapability]:
        """REST API умеет всё — клиент сам рендерит."""
        ...
    
    async def validate_config(self, config: dict) -> bool:
        """Проверить webhook URL, API keys."""
        ...
    
    async def health_check(self) -> dict:
        """Проверить webhook endpoint."""
        ...
    
    async def shutdown(self) -> None:
        """Очистить pending responses."""
        ...
```

---

## 8. WhatsAppChannel (Phase 2)

```python
class WhatsAppChannel(BaseChannel):
    """Адаптер WhatsApp Business Cloud API (Meta).
    
    Phase 2 — только когда Telegram становится рискованным в РФ.
    
    Требует:
    - Meta Business Account
    - WhatsApp Business API client
    - Template messages (утверждённые Meta)
    """
    
    channel_type = ChannelType.WHATSAPP
    
    # send_message: template messages, session messages, media
    # receive_webhook: Meta Graph API webhook
    # get_capabilities: template messages, buttons, carousel, location
    # validate_config: phone_number_id, access_token, verify_token
    # health_check: проверить webhook endpoint
```

---

## 9. Фронтенд компоненты каналов

```
frontend/src/components/channels/
├── ChannelConfigForm.vue
│   ⚡ Компонент: ChannelConfigForm
│   Props: channelType, config, credentials
│   Emits: save, test, delete
│   Динамически рендерит форму под тип канала
│   (Telegram → bot_token, WebWidget → color/logo/position, Email → SMTP/SES keys)
│
├── ChannelStatusCard.vue
│   ⚡ Компонент: ChannelStatusCard
│   Props: channel (ChannelResponse)
│   Отображает: иконка канала, название, статус (зелёный/красный индикатор),
│   метрики (messages today, errors, avg latency)
│   Emits: test, edit, delete
│
├── ChannelSelector.vue
│   ⚡ Компонент: ChannelSelector
│   Props: channels, modelValue (selected channel_ids)
│   Emits: update:modelValue
│   Выбор активных каналов для service binding
│
├── WebWidget.vue
│   ⚡ Компонент: WebWidget (автономный, для встраивания на сайт клиента)
│   Props: channelId, tenantSlug, position ("bottom-right"), greeting
│   WebSocket соединение с Aether
│   Reconnection logic с экспоненциальным backoff
│   Offline message queue в localStorage
│
├── WebWidgetSettings.vue
│   ⚡ Компонент: WebWidgetSettings
│   Props: config (WebWidgetConfig)
│   Emits: update:config
│   Настройки: primaryColor, position, logo, greetingMessage, offlineMessage,
│   workingHours, autoOpen (delay)
│   Live preview виджета
│
├── TelegramConfigForm.vue
│   ⚡ Компонент: TelegramConfigForm
│   Props: config
│   Emits: save
│   Поля: botToken, webhookUrl, mode (webhook/polling)
│
└── EmailConfigForm.vue
    ⚡ Компонент: EmailConfigForm
    Props: config
    Emits: save
    Поля: provider (smtp/ses/postmark/resend), smtpHost, smtpPort,
    smtpUser, smtpPassword, fromName, fromEmail
```

### WebWidget API (JavaScript client)

```typescript
// window.AetherWidget — глобальный объект на сайте клиента
interface AetherWidget {
  init(config: {
    channelId: string;
    tenantSlug: string;
    apiHost: string;             // "https://api.aether.cloud"
    position?: "bottom-right" | "bottom-left";
    primaryColor?: string;
    greetingMessage?: string;
    autoOpenDelay?: number;      // ms, 0 = manual only
    locale?: string;
  }): void;
  
  open(): void;
  close(): void;
  sendMessage(text: string): void;
  onMessage(callback: (msg: { role: string; content: string }) => void): void;
  destroy(): void;
}
```

---

## 📊 Статистика модуля

| Компонент | Файл | Классов | Методов |
|-----------|------|---------|---------|
| BaseChannel | base.py | 1 (ABC) + 3 dataclass | 6 abstract |
| ChannelRouter | router.py | 1 | 7 |
| MessageNormalizer | normalizer.py | 1 | 3 |
| TelegramChannel | telegram.py | 1 | 8 (+3 private) |
| WebWidgetChannel | web_widget.py | 1 | 7 |
| EmailChannel | email_channel.py | 1 | 7 (+3 private) |
| RestApiChannel | rest_api.py | 1 | 6 |
| WhatsAppChannel | whatsapp.py | 1 | 6 |
| Frontend | 7 компонентов | — | — |
| **Итого** | **~9 файлов** | **~9 классов** | **~50 методов** |
