# Celery Tasks Specification — Aether Background Jobs

## Infrastructure

| Компонент | Development | Production |
|-----------|-------------|------------|
| Broker | Redis | RabbitMQ |
| Result Backend | Redis (expiry 1h) | Redis (expiry 1h) |
| Serializer | JSON | JSON |
| Task Tracking | `task_track_started = True` | `task_track_started = True` |
| Confirm Publish | False | True (RabbitMQ) |

## Queue Configuration

```python
# celery_app.py
task_queues = (
    Queue('default', routing_key='default', priority=10),
    Queue('ai', routing_key='ai', priority=10),
    Queue('long_running', routing_key='long_running', priority=10),
)

task_routes = {
    'app.tasks.notifications.*': {'queue': 'default'},
    'app.tasks.ai.*': {'queue': 'ai'},
    'app.tasks.maintenance.*': {'queue': 'long_running'},
}
```

## Worker Pool Sizing

| Worker | Concurrency | Queue | Notes |
|--------|------------|-------|-------|
| `default` | 4 | `default` | I/O bound (HTTP/SMTP) |
| `ai` | 2 | `ai` | GPU affinity, env `CUDA_VISIBLE_DEVICES=0` |
| `long_running` | 1 | `long_running` | Serial execution, high memory |

## Task Catalog

### 1. `process_intent`
| Field | Value |
|-------|-------|
| **Queue** | `ai` |
| **Priority** | 8 |
| **Timeout** | 30s (soft), 60s (hard) |
| **Retries** | 0 (retry on next message) |
| **Task** | `app.tasks.ai.process_intent` |

**Input:**
```json
{
  "message_id": "UUID",
  "conversation_id": "UUID",
  "organisation_id": "UUID",
  "text": "string",
  "language": "ru"
}
```

**Output:**
```json
{
  "message_id": "UUID",
  "intent_type": "string",
  "confidence": 0.92,
  "entities": {}
}
```

**Error handling:** Не ретраить — intent будет переклассифицирован на следующем сообщении.

---

### 2. `extract_entities`
| Field | Value |
|-------|-------|
| **Queue** | `ai` |
| **Priority** | 7 |
| **Timeout** | 15s (soft), 30s (hard) |
| **Retries** | 1 (60s backoff) |
| **Task** | `app.tasks.ai.extract_entities` |

**Input:**
```json
{
  "message_id": "UUID",
  "text": "string",
  "intent_type": "price_calculation",
  "language": "ru"
}
```

**Output:**
```json
{
  "entities": {
    "cargo_type": "уголь",
    "weight_tons": 60,
    "from": "Кузбасс",
    "to": "Находка"
  }
}
```

**Error handling:** 1 retry, затем fallback — entities=None (плагин запросит уточнение).

---

### 3. `invoke_plugin`
| Field | Value |
|-------|-------|
| **Queue** | `ai` |
| **Priority** | 6 |
| **Timeout** | 60s (soft), 120s (hard) |
| **Retries** | 2 (exponential backoff: 10s, 60s) |
| **Task** | `app.tasks.ai.invoke_plugin` |

**Input:**
```json
{
  "plugin_id": "UUID",
  "instance_id": "UUID",
  "organisation_id": "UUID",
  "conversation_id": "UUID",
  "message_id": "UUID",
  "intent": {},
  "context": {},
  "config": {}
}
```

**Output:**
```json
{
  "success": true,
  "response_text": "Стоимость перевозки: 125 000 ₽",
  "structured_data": {"price": 125000, "currency": "RUB"},
  "actions": [{"action_type": "send_message", "payload": {"text": "..."}}],
  "confidence": 0.95
}
```

**Error handling:** 2 retries, после failure → `EscalationPlugin.transfer_to_human()`.

---

### 4. `generate_embedding`
| Field | Value |
|-------|-------|
| **Queue** | `ai` |
| **Priority** | 5 |
| **Timeout** | 60s (soft), 120s (hard) |
| **Retries** | 3 (exponential: 10s, 30s, 90s) |
| **Task** | `app.tasks.ai.generate_embedding` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "knowledge_base_id": "UUID",
  "document_id": "UUID",
  "chunks": [{"index": 0, "text": "..."}, {"index": 1, "text": "..."}],
  "model": "bge-small"
}
```

**Output:**
```json
{
  "document_id": "UUID",
  "chunks_processed": 45,
  "embedding_model": "bge-small",
  "dimensions": 384
}
```

---

### 5. `batch_index_knowledge_base`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 4 |
| **Timeout** | 3600s (1 hour) |
| **Retries** | 1 (300s backoff) |
| **Task** | `app.tasks.ai.batch_index_knowledge_base` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "knowledge_base_id": "UUID",
  "file_paths": ["/data/.../faq.pdf", "/data/.../terms.docx"],
  "embedding_model": "bge-small"
}
```

