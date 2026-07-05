# 🤖 ProcessBot — AI Process Generation Service

**Version:** 1.0.0
**Created:** 2026-07-05
**Status:** Draft — pending review
**Dependencies:** Aether AI Router (✅ exists), Vela Process API (✅ exists)

---

## 1. Overview

ProcessBot — платный AI-сервис, генерирующий ProcessDefinition (BPMN-схему) из:
1. **Изображений** (фото доски, скриншоты схем, отсканированные документы)
2. **Текстового описания** (NL → процесс)
3. **Событий из Logicore** (поток данных → паттерны → процесс)

ProcessBot — VIP-фича экосистемы Aether. Каждый вызов тарифицируется через streaming billing.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  VELA FLOWEDITOR UI                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  [Create Process] [Upload Photo] [Describe in Text]        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  VELA BACKEND — ProcessBot Router                                │
│  POST /api/process-definitions/generate                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Input validation (file size, mime type, text length)     │   │
│  │  Tenant auth + usage check (billing quota)                │   │
│  │  Dispatch to pipeline based on input_type                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
           ┌───────▼──────┐   ┌──────▼──────┐
           │  Vision       │   │  NLP         │
           │  Pipeline     │   │  Pipeline    │
           └───────┬──────┘   └──────┬──────┘
                   │                 │
           ┌───────▼─────────────────▼──────┐
           │     AETHER AI ROUTER           │
           │  ┌────────────────────────┐    │
           │  │ Model Selection:        │    │
           │  │  Local: Qwen 35B (free) │    │
           │  │  Cloud: DeepSeek V4 Pro │    │
           │  │  Cloud: GPT-4V (fallbk) │    │
           │  └────────────────────────┘    │
           └───────────────┬───────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  PROCESSBOT — Output Post-Processing                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  1. Parse AI response → ProcessDefinition (blocks+conns)   │  │
│  │  2. Validate against BlockType catalog                     │  │
│  │  3. Auto-layout: position blocks on canvas                 │  │
│  │  4. Generate suggested pages (PageBuilder layout)          │  │
│  │  5. Return to FlowEditor for human validation             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. API Specification

### 3.1 POST /api/process-definitions/generate

Generate a ProcessDefinition from image or text.

#### Request

```json
{
  "input_type": "image",
  "title": "Процесс приёмки груза",
  "files": [
    {
      "filename": "board-photo.jpg",
      "mime_type": "image/jpeg",
      "data": "<base64-encoded>"
    }
  ],
  "text": null,
  "options": {
    "model_preference": "auto",
    "auto_layout": true,
    "generate_pages": true,
    "language": "ru"
  }
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input_type` | enum | ✅ | `"image"`, `"text"`, `"events"` |
| `title` | string | ✅ | Process name |
| `files` | array | if `image` | Max 5 images, ≤10MB each |
| `text` | string | if `text` | Natural language description, ≤5000 chars |
| `options.model_preference` | enum | ❌ | `"auto"`, `"local"`, `"cloud"` |
| `options.auto_layout` | bool | ❌ | Auto-position blocks (default: true) |
| `options.generate_pages` | bool | ❌ | Generate PageBuilder layouts (default: true) |
| `options.language` | string | ❌ | Output language (default: `"ru"`) |

#### Response (200)

```json
{
  "status": "success",
  "process_definition": {
    "name": "Процесс приёмки груза",
    "slug": "cargo-acceptance",
    "blocks": [
      {
        "key": "b1",
        "block_type": "start",
        "label": "Поступление груза",
        "position_x": 100,
        "position_y": 50,
        "config": {
          "trigger": "document_arrival"
        }
      },
      {
        "key": "b2",
        "block_type": "task",
        "label": "Проверка накладной",
        "position_x": 400,
        "position_y": 50,
        "config": {
          "assignee_role": "warehouse_manager"
        }
      },
      {
        "key": "b3",
        "block_type": "condition",
        "label": "Расхождения?",
        "position_x": 700,
        "position_y": 50,
        "config": {
          "branches": [
            {"condition": "discrepancies == true", "label": "Есть расхождения"},
            {"condition": "discrepancies == false", "label": "Всё верно"}
          ]
        }
      }
    ],
    "connections": [
      {"source": "b1", "target": "b2", "source_port": "out", "target_port": "in"},
      {"source": "b2", "target": "b3", "source_port": "out", "target_port": "in"}
    ],
    "suggested_pages": [
      {
        "route": "/cargo/dashboard",
        "title": "Панель управления",
        "layout_config": {...}
      }
    ]
  },
  "billing": {
    "credits_used": 50,
    "model_used": "deepseek-v4-pro",
    "tokens": {
      "input": 1250,
      "output": 3400
    }
  },
  "warnings": [
    "Block 'Отправка уведомления' type not matched — using generic 'task' instead"
  ]
}
```

