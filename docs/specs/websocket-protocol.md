# WebSocket Protocol Specification — WebWidget Channel

## Endpoint

```
wss://{host}/ws/widget/{tenant_id}?token={jwt_token}
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|:------------:|----------|
| `tenant_id` | UUID (v4) | ✅ | Идентификатор tenant'а |
| `token` | JWT string | ✅ | Access token (query parameter при коннекте) |

**Пример URL:**
```
wss://api.aether.cloud/ws/widget/550e8400-e29b-41d4-a716-446655440000?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Аутентификация

JWT token передаётся **только** через query параметр при установлении соединения. После успешной аутентификации сервер отвечает `system.connected`.

**Процесс аутентификации:**

```
Client                              Server
   |                                    |
   |  CONNECT wss://host/ws/widget/{tenant_id}?token={jwt}
   |──────────────────────────────────>|
   |                                    |  ✓ Валидация JWT (подпись, expiry, tenant_id)
   |  system.connected                  |
   |<──────────────────────────────────|
   |                                    |
```

**При невалидном JWT соединение отклоняется** (HTTP 403 при WebSocket upgrade):

```json
{
  "error": "invalid_token",
  "message": "JWT token is expired or has an invalid signature"
}
```

**JWT payload структура:**
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",   // user_id
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "ws_sess_abc123",
  "exp": 1750000000,
  "iat": 1749996400,
  "scope": ["chat:read", "chat:write"]
}
```

---

## Heartbeat (Ping/Pong)

| Параметр | Значение |
|----------|----------|
| Интервал | 30 секунд |
| Максимум пропущенных | 3 |
| Действие при превышении | Закрытие соединения (close code 4001) |

```
Client                              Server
   |                                    |
   |  ping (WebSocket frame opcode 0x9) |
   |──────────────────────────────────>|
   |  pong (WebSocket frame opcode 0xA) |
   |<──────────────────────────────────|
   |                                    |
   |     ... 30 сек ...                 |
   |  ping                               |
   |──────────────────────────────────>|
   |     (pong не получен)              |
   |                                    |
   |     ... × 3 пропущенных            |
   |  CLOSE 4001 "heartbeat_timeout"    |
   |<──────────────────────────────────|