**Output:**
```json
{
  "knowledge_base_id": "UUID",
  "files_processed": 5,
  "chunks_indexed": 342,
  "collection_name": "kb_{org_id}_v1",
  "duration_seconds": 245.3
}
```

**Error handling:** 1 retry. Dead letter queue: `long_running_dlq`.

---

### 6. `send_email`
| Field | Value |
|-------|-------|
| **Queue** | `default` |
| **Priority** | 8 |
| **Timeout** | 30s |
| **Retries** | 3 (60s, 180s, 600s backoff) |
| **Task** | `app.tasks.notifications.send_email` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "channel_id": "UUID",
  "to": "user@example.com",
  "subject": "Magic Link",
  "body_html": "<p>...</p>",
  "body_text": "...",
  "reply_to": null,
  "attachments": []
}
```

**Output:**
```json
{
  "message_id": "<UUID@aether.cloud>",
  "accepted": ["user@example.com"],
  "rejected": []
}
```

---

### 7. `send_telegram`
| Field | Value |
|-------|-------|
| **Queue** | `default` |
| **Priority** | 8 |
| **Timeout** | 15s |
| **Retries** | 3 (5s, 15s, 45s backoff) |
| **Task** | `app.tasks.notifications.send_telegram` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "channel_id": "UUID",
  "chat_id": "123456789",
  "text": "Ваша заявка принята!",
  "parse_mode": "HTML",
  "reply_markup": {"inline_keyboard": [[{"text": "Подробнее", "callback_data": "details"}]]}
}
```

**Output:**
```json
{
  "message_id": 12345,
  "chat_id": "123456789",
  "date": 1719360000
}
```

**Error handling:** Telegram rate limit: 429 → `Retry-After` header → exponential backoff.

---

### 8. `send_push_notification`
| Field | Value |
|-------|-------|
| **Queue** | `default` |
| **Priority** | 7 |
| **Timeout** | 10s |
| **Retries** | 2 (30s, 120s backoff) |
| **Task** | `app.tasks.notifications.send_push_notification` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "user_id": "UUID",
  "title": "Новое сообщение",
  "body": "Иван Петров: Сколько будет стоить...",
  "data": {"conversation_id": "UUID", "message_id": "UUID"}
}
```

**Output:**
```json
{
  "success": true,
  "tokens_sent": 1,
  "provider": "fcm"
}
```

---

### 9. `cleanup_expired_conversations`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 3 |
| **Timeout** | 600s |
| **Retries** | 0 |
| **Schedule** | Daily at 03:00 UTC |
| **Task** | `app.tasks.maintenance.cleanup_expired_conversations` |

**Input:**
```json
{
  "archive_before_days": 90,
  "batch_size": 1000
}
```

**Output:**
```json
{
  "conversations_archived": 1234,
  "messages_archived": 56789,
  "duration_seconds": 45.2
}
```

---

### 10. `archive_old_audit_logs`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 2 |
| **Timeout** | 1800s |
| **Retries** | 0 |
| **Schedule** | Weekly Sunday 02:00 UTC |
| **Task** | `app.tasks.maintenance.archive_old_audit_logs` |

**Input:**
```json
{
  "archive_before_days": 365,
  "batch_size": 5000
}
```

**Output:**
```json
{
  "rows_archived": 120000,
  "table": "audit_log_archive",
  "duration_seconds": 320.5
}
```

**Implementation:** `INSERT INTO audit_log_archive SELECT * FROM audit_log WHERE created_at < $1; DELETE FROM audit_log WHERE created_at < $1;` в транзакции с `batch_size`.

---

### 11. `generate_monthly_invoice`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 5 |
| **Timeout** | 300s |
| **Retries** | 2 (300s backoff) |
| **Schedule** | Monthly 1st 00:00 UTC |
| **Task** | `app.tasks.billing.generate_monthly_invoice` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "period_start": "2026-06-01T00:00:00Z",
  "period_end": "2026-07-01T00:00:00Z"
}
```

**Output:**
```json
{
  "invoice_id": "UUID",
  "amount_rub": 2990,
  "status": "pending_payment",
  "line_items": [
    {"description": "Starter Plan — June 2026", "amount": 2990}
  ]
}
```

---

### 12. `health_check_drivers`
| Field | Value |
|-------|-------|
| **Queue** | `default` |
| **Priority** | 9 (highest) |
| **Timeout** | 30s |
| **Retries** | 0 |
| **Schedule** | Every 5 minutes |
| **Task** | `app.tasks.ai.health_check_drivers` |

**Input:**
```json
{}
```

**Output:**
```json
{
  "drivers": {
    "ollama_local": {"status": "online", "latency_ms": 45},
    "openai_gpt4o": {"status": "online", "latency_ms": 320},
    "llamacpp_qwen": {"status": "online", "latency_ms": 25}
  },
  "timestamp": "2026-06-25T05:55:00Z"
}
```