**Response (402 — Payment Required):**

```json
{
  "status": "error",
  "error": "insufficient_credits",
  "message": "Недостаточно кредитов. Требуется: 50, доступно: 12",
  "upgrade_url": "/billing/upgrade"
}
```

**Response (422 — Too Large):**

```json
{
  "status": "error",
  "error": "image_too_complex",
  "message": "Схема содержит более 50 блоков. Упростите или разбейте на подпроцессы.",
  "max_blocks": 50,
  "detected_blocks": 67
}
```

---

### 3.2 GET /api/process-definitions/generate/status/{task_id}

Check async generation status (long-running generations).

```json
{
  "task_id": "uuid",
  "status": "processing",
  "progress": {
    "stage": "vision",
    "percentage": 60,
    "message": "Распознаю связи между блоками..."
  }
}
```

---

## 4. Vision Pipeline (Image → ProcessDefinition)

### 4.1 Pipeline Stages

```
Stage 1: PREPROCESS
  ├── Validate image (size, format, resolution)
  ├── Resize if needed (max 2048px longest edge)
  └── Convert to PNG for consistency

Stage 2: VISION ANALYSIS (AI Router call)
  ├── Send image to vision-capable model
  ├── Prompt: "Extract process diagram. Identify:
  │   - Boxes/Rectangles → process blocks (type, label, position)
  │   - Arrows → connections (direction, label)
  │   - Groupings → nesting (parent/child)
  │   - Notes → block descriptions
  │   Output as JSON following OpenAPI schema."
  └── Parse response → raw ProcessDefinition

Stage 3: BLOCK MATCHING
  ├── For each detected block: match label/keyword → BlockType from catalog
  ├── Fuzzy matching: "Проверить" → "task", "Согласовать" → "approval"
  ├── Unmatched → generic "task" type + warning
  └── Validate: max 50 blocks, no orphan connections

Stage 4: AUTO-LAYOUT
  ├── Compute optimal canvas positions (Dagre layout algorithm)
  ├── Assign position_x, position_y, width, height
  ├── Order by flow direction (top→bottom or left→right)
  └── Nest blocks (parent_block_id for containers)

Stage 5: PAGE GENERATION
  ├── Analyze block types → suggest page structure
  ├── List blocks → table pages
  ├── Form blocks → form pages
  ├── Dashboard blocks → dashboard pages
  └── Generate layout_config for vue-grid-layout
```

### 4.2 Vision Prompt Template

```
Ты — AI-ассистент для распознавания бизнес-процессов.
Проанализируй изображение и извлеки диаграмму процесса.

Инструкции:
1. Найди все прямоугольники/блоки. Каждый блок — шаг процесса.
2. Найди все стрелки/линии. Каждая стрелка — связь между блоками.
3. Прочитай текст в каждом блоке и на стрелках.
4. Определи тип каждого блока:
   - "start" — начало процесса (зелёный/овальный)
   - "end" — завершение (красный/овальный)
   - "task" — действие (синий/прямоугольный)
   - "condition" — условие/развилка (ромб)
   - "form" — форма ввода (с полями)
   - "notification" — уведомление (конверт/колокольчик)
   - "document" — генерация документа (иконка файла)
5. Сгруппируй вложенные блоки (parent/child).

Формат ответа — JSON:
{
  "blocks": [
    {
      "key": "b1",
      "block_type": "start",
      "label": "Начало",
      "description": "",
      "config": {},
      "children": []
    }
  ],
  "connections": [
    {
      "source_key": "b1",
      "target_key": "b2",
      "label": "",
      "condition": null
    }
  ]
}

Ответь ТОЛЬКО JSON, без пояснений.
```

