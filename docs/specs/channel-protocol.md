# Спецификация канального протокола Aether

## 1. NormalizedMessage

NormalizedMessage — это стандартная структура сообщения, используемая во всех каналах. Все входящие сообщения преобразуются в эту структуру для унификации.

### Структура

```json
{
  "id": "string",
  "tenant_id": "string",
  "channel": "string",
  "text": "string",
  "attachments": [
    {
      "type": "string",
      "url": "string",
      "name": "string",
      "size": "number",
      "mimeType": "string"
    }
  ],
  "metadata": {
    "sender_id": "string",
    "sender_name": "string",
    "timestamp": "string",
    "thread_id": "string",
    "source": "string",
    "extra": "object"
  }
}
```

### Поля

| Поле | Тип | Описание |
|--------|------|----------|
| `id` | string | Уникальный идентификатор сообщения |
| `tenant_id` | string | Идентификатор клиента (tenant) |
| `channel` | string | Название канала (telegram, web_widget, email) |
| `text` | string | Текст сообщения |
| `attachments` | array | Список вложений |
| `metadata` | object | Дополнительные метаданные |

#### Attachment

```json
{
  "type": "string",
  "url": "string",
  "name": "string",
  "size": "number",
  "mimeType": "string"
}
```

| Поле | Тип | Описание |
|------|------|----------|
| `type` | string | Тип вложения: `image`, `file`, `video`, `audio` |
| `url` | string | URL-адрес вложения |
| `name` | string | Имя файла |
| `size` | number | Размер файла в байтах |
| `mimeType` | string | MIME-тип файла |

#### Metadata

```json
{
  "sender_id": "string",
  "sender_name": "string",
  "timestamp": "string",
  "thread_id": "string",
  "source": "string",
  "extra": "object"
}
```

| Поле | Тип | Описание |
|------|------|----------|
| `sender_id` | string | Идентификатор отправителя |
| `sender_name` | string | Имя отправителя |
| `timestamp` | string | Временная метка |
| `thread_id` | string | Идентификатор потока (для чатов) |
| `source` | string | Источник сообщения |
| `extra` | object | Дополнительные данные |

### Пример

```json
{
  "id": "msg_001",
  "tenant_id": "tenant_123",
  "channel": "telegram",
  "text": "Привет!",
  "attachments": [
    {
      "type": "image",
      "url": "https://example.com/image.jpg",
      "name": "image.jpg",
      "size": 102400,
      "mimeType": "image/jpeg"
    }
  ],
  "metadata": {
    "sender_id": "user_456",
    "sender_name": "Иван Петров",
    "timestamp": "2026-07-02T10:00:00Z",
    "thread_id": "thread_789",
    "source": "telegram_bot"
  }
}
```

## 2. DeliveryResult

DeliveryResult описывает результат доставки сообщения.

### Структура

```json
{
  "status": "string",
  "message_id": "string",
  "retry_count": "number",
  "error": "string"
}
```

### Поля

| Поле | Тип | Описание |
|------|------|----------|
| `status` | string | Статус доставки (`delivered`, `failed`, `pending`, `retry`) |
| `message_id` | string | ID сообщения |
| `retry_count` | number | Количество попыток |
| `error` | string | Описание ошибки (если есть) |

### Политика повтора

- Максимум 3 попытки
- Интервал между попытками: экспоненциальный (1, 2, 4 секунды)
- После третьей попытки — сообщение помечается как не доставленное

## 3. ChannelCapability

ChannelCapability описывает возможности каждого канала.

```json
{
  "channel": "string",
  "capabilities": {
    "text": "boolean",
    "images": "boolean",
    "files": "boolean",
    "buttons": "boolean",
    "quick_replies": "boolean",
    "voice": "boolean",
    "video": "boolean"
  }
}
```

### Поддерживаемые каналы

| Канал | text | images | files | buttons | quick_replies | voice | video |
|-------|------|-------|-------|---------|------------------|--------|-------|
| telegram | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| web_widget | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| email | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

## 4. Протоколы каналов

### 4.1 Telegram

#### Webhook формат