```

Сервер инициирует WebSocket-level `ping` frames (opcode 0x9). Клиент обязан отвечать `pong` (opcode 0xA). При 3 пропущенных pong — сервер закрывает соединение с close code `4001`.

---

## Форматы сообщений

Все сообщения — JSON объекты. Каждое сообщение имеет поле `type` и `timestamp` (ISO 8601 UTC).

### Общие поля

```json
{
  "type": "string",           // тип сообщения
  "id": "string",             // UUID v4 — уникальный ID сообщения (client-generated для исходящих)
  "timestamp": "string",      // ISO 8601 UTC, например "2026-06-25T05:44:00Z"
  "seq": 0                    // monotonically increasing sequence number (для ordering)
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Тип сообщения (описан ниже) |
| `id` | string (UUID v4) | Уникальный идентификатор сообщения |
| `timestamp` | string (ISO 8601) | Время отправки в UTC |
| `seq` | integer | Монаotonically increasing sequence number, используется для гарантии порядка доставки |

---

### `chat.message` — Client → Server

Отправка сообщения пользователем.

```json
{
  "type": "chat.message",
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp": "2026-06-25T05:44:00Z",
  "seq": 1,
  "conversation_id": "conv_abc123",
  "content": "Здравствуйте, хочу заказать перевозку",
  "attachments": [
    {
      "file_type": "image",
      "filename": "cargo-photo.jpg",
      "mime_type": "image/jpeg",
      "file_size_bytes": 245000,
      "file_url": "https://cdn.aether.cloud/uploads/550e8400/cargo-photo.jpg"
    }
  ],
  "metadata": {
    "locale": "ru",
    "user_agent": "WebWidget/1.0.0",
    "browser": "Chrome 126"
  }
}
```

| Поле | Тип | Обязательный | Описание |
|------|-----|:------------:|----------|
| `type` | string | ✅ | Всегда `"chat.message"` |
| `id` | string (UUID) | ✅ | Client-generated UUID |
| `conversation_id` | string | условно | Существующий ID диалога. `null` — новый диалог (сервер создаст) |
| `content` | string | ✅ | Текст сообщения (max 10 000 символов) |
| `attachments` | array | ❌ | Вложения (max 5 файлов, max 10 MB каждый) |
| `metadata` | object | ❌ | Дополнительные метаданные клиента |

**Attachment объект:**

| Поле | Тип | Описание |
|------|-----|----------|
| `file_type` | string | `image`, `document`, `audio`, `video` |
| `filename` | string | Имя файла |
| `mime_type` | string | MIME тип |
| `file_size_bytes` | integer | Размер в байтах |
| `file_url` | string | URL предзагруженного файла (upload через REST API до отправки) |

---

### `chat.response` — Server → Client

Ответ от AI или оператора.

```json
{
  "type": "chat.response",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-06-25T05:44:02Z",
  "seq": 2,
  "conversation_id": "conv_abc123",
  "reply_to": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "role": "ai",
  "content": "Добрый день! Я помогу вам оформить перевозку. Укажите, пожалуйста, станцию отправления и назначения.",
  "attachments": [
    {
      "file_type": "document",
      "filename": "tariff-table.pdf",
      "file_url": "https://cdn.aether.cloud/docs/tariff-table.pdf"
    }
  ],
  "metadata": {
    "intent": "booking",
    "intent_confidence": 0.92,
    "model": "llama-70b",
    "driver": "ollama",
    "processing_time_ms": 1850,
    "tokens_used": 142
  }
}
```

| Поле | Тип | Обязательный | Описание |
|------|-----|:------------:|----------|
| `type` | string | ✅ | Всегда `"chat.response"` |
| `reply_to` | string | ✅ | `id` сообщения `chat.message`, на которое ответ |
| `conversation_id` | string | ✅ | ID диалога |
| `role` | string | ✅ | `"ai"` или `"human"` (оператор) |
| `content` | string | ✅ | Текст ответа |
| `attachments` | array | ❌ | Вложения от AI/оператора |
| `metadata` | object | ❌ | Metadata: intent, model, processing time, tokens |

---

### `chat.typing` — Server → Client

Индикатор набора текста ("AI печатает...").

```json
{
  "type": "chat.typing",
  "id": "typing_123",
  "timestamp": "2026-06-25T05:44:01Z",
  "seq": 3,
  "conversation_id": "conv_abc123",
  "status": "started",
  "role": "ai"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"chat.typing"` |
| `status` | string | `"started"` — показать индикатор, `"stopped"` — скрыть |
| `role` | string | `"ai"` или `"human"` |
| `conversation_id` | string | ID диалога |

**Поведение:**
- `status: "started"` — показать анимацию набора
- `status: "stopped"` — скрыть анимацию
- Если `chat.typing` со `status: "started"` не followed by `chat.response` в течение 30 секунд — клиент должен считать что обработка зависла и показать fallback сообщение

---

### `chat.quick_replies` — Server → Client

Предложенные быстрые ответы (кнопки).

```json
{
  "type": "chat.quick_replies",
  "id": "qr_456",
  "timestamp": "2026-06-25T05:44:03Z",
  "seq": 4,
  "conversation_id": "conv_abc123",
  "replies": [
    {
      "id": "qr_station",
      "label": "Москва",
      "payload": "Станция отправления: Москва",
      "metadata": {
        "entity": "departure_station"
      }
    },
    {
      "id": "qr_station_2",
      "label": "Санкт-Петербург",
      "payload": "Станция отправления: Санкт-Петербург",
      "metadata": {
        "entity": "departure_station"
      }
    },
    {
      "id": "qr_price",
      "label": "Рассчитать стоимость",
      "payload": "Рассчитать стоимость перевозки",
      "metadata": {
        "intent": "calculation"
      }
    }
  ],
  "expires_in_seconds": 60
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"chat.quick_replies"` |
| `replies` | array | Список быстрых ответов (max 10) |
| `expires_in_seconds` | integer | Через сколько секунд скрыть кнопки (default: 60) |

**Reply объект:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | Уникальный ID кнопки |
| `label` | string | Текст кнопки (показывается пользователю) |
| `payload` | string | Текст, отправляемый как `chat.message` при клике |
| `metadata` | object | Опциональные метаданные (entity, intent hint) |

При клике на quick reply клиент отправляет `chat.message` с `content` равным `payload` соответствующей кнопки.

---

### `chat.delivery_status` — Server → Client

Статус доставки сообщения пользователя.

```json
{
  "type": "chat.delivery_status",
  "id": "ds_789",
  "timestamp": "2026-06-25T05:44:01Z",
  "seq": 5,
  "message_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "delivered"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"chat.delivery_status"` |
| `message_id` | string | `id` оригинального `chat.message` |
| `status` | string | Статус доставки |

**Возможные статусы:**

| Статус | Описание |
|--------|----------|
| `sent` | Сообщение принято сервером |
| `delivered` | Сообщение обработано pipeline'ом (intent classified) |
| `read` | Ответ сформирован и отправлен |
| `failed` | Ошибка обработки (см. `system.error`) |

---

### `system.error` — Server → Client

Ошибка с кодом и сообщением.

```json
{
  "type": "system.error",
  "id": "err_001",
  "timestamp": "2026-06-25T05:44:05Z",
  "seq": 6,
  "code": "INTENT_PROCESSING_FAILED",
  "message": "Не удалось обработать запрос. Попробуйте переформулировать.",
  "message_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "details": {
    "intent_confidence": 0.21,
    "threshold": 0.4,
    "fallback_used": true
  }
}
```

| Поле | Тип | Обязательный | Описание |
|------|-----|:------------:|----------|
| `type` | string | ✅ | Всегда `"system.error"` |
| `code` | string | ✅ | Machine-readable error code |
| `message` | string | ✅ | Human-readable сообщение для UI |
| `message_id` | string | ❌ | ID сообщения, которое вызвало ошибку |
| `details` | object | ❌ | Дополнительные данные для отладки |

**Коды ошибок:**

| Code | HTTP-аналог | Описание |
|------|:-----------:|----------|
| `INVALID_TOKEN` | 401 | JWT невалиден |
| `TENANT_NOT_FOUND` | 404 | Tenant не найден |
| `INTENT_PROCESSING_FAILED` | 500 | Ошибка классификации интента |
| `AI_DRIVER_UNAVAILABLE` | 503 | Все AI драйверы недоступны |
| `PLUGIN_EXECUTION_ERROR` | 500 | Ошибка выполнения плагина |
| `RATE_LIMITED` | 429 | Превышен лимит сообщений |
| `ATTACHMENT_TOO_LARGE` | 413 | Файл слишком большой |
| `CONVERSATION_EXPIRED` | 410 | Диалог истёк |
| `CHANNEL_DISABLED` | 403 | WebWidget канал отключён для tenant |

---

### `system.connected` — Server → Client

Успешное установление соединения.

```json
{
  "type": "system.connected",
  "id": "conn_001",
  "timestamp": "2026-06-25T05:43:59Z",
  "seq": 0,
  "session_id": "ws_sess_xyz789",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "usr_abc123",
  "config": {
    "greeting_message": "Здравствуйте! Чем могу помочь?",
    "locale": "ru",
    "max_file_size_bytes": 10485760,
    "rate_limit": {
      "messages_per_minute": 30,
      "messages_per_day": 1000
    },
    "working_hours": {
      "enabled": true,
      "timezone": "Europe/Moscow",
      "schedule": "09:00-18:00"
    }
  }
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"system.connected"` |
| `session_id` | string | Уникальный ID сессии WebSocket |
| `tenant_id` | string | ID tenant'а |
| `user_id` | string | ID пользователя из JWT |
| `config` | object | Конфигурация WebWidget (greeting, locale, limits) |

Это **первое сообщение** после успешного handshake. Клиент должен показать `greeting_message`.

---

### `system.reconnect` — Server → Client

Восстановление сессии после разрыва.

```json
{
  "type": "system.reconnect",
  "id": "reconn_001",
  "timestamp": "2026-06-25T05:45:10Z",
  "seq": 100,
  "session_id": "ws_sess_xyz789",
  "conversation_id": "conv_abc123",
  "missed_messages_count": 2,
  "last_seq_before_disconnect": 99
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Всегда `"system.reconnect"` |
| `session_id` | string | ID сессии (тот же, что был до разрыва) |
| `conversation_id` | string | ID диалога для восстановления |
| `missed_messages_count` | integer | Количество сообщений, отправленных сервером пока клиент был offline |
| `last_seq_before_disconnect` | integer | Последнее `seq`, которое знал клиент до разрыва |

---

## Reconnection Policy

Экспоненциальный backoff с джиттером:

| Параметр | Значение |
|----------|----------|
| Базовая задержка | 1 секунда |
| Множитель | 2× |
| Максимальная задержка | 30 секунд |
| Максимум попыток | 10 |
| Джиттер | ±25% случайный |

**Формула задержки:**

```
delay = min(1s × 2^n, 30s) × (0.75 + random() × 0.5)
```

где `n` — номер попытки (0-indexed).

**Таблица задержек (среднее):**

| Попытка | Формула | Задержка |
|:-------:|---------|----------|
| 1 | `min(1s × 2⁰, 30s)` | ~1s |
| 2 | `min(1s × 2¹, 30s)` | ~2s |
| 3 | `min(1s × 2², 30s)` | ~4s |
| 4 | `min(1s × 2³, 30s)` | ~8s |
| 5 | `min(1s × 2⁴, 30s)` | ~16s |
| 6 | `min(1s × 2⁵, 30s)` | ~30s |
| 7–10 | clamped | ~30s |

После 10 неудачных попыток — показать offline-UI с возможностью ручной перезагрузки.

---

## Session Persistence

Если WebSocket разорван менее чем на **60 секунд**, сервер восстанавливает контекст диалога:

```
Client                              Server
   |                                    |
   |  (соединение разорвано)            |
   |                                    |
   |     ... < 60 сек ...               |
   |                                    |
   |  CONNECT (тот же JWT + session_id) |
   |──────────────────────────────────>|
   |                                    |
   |  system.reconnect (conv_abc123)    |
   |<──────────────────────────────────|
   |                                    |
   |  chat.response (пропущенные)       |
   |<──────────────────────────────────|
   |  ... (N пропущенных сообщений)     |
   |<──────────────────────────────────|
```

**Условия восстановления:**
1. Тот же JWT token (не истёк)
2. Сессия существует в Redis (< 60 секунд с разрыва)
3. `conversation_id` из сессии

При восстановлении сервер:
1. Отправляет `system.reconnect`
2. Достаивает пропущенные `chat.response` сообщения в порядке `seq`
3. Возобновляет нормальную обработку

Если сессия старше 60 секунд — сервер обрабатывает как новое соединение (`system.connected`).

---

## Offline Queue

Сообщения, отправленные клиентом пока он был offline, кэшируются в `localStorage` и доставляются при reconnect.

**Хранение:** `localStorage` с ключом `aether:offline_queue:{tenant_id}`

```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "timestamp": "2026-06-25T05:44:00Z",
    "seq": 95,
    "conversation_id": "conv_abc123",
    "content": "Мой вопрос...",
    "status": "pending"
  }
]
```

**Поведение при reconnect:**

1. Клиент получает `system.reconnect`
2. Клиент сортирует offline queue по `seq`
3. Посылает сообщения в порядке `seq` (гарантированный порядок)
4. Каждое сообщение помечается как `delivered` при получении `chat.delivery_status`
5. Если `chat.delivery_status` не получен за 15 секунд — message помечается как `retry` и пересылается один раз
6. После полной доставки queue очищается из `localStorage`

**Гарантия порядка:** Sequence numbers (`seq`) гарантируют что сообщения доставляются в том порядке, в котором были отправлены, даже если сетевые пакеты пришли в другом порядке.

---

## Full Connection Lifecycle

```
                    ┌─────────────────┐
                    │  Initial Connect │
                    └────────┬────────┘
                             │
                    CONNECT wss://host/ws/widget/{tenant_id}?token={jwt}
                             │
                    ┌────────▼────────┐
                    │ Auth Validation  │
                    └───┬─────────┬───┘
                        │         │
                   ✓ valid     ✗ invalid
                        │         │
                        │     HTTP 403 (reject upgrade)
                        │
               ┌────────▼────────┐
               │ system.connected │
               └────────┬────────┘
                        │
          ┌─────────────▼──────────────┐
          │    Active Session          │
          │                            │
          │  chat.message → client     │
          │  chat.response ← server    │
          │  chat.typing ← server      │
          │  chat.quick_replies ← s    │
          │  chat.delivery_status ← s  │
          │  ping/pong (30s)           │
          └─────────────┬──────────────┘
                        │
              disconnect / heartbeat timeout
                        │
               ┌────────▼────────┐
               │  < 60 сек ?     │
               └───┬─────────┬───┘
                   │         │
              yes  │    no   │
                   │         │
        ┌──────────▼──┐  ┌───▼──────────┐
        │ system.     │  │ system.       │
        │ reconnect   │  │ connected     │
        │ + missed    │  │ (new session) │
        └─────────────┘  └──────────────┘