### 4.3 Block Type Matching Table

| Vision Label Keywords | Block Type | Category |
|----------------------|------------|----------|
| начало, start, старт | `start` | flow |
| конец, end, финиш, завершение | `end` | flow |
| проверить, check, verify, инспекция | `task` | action |
| согласовать, approve, утвердить | `approval` | action |
| создать, generate, сформировать | `document` | action |
| заполнить, form, анкета, заявка | `form` | data |
| если, condition, проверка, ветвление | `condition` | flow |
| уведомить, notify, email, сообщить | `notification` | action |
| ждать, wait, ожидание, задержка | `wait` | flow |
| данные, data, таблица, список | `data_table` | data |
| отчёт, report, аналитика | `report` | analytics |

---

## 5. NLP Pipeline (Text → ProcessDefinition)

### 5.1 Pipeline Stages

```
Stage 1: PARSE
  ├── Send text to LLM with structured prompt
  ├── Extract actors, steps, conditions, outcomes
  └── Map to block types from catalog

Stage 2: ENRICH
  ├── Suggest missing steps (LLM completion)
  ├── Add default configurations
  └── Flag ambiguities for human review

Stage 3: BUILD
  ├── Build ProcessDefinition JSON
  ├── Auto-layout (Dagre)
  └── Generate pages
```

### 5.2 NLP Prompt Template

```
Ты — AI-ассистент для создания бизнес-процессов.
Опиши процесс по следующему тексту. Используй блоки из каталога.

Каталог доступных типов блоков:
[BCT_CATALOG]

Текст описания процесса:
"""
$USER_TEXT
"""

Выдели:
1. Этапы процесса (последовательно)
2. Условия и развилки
3. Исполнителей (роли)
4. Документы (что создаётся/проверяется)
5. Уведомления (кому и когда)

Ответь JSON по схеме ProcessDefinition, без пояснений.
```

---

## 6. Billing Integration

### 6.1 Cost Model

| Input Type | Base Credits | Per-Block Surcharge | Model Used |
|-----------|-------------|---------------------|------------|
| Image (Vision) | 50 | +5/block over 10 | DeepSeek V4 Pro / GPT-4V |
| Text (NLP) | 30 | +3/block over 10 | Qwen 35B / DeepSeek |
| Events (mining) | 100/mo | included | Qwen 35B |

### 6.2 Streaming Billing Middleware

ProcessBot uses Aether's `streaming_billing.py`:

```python
# Vela backend calls Aether billing middleware

async def generate_process_definition(request: GenerateRequest, tenant: TenantContext):
    billing = BillingMiddleware(tenant)

    # Check credits
    estimated_cost = estimate_cost(request)
    if not await billing.check_credits(estimated_cost):
        raise InsufficientCreditsError(estimated_cost)

    # Execute generation with streaming tracking
    async with billing.track_stream("processbot_generate") as tracker:
        result = await processbot_pipeline(request)
        tracker.record_tokens(result.tokens_input, result.tokens_output)

    # Deduct credits
    await billing.deduct(result.actual_cost)

    return result
```

### 6.3 Billing Events (Audit Log)

```json
{
  "event": "processbot.generate",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "input_type": "image",
  "model": "deepseek-v4-pro",
  "credits": 50,
  "tokens_input": 1250,
  "tokens_output": 3400,
  "blocks_generated": 12,
  "duration_ms": 2340,
  "timestamp": "2026-07-05T03:15:00Z"
}
```

---

## 7. Error Handling & Edge Cases

| Scenario | HTTP | Response |
|----------|------|----------|
| Image too complex (>50 blocks) | 422 | Suggest splitting into subprocesses |
| No blocks detected | 422 | "Не удалось распознать блоки. Попробуйте более чёткое изображение." |
| All blocks unrecognized types | 200 + warnings | All → generic "task" + warning |
| OCR failed (unreadable text) | 200 + warnings | Blocks placed, labels empty |
| Credits insufficient | 402 | Required vs available credits |
| Model timeout (30s) | 503 | "AI-модель не отвечает. Попробуйте позже." |
| Model error | 503 | Fallback to alternative model |
| File too large (>10MB) | 413 | Max file size |
| Unsupported format | 415 | Supported: JPG, PNG, WEBP |
| Rate limited | 429 | Retry-After header |