Все сообщения от Telegram приходят через webhook в формате JSON.

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "first_name": "Иван",
      "last_name": "Петров",
      "username": "ivan_petrov"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "date": 1441645440,
    "text": "Привет!"
  }
}
```

#### Команды

- `/start` — активация бота
- `/help` — показ помощи
- `/status` — статус

#### Inline клавиатуры

Telegram поддерживает inline клавиатуры с кнопками и callback queries.

#### Обработка медиа

Изображения, файлы и видео передаются через `photo`, `document`, `video`.

### 4.2 Web Widget

#### WebSocket протокол

WebSocket протокол описан в `/home/den/aether/docs/specs/websocket-protocol.md`.

#### Message Flow

1. Клиент устанавливает WebSocket соединение
2. Бот отправляет `channel_init` сообщение с `tenant_id` и `channel`
3. Пользователь отправляет сообщение через WebSocket
4. Сервер преобразует сообщение в `NormalizedMessage` и передает в core

#### Пример сообщения

```json
{
  "type": "message",
  "payload": {
    "tenant_id": "tenant_123",
    "channel": "web_widget",
    "text": "Привет!",
    "metadata": {
      "sender_id": "user_456",
      "sender_name": "Иван Петров"
    }
  }
}
```

### 4.3 Email

#### SMTP отправка

- Все исходящие сообщения отправляются через SMTP
- Конфигурация хранится в БД: `channel_configs`

#### IMAP получение

- Входящие сообщения обрабатываются через IMAP
- Email преобразуется в `NormalizedMessage` с `channel` = `email`

#### Преобразование Email в NormalizedMessage

```json
{
  "id": "email_001",
  "tenant_id": "tenant_123",
  "channel": "email",
  "text": "Текст письма",
  "attachments": [
    {
      "type": "file",
      "url": "https://example.com/attachment.pdf",
      "name": "attachment.pdf",
      "size": 102400,
      "mimeType": "application/pdf"
    }
  ],
  "metadata": {
    "sender_id": "sender@example.com",
    "sender_name": "Иван Петров",
    "timestamp": "2026-07-02T10:00:00Z",
    "thread_id": "thread_789",
    "source": "imap"
  }
}
```

## 5. Безопасность каналов

### 5.1 Webhook безопасности Telegram

Для проверки подлинности webhook от Telegram используется подпись.

#### Подпись

- Подпись генерируется из `content` сообщения с помощью секретного ключа
- Ключ хранится в `channel_configs`

#### Пример проверки

```python
import hashlib
import hmac

def verify_telegram_signature(secret, content):
    expected = hmac.new(secret.encode(), content.encode(), hashlib.sha256).hexdigest()
    return expected == signature
```

### 5.2 JWT для Web Widget

Для авторизации WebSocket соединений используется JWT токен.

#### Генерация токена

```python
import jwt

token = jwt.encode({
  "tenant_id": "tenant_123",
  "channel": "web_widget",
  "exp": datetime.utcnow() + timedelta(hours=1)
}, SECRET_KEY, algorithm="HS256")
```

#### Проверка токена

```python
try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    # Валидный токен
except jwt.ExpiredSignatureError:
    # Токен истек
except jwt.InvalidTokenError:
    # Невалидный токен
```

## 6. Acknowledgement и retry flow

### 6.1 Acknowledgement

- При получении сообщения от канала, система отвечает `ack` с `message_id`
- Это гарантирует, что сообщение было принято

### 6.2 Retry flow

- При возникновении ошибки доставки, система пытается повторить отправку
- Максимум 3 попытки
- Если все попытки провалились — сообщение отправляется в очередь ошибок

## 7. Схема БД

### channels table

| Поле | Тип | Описание |
|-------|------|--------|
| id | UUID | Уникальный ID |
| name | string | Название канала (telegram, web_widget, email) |
| type | string | Тип канала (bot, widget, smtp, imap) |
| created_at | datetime | Дата создания |
| updated_at | datetime | Дата обновления |

### channel_configs

| Поле | Тип | Описание |
|-------|------|--------|
| id | UUID | Уникальный ID |
| channel_id | UUID | Ссылка на `channels` |
| config | JSON | Конфигурация для канала |
| created_at | datetime | Дата создания |
| updated_at | datetime | Дата обновления |

## 8. Обработка ошибок

### 8.1 Невалидные сообщения

- Все не валидные сообщения от канала отбрасываются
- Логируются в систему мониторинга

### 8.2 Неподдерживаемые типы

- Если тип сообщения не поддерживается, система возвращает ошибку
- Сообщение помечается как "не поддерживаемый тип"

### 8.3 Rate limits

- Каждый канал имеет свои лимиты
- Превышение — возвращает ошибку с кодом `429 Too Many Requests`
- Лимиты могут быть настроены через `channel_configs`