```

---

## WebSocket Close Codes

| Code | Название | Описание |
|------|----------|----------|
| 1000 | `NORMAL_CLOSE` | Корректное закрытие |
| 1001 | `GOING_AWAY` | Клиент/сервер уходит |
| 4000 | `AUTH_FAILED` | JWT невалиден |
| 4001 | `HEARTBEAT_TIMEOUT` | 3 пропущенных pong |
| 4002 | `RATE_LIMITED` | Превышен rate limit |
| 4003 | `TENANT_DISABLED` | Tenant деактивирован |
| 4004 | `CONVERSATION_EXPIRED` | Диалог истёк |
| 4005 | `SERVER_SHUTDOWN` | Graceful shutdown сервера |
| 4006 | `SESSION_CONFLICT` | Та же сессия уже подключена |

---

## Rate Limiting

| Лимит | Значение | Окошко |
|-------|----------|--------|
| Сообщений в минуту | 30 | 60 секунд (sliding) |
| Сообщений в день | 1000 | 24 часа |
| Размер сообщения | 10 000 символов | per message |
| Размер вложения | 10 MB | per file |
| Вложений в сообщении | 5 | per message |

При превышении — сервер отправляет `system.error` с кодом `RATE_LIMITED` и закрывает соединение с code `4002`.