---

## 8. Security

- **File scanning:** ClamAV on uploaded images (optional, configurable)
- **Max file size:** 10MB per image, 5 images per request
- **Rate limiting:** 10 generations/minute per tenant (pro), 60/m (enterprise)
- **Content filtering:** NSFW filter on images (optional)
- **PII detection:** Strip PII from OCR text before processing
- **Audit trail:** All generations logged to AuditLog table

---

## 9. Implementation Plan

### Phase 1: Core Vision Pipeline (Week 1)

```
Day 1-2: ProcessBot Vision Service
  □ POST /api/process-definitions/generate endpoint
  □ Image validation, preprocessing
  □ AI Router integration (call Aether)
  □ Vision prompt template
  □ Response parser (AI JSON → ProcessDefinition)

Day 3: Block Matching + Auto-Layout
  □ BlockType catalog fuzzy matching
  □ Dagre auto-layout implementation
  □ Position calculation
  □ Unmatched block handling (→ generic task)

Day 4: FlowEditor Integration
  □ Upload UI in FlowEditor
  □ Preview recognized process
  □ Human validation/edit flow
  □ Save to ProcessDefinition API

Day 5: Billing + Polish
  □ Billing middleware integration
  □ Credit check + deduction
  □ Error handling (all 4xx/5xx cases)
  □ Success/failure analytics
```

### Phase 2: NLP Pipeline (Week 2)

```
Day 1-2: NLP Service
  □ POST /api/process-definitions/generate (text input)
  □ NLP prompt template with catalog injection
  □ Response parser
  □ Ambiguity detection + suggestions

Day 3-4: Enhanced Features
  □ Multi-step generation (follow-up questions)
  □ "Generate missing steps" suggestion
  □ Page auto-generation
  □ Template selection
```

### Phase 3: Events Pipeline (Week 3-4)

```
Day 1-3: Logicore Event Connector
  □ Logicore webhook → Vela event stream
  □ Event aggregation + pattern detection
  □ Process candidate proposals

Day 4-5: Autonomous Mode
  □ Passive monitoring (cron-based)
  □ Process improvement suggestions
  □ A/B testing: current vs proposed process
```

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Vision accuracy (block detection) | ≥85% | Manual verification on 50 sample images |
| Vision accuracy (connections) | ≥80% | Manual verification |
| NLP accuracy (process completeness) | ≥90% | User acceptance rate |
| Generation time (image) | <5s | p95 latency |
| Generation time (text) | <3s | p95 latency |
| User edit rate (corrections needed) | <20% | Blocks modified after generation |
| Billing conversion (free→pro) | ≥15% | ProcessBot trial → subscription |

---

## Appendix A: Dagre Auto-Layout Algorithm

```python
async def auto_layout_blocks(
    blocks: list[ProcessBlock],
    connections: list[ProcessConnection]
) -> None:
    """Auto-position blocks using layered graph layout (Dagre-inspired)."""

    # 1. Build adjacency graph
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)

    for conn in connections:
        graph[conn.source_block_id].append(conn.target_block_id)
        in_degree[conn.target_block_id] += 1

    # 2. Topological sort → layers
    layers: list[list[str]] = []
    queue = [b.key for b in blocks if in_degree[b.key] == 0]

    while queue:
        layers.append(queue)
        next_queue = []
        for node in queue:
            for child in graph[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    next_queue.append(child)
        queue = next_queue

    # 3. Assign positions
    LAYER_GAP_X = 300
    BLOCK_GAP_Y = 120

    for layer_idx, layer in enumerate(layers):
        x = 100 + layer_idx * LAYER_GAP_X
        total_height = len(layer) * BLOCK_GAP_Y
        start_y = 50 + (600 - total_height) // 2  # center vertically

        for block_idx, block_key in enumerate(layer):
            block = next(b for b in blocks if b.key == block_key)
            block.position_x = x
            block.position_y = start_y + block_idx * BLOCK_GAP_Y
            block.width = 200
            block.height = 80
```