**Error handling:** Обновляет `ai_models.driver_status`. Alert если `offline` > 5 минут.

---

### 13. `reindex_qdrant`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 4 |
| **Timeout** | 7200s (2 hours) |
| **Retries** | 1 (3600s backoff) |
| **Task** | `app.tasks.ai.reindex_qdrant` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "knowledge_base_id": "UUID",
  "old_model": "bge-small",
  "new_model": "bge-large",
  "old_collection": "kb_{org_id}_v1",
  "new_collection": "kb_{org_id}_v2"
}
```

**Output:**
```json
{
  "knowledge_base_id": "UUID",
  "documents_reindexed": 500,
  "chunks_reindexed": 12500,
  "new_dimensions": 1024,
  "alias_switched": true,
  "duration_seconds": 1845.2
}
```

**Implementation:**
1. Создать `{new_collection}` в Qdrant с новыми dimensions
2. Бачтать документы из source, генерировать embedding новой моделью
3. Индексировать в новую коллекцию
4. Атомарный swap: `update_collection_alias(old_collection, new_collection)`
5. Удалить старую коллекцию через 24h (grace period)

---

### 14. `provision_tenant`
| Field | Value |
|-------|-------|
| **Queue** | `long_running` |
| **Priority** | 7 |
| **Timeout** | 120s |
| **Retries** | 1 (60s backoff) |
| **Task** | `app.tasks.tenant.provision_tenant` |

**Input:**
```json
{
  "organisation_id": "UUID",
  "tenant_config": {
    "plan_slug": "starter",
    "channels": [{"type": "web_widget", "name": "Default Widget"}]
  }
}
```

**Output:**
```json
{
  "organisation_id": "UUID",
  "tenant_id": "UUID",
  "subscription_id": "UUID",
  "default_channel_id": "UUID",
  "provisioned_at": "2026-06-25T05:55:00Z"
}
```

**Implementation:**
1. Создать `tenant_configs` запись
2. Создать `subscription` (trial 14 дней)
3. `tenant_migration_runner.apply_rls_policies(organisation_id=...)`
4. Создать default WebWidget channel
5. Запустить `on_install()` для всех плагинов enabled по умолчанию

---

## Celery Beat Schedule

```python
# celery_schedule.py
from celery.schedules import crontab

beat_schedule = {
    'health-check-drivers': {
        'task': 'app.tasks.ai.health_check_drivers',
        'schedule': 300.0,  # every 5 minutes
    },
    'cleanup-expired-conversations': {
        'task': 'app.tasks.maintenance.cleanup_expired_conversations',
        'schedule': crontab(hour=3, minute=0),  # daily 03:00 UTC
    },
    'archive-audit-logs': {
        'task': 'app.tasks.maintenance.archive_old_audit_logs',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # weekly Sunday
    },
    'generate-invoices': {
        'task': 'app.tasks.billing.generate_monthly_invoice',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),  # monthly 1st
    },
}
```

## Graceful Shutdown

```python
# Worker signal handlers
@worker_shutdown.connect
def graceful_shutdown(sender, **kwargs):
    """SIGTERM: завершить текущие задачи, не брать новые."""
    logger.info("Worker shutting down...")
    sender.control.cancel_consumer(sender.queues)

# Soft timeout: SIGUSR1 → SoftTimeLimitExceeded (можно поймать)
# Hard timeout: SIGKILL (нельзя поймать)
task_soft_time_limit = None  # per-task override
task_time_limit = None       # per-task override
```

## Monitoring

### Metrics (exported via Prometheus / Flower)

| Metric | Type | Labels |
|--------|------|--------|
| `celery_task_duration_seconds` | Histogram | task_name, queue |
| `celery_task_success_total` | Counter | task_name |
| `celery_task_failure_total` | Counter | task_name, error_type |
| `celery_task_retry_total` | Counter | task_name |
| `celery_queue_length` | Gauge | queue |
| `celery_worker_status` | Gauge | worker_name |

### Flower Dashboard

```
URL: http://{host}:5555
Auth: basic auth (admin / env FLOWER_PASSWORD)

Endpoints:
  GET /api/tasks           — список задач
  GET /api/task/types      — типы задач
  GET /api/workers         — статус worker'ов
  GET /api/queues/length   — длина очередей
```

## Error Handling Strategy

| Scenario | Policy |
|----------|--------|
| Transient failure (network, timeout) | Retry с exponential backoff |
| Permanent failure (validation, auth) | Dead letter queue + alert |
| All retries exhausted | Dead letter queue `{queue}_dlq` + error log |
| Queue overflow (>1000 pending) | Circuit breaker: reject new tasks, alert |
| Worker OOM | Supervisor restart, no task loss (Redis persist) |
| Redis down | Tasks queued but not consumed. Resume on reconnect. |
