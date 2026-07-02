# AI-ядро Aether: Сравнительный анализ подходов

> **Aether** — универсальная AI-воронка «канал → AI-ядро → услуга → канал»
> Стек: Python (FastAPI) | Дата: 2026-06-25 | Stage 0

---

## Архитектурные подходы

### 1. OpenClaw как execution engine

Использование OpenClaw Gateway API / agent sessions как AI-движка.

**Концепция:** Запросы клиентов маршрутизируются через OpenClaw Gateway, который управляет agent session'ами. Каждый tenant получает изолированный session context. OpenClaw handles inference routing, tool use, и response generation.

```
Client → Aether Channels → OpenClaw Gateway → Agent Session → Inference (llama/vllm/ollama) → Response
```

### 2. Собственный lightweight inference router

Многодрайверный router поверх ai-ops паттерна, адаптированный для мультитенантности.

**Концепция:** Собственный FastAPI-сервис с драйверным слоем (как ai-ops), queue (Celery/RQ/Redis), tenant isolation, и orchestration логикой. Управляет локальными и удалёнными моделями.

```
Client → Aether Channels → AI Router (FastAPI) → [Driver: llama | vllm | ollama | openai | tgi] → Queue → Response
```

### 3. Внешние AI API + оркестрация

OpenAI, DeepSeek, Grok, Anthropic как inference backend + собственный orchestration layer.

**Концепция:** Минимальная инфраструктура. FastAPI-сервис с API client pool, fallback-логикой, rate limiting, cost tracking. Всё inference — у провайдеров.

```
Client → Aether Channels → Orchestration (FastAPI) → [OpenAI | DeepSeek | Grok | Anthropic] → Response
```

---

## Детальный анализ

### 1. Latency (p50 / p99)

| Метрика | OpenClaw Engine | Собственный Router | Внешние API |
|---|---|---|---|
| **p50 (idle)** | 200–500 ms | 50–200 ms | 300–800 ms |
| **p50 (100 concurrent)** | 400–800 ms | 100–300 ms | 500–1200 ms |
| **p50 (1K concurrent)** | 800–2000 ms | 200–500 ms | 1000–3000 ms |
| **p99 (idle)** | 1–3 sec | 500 ms–2 sec | 3–8 sec |
| **p99 (100 concurrent)** | 2–5 sec | 1–3 sec | 8–20 sec |
| **p99 (1K concurrent)** | 5–15 sec | 3–8 sec | 20–60 sec |
| **Streaming support** | ✅ (SSE) | ✅ (native) | ✅ (все поддерживают) |
| **First token latency** | 300–800 ms | 100–300 ms | 500–1500 ms |
| **TTFT под нагрузкой** | 1–3 sec | 300–800 ms | 2–5 sec |
| **Batch processing** | ❌ не родной | ✅ queue-native | ⚠️ rate-limited |

**Комментарий:** OpenClaw добавляет overhead Gateway → agent session → inference. Собственный router минимизирует hop-число. Внешние API имеют network roundtrip + provider queue. Для Aether, где воронка требует быстрой реакции (<2s), собственный router выигрывает. Внешние API приемлемы при streaming (TTFT важнее total time).

**Ключевой фактор:** При локальных моделях (llama/vllm на GPU) latency определяется GPU throughput, не network. OpenClaw overhead — 200-500ms добавочных. Внешние API — network hop + provider load = 300-1000ms добавочных.

---

### 2. Мультитенантность (изоляция данных)

| Критерий | OpenClaw Engine | Собственный Router | Внешние API |
|---|---|---|---|
| **Tenant isolation** | ⚠️ Session-based, не tenant-native | ✅ Native tenant context | ✅ API key per tenant |
| **Data separation** | ⚠️ Shared context window risk | ✅ Per-tenant vector store, DB schema | ✅ Data у провайдера, не наша |
| **Prompt isolation** | ⚠️ System prompt может «утечь» между session'ами | ✅ Hard-coded tenant boundaries | ✅ Изолировано по API key |
| **Rate limiting per tenant** | ⚠️ Нет native tenant rate limit | ✅ Per-tenant queue, configurable | ✅ Per API key (provider-side) |
| **Audit trail** | ✅ OpenClaw имеет audit log | ✅ Полностью custom | ✅ Логируем сами вызовы |
| **Data residency** | ✅ Локальные модели = данные в РФ | ✅ Локальные модели = данные в РФ | ❌ Данные у провайдера (США) |
| **GDPR / 152-ФЗ** | ✅ Если модели локальные | ✅ Если модели локальные | ❌ Трансграничная передача |
| **Tenant-specific models** | ⚠️ Сложно настроить | ✅ Per-tenant model routing | ✅ Per-tenant API key + model |

**Комментарий:** OpenClaw не был создан для мультитенантности — session isolation не равно tenant isolation. Собственный router строится с tenant context из коробки. Внешние API изолированы по API key, но создают проблемы с данными.

---

### 3. Стоимость per request

Цены на основе 2026 года. Локальные модели: 7B-70B параметр, GPU inference.

| Клиентов | OpenClaw (локальные модели) | Собственный Router (локальные) | Внешние API (GPT-4o-mini / DeepSeek) |
|---|---|---|---|
| **100** | $50–150/мес (infra) | $50–150/мес (infra) | $5–20/мес (API calls) |
| **1,000** | $150–400/мес (infra + scaling) | $150–400/мес (infra + scaling) | $50–200/мес (API calls) |
| **10,000** | $500–2,000/мес (infra + GPU) | $500–2,000/мес (infra + GPU) | $500–5,000/мес (API calls) |
| **Per request** | $0.001–0.005 | $0.001–0.005 | $0.003–0.015 |
| **GPU cost** | ~$200–800/мес (A100/H100) | ~$200–800/мес (A100/H100) | $0 (provider hosts) |
| **Network** | Локальная (мин.) | Локальная (мин.) | Cloud egress ($0.09/GB) |
| **Economy of scale** | ✅ Фиксированная GPU | ✅ Фиксированная GPU | ❌ Растёт линейно |

**Детальный расчёт (10,000 клиентов, ~500K запросов/мес):**

| Компонент | OpenClaw | Собственный Router | Внешние API |
|---|---|---|---|
| GPU inference (1× A100 80GB) | $600/мес | $600/мес | $0 |
| CPU/RAM infra | $150/мес | $150/мес | $100/мес (lightweight) |
| Network | $20/мес | $20/мес | $50/мес (egress) |
| API costs | $0 | $0 | $300–1500/мес |
| **Итого** | **~$770/мес** | **~$770/мес** | **~$450–1650/мес** |

**Комментарий:** При <5K клиентов внешние API дешевле. При >10K локальные модели выгоднее (фиксированная GPU). Break-even ~5K-10K клиентов. OpenClaw и собственный router имеют идентичную стоимость infra — разница в dev cost.

---

### 4. Приватность данных

| Критерий | OpenClaw (локальные) | Собственный Router (локальные) | Внешние API |
|---|---|---|---|
| **Данные покидают инфраструктуру?** | ❌ Нет | ❌ Нет | ✅ Да |
| **152-ФЗ compliance** | ✅ Полная | ✅ Полная | ❌ Трансграничная передача |
| **GDPR compliance** | ✅ Полная | ✅ Полная | ⚠️ DPA с провайдером |
| **Training data risk** | ❌ Данные не используются для training | ❌ Данные не используются для training | ⚠️ OpenAI: опционально. DeepSeek: unclear. Grok: unclear |
| **PII exposure** | ❌ Нет | ❌ Нет | ✅ Все PII уходит провайдеру |
| **Industry compliance** | ✅ Healthcare, finance, gov | ✅ Healthcare, finance, gov | ⚠️ Зависит от провайдера |
| **Data encryption at rest** | ✅ Контролируем сами | ✅ Контролируем сами | ⚠️ Доверяем провайдеру |
| **Right to erasure (GDPR)** | ✅ Удалить из своей БД | ✅ Удалить из своей БД | ❌ Не можем гарантировать у провайдера |
| **Audit / forensics** | ✅ Полный контроль | ✅ Полный контроль | ❌ Зависим от провайдера |

**Комментарий:** Для B2B SaaS в РФ/СНГ это критический фактор. 152-ФЗ требует хранения ПДн в РФ. Внешние API (OpenAI — США, DeepSeek — Китай, Grok — США) автоматически нарушают это без юридической обёртки. Локальные модели решают проблему полностью.

---

### 5. Масштабируемость (horizontal scaling)

| Критерий | OpenClaw Engine | Собственный Router | Внешние API |
|---|---|---|---|
| **Horizontal scaling** | ⚠️ Ограничено (single gateway) | ✅ Stateless router + stateful workers | ✅ Stateless, infinite |
| **Vertical scaling** | ✅ Больше GPU/RAM | ✅ Больше GPU/RAM | ✅ Provider handles |
| **Auto-scaling** | ⚠️ Manual | ✅ K8s HPA / Celery autoscale | ✅ Provider auto-scales |
| **Concurrent sessions** | ~500–2000 | ~2,000–10,000+ | ~50,000+ |
| **Load balancing** | ⚠️ Нет native LB | ✅ Nginx / K8s service | ✅ Provider LB |
| **Queue-based** | ❌ Not native | ✅ Redis/RabbitMQ/Celery | ✅ Provider queue |
| **Rate limiting** | ⚠️ IP-based | ✅ Per-tenant, configurable | ✅ Per API key |
| **Multi-region** | ⚠️ Сложно | ✅ Deploy per region | ✅ Provider multi-region |
| **Cold start** | ~1–3 sec | ~1–3 sec (model load) | ~instant |
| **Burst handling** | ⚠️ Ограничено session capacity | ✅ Queue absorbs bursts | ✅ Provider handles |

**Комментарий:** OpenClaw не создан для горизонтального масштабирования — это agent platform, не load balancer. Собственный router легко масштабируется через queue + worker pool. Внешние API — infinite scale, но с cost tradeoff.

---

### 6. Сложность поддержки

| Критерий | OpenClaw Engine | Собственный Router | Внешние API |
|---|---|---|---|
| **Dev effort (initial)** | ⚠️ Glue-код, не native fit | 🔥 300–500 часов (полный цикл) | ✅ 50–100 часов |
| **Dev effort (ongoing)** | ⚠️ Tracking OpenClaw changes | 🔥🔤 20–40 часов/мес | ✅ 5–10 часов/мес |
| **Model management** | ✅ OpenClaw handles | 🔥 Manual (download, update, quantize) | ✅ Provider handles |
| **Bug fixes** | ⚠️ Waiting for OpenClaw | 🔥 Наша ответственность | ✅ Provider fixes |
| **Monitoring** | ✅ OpenClaw dashboards | 🔤 Custom (Prometheus + Grafana) | ✅ Provider dashboards |
| **Security patches** | ⚠️ OpenClaw release cycle | 🔤 Мы сами | ✅ Provider handles |
| **Team skill req** | ✅ Знать OpenClaw (есть) | 🔥 ML ops + infra + backend | ✅ Backend + API integration |
| **Documentation** | ⚠️ OpenClaw docs | 🔤 Пишем сами | ✅ Provider docs |
| **Dependency risk** | ⚠️ OpenClaw roadmap | ✅ Полный контроль | 🔥🔤 Vendor lock-in |
| **Total maintenance** | **Средняя** | **Высокая** | **Низкая** |

---

## Сводная матрица оценок

### По критериям (1–10, 10 = лучше)

| Критерий | OpenClaw Engine | Собственный Router | Внешние API | Вес для Aether |
|---|---:|---:|---:|---|
| Latency (p50/p99) | 5 | 8 | 6 | 25% |
| Мультитенантность | 3 | 9 | 7 | 25% |
| Стоимость per request | 7 | 7 | 5 | 15% |
| Приватность данных | 9 | 9 | 2 | 20% |
| Масштабируемость | 4 | 8 | 10 | 5% |
| Сложность поддержки | 6 | 3 | 9 | 10% |
| **Взвешенный итог** | **6.0** | **7.4** | **5.1** | |

### Взвешивание для Aether

| Критерий | Вес | Обоснование |
|---|---|---|
| Latency | 25% | Воронка требует быстрой реакции, пользователь ждёт |
| Мультитенантность | 25% | White-label SaaS — это основа продукта |
| Приватность | 20% | B2B РФ/СНГ, 152-ФЗ, enterprise клиенты требуют локальные данные |
| Стоимость | 15% | Unit economics влияют на бизнес-модель |
| Масштабируемость | 5% | Важно, но не критично на early stage |
| Поддержка | 10% | Команда малая, time-to-market важен |

---

## Рекомендации по стадиям

### Stage 1 (MVP): Собственный lightweight inference router

**Обоснование:** Лучший баланс latency, мультитенантности и приватности. Переиспользует паттерны ai-ops (multi-driver архитектура). FastAPI — выбранный стек.

**Архитектура Stage 1:**

```
┌─────────────────────────────────────────────────────┐
│                    Aether Channels                   │
│           Telegram │ Web Widget │ Email              │
└────────────────────┬────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │ Channel     │
              │ Abstraction │
              │ Layer       │
              └──────┬──────┘
                     │
              ┌──────▼──────────────────────┐
              │      AI Router (FastAPI)     │
              │  ┌────────────────────────┐  │
              │  │  Tenant Context        │  │
              │  │  • tenant_id           │  │
              │  │  • model routing       │  │
              │  │  • rate limiting       │  │
              │  │  • cost tracking       │  │
              │  └────────┬───────────────┘  │
              │           │                  │
              │  ┌────────▼───────────────┐  │
              │  │  Inference Driver Pool │  │
              │  │  ┌────┐ ┌────┐ ┌────┐ │  │
              │  │  │LLa│ │vll│ │Oll│ │  │
              │  │  │ma │ │m  │ │ama│ │  │
              │  │  └────┘ └────┘ └────┘ │  │
              │  └────────────────────────┘  │
              │  ┌────────────────────────┐  │
              │  │  Queue (Redis + Celery)│  │
              │  │  • async jobs          │  │
              │  │  • retry logic         │  │
              │  │  • dead letter         │  │
              │  └────────────────────────┘  │
              └──────────────────────────────┘
                     │
              ┌──────▼──────┐
              │  Services   │
              │  Layer      │
              └─────────────┘
```

**Компоненты Stage 1:**

| Компонент | Технология | Зачем |
|---|---|---|
| API Router | FastAPI | Tenant context, routing, rate limiting |
| Driver Layer | Custom (ai-ops pattern) | Llama, vLLM, Ollama, OpenAI-compatible |
| Queue | Redis + Celery | Async inference, retry, DLQ |
| Model Store | Локальные GGUF/SAFETENSORS | Приватность, контроль |
| Vector Store | Qdrant (self-hosted) | Tenant memories, embeddings |
| Rate Limiting | Per-tenant token bucket | Fairness, abuse protection |
| Monitoring | Prometheus + Grafana | Metrics, alerting |
| Fallback | OpenAI API (optional) | When local GPU unavailable |

**Минимальный набор драйверов:**
1. `OllamaDriver` — dev/testing, лёгкие модели (7B)
2. `LlamaDriver` — production, GGUF quantized models
3. `OpenAIDriver` — fallback / high-quality queries (с бюджет-контролем)

---

### Stage 2 (Growth): Гибридная модель

**Обоснование:** Рост клиентов → GPU bottleneck. Добавляем внешние API как overflow + model-specific routing.

**Архитектура Stage 2:**

```
┌──────────────────────────────────────────────────────┐
│                   AI Router (FastAPI)                 │
│  ┌─────────────────┐    ┌──────────────────────────┐ │
│  │  Local Models   │    │  External API Pool       │ │
│  │  ┌────┐ ┌────┐ │    │  ┌──────┐ ┌──────┐      │ │
│  │  │LLa│ │vll│ │    │  │OpenAI│ │Deep- │      │ │
│  │  │ma │ │m  │ │    │  │      │ │Seek  │      │ │
│  │  └────┘ └────┘ │    │  └──────┘ └──────┘      │ │
│  └────────┬───────┘    │  ┌──────┐                │ │
│           │            │  │ Grok │                │ │
│  ┌────────▼───────┐    │  └──────┘                │ │
│  │  Smart Router  │    └──────────────────────────┘ │
│  │  • Priority    │                                 │
│  │  • Cost-aware  │                                 │
│  │  • Latency-    │                                 │
│  │    aware       │                                 │
│  └────────────────┘                                 │
└──────────────────────────────────────────────────────┘
```

**Smart Router логика:**
- Low priority / batch → внешние API (дёшево, async)
- High priority / PII → локальные модели (приватность, скорость)
- Cost optimization → cheapest available provider
- Fallback → если основной driver down, переключается

---

### Stage 3 (Scale): Full hybrid + fine-tuned models

**Target state architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      Aether Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 AI Orchestration Layer                  │    │
│  │                                                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │    │
│  │  │ Tenant Router│  │Smart Router  │  │  Model Zoo   │  │    │
│  │  │• Multi-ten.  │  │• Cost-aware  │  │• Base models │  │    │
│  │  │• Isolation   │  │• Latency-opt │  │• Fine-tuned  │  │    │
│  │  │• Rate limit  │  │• Fallback    │  │• LoRA adapters│   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │           Inference Tier                         │   │    │
│  │  │                                                  │   │    │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐ │   │    │
│  │  │  │ Local GPU  │  │ Local CPU  │  │ External   │ │   │    │
│  │  │  │ Cluster    │  │ Workers    │  │ API Pool   │ │   │    │
│  │  │  │(vLLM/TGI)  │  │(Ollama)   │  │(OpenAI etc)│ │   │    │
│  │  │  └────────────┘  └────────────┘  └────────────┘ │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │    │
│  │  │  Queue Layer │  │  Vector DB   │  │  Memory      │  │    │
│  │  │(Redis+Celery)│  │  (Qdrant)    │  │  (tenant ctx)│  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Stage 3 компоненты:**

| Компонент | Технология | Зачем |
|---|---|---|
| Tenant Router | Custom FastAPI | Multi-tenant isolation, per-tenant config |
| Smart Router | Custom routing engine | Cost, latency, privacy-aware model selection |
| Model Zoo | vLLM + LoRA | Base models + fine-tuned adapters per tenant |
| Inference Cluster | vLLM (GPU) + Ollama (CPU) | Multi-tier inference |
| External API Pool | OpenAI, DeepSeek, Grok, Anthropic | Overflow, specialized models, cost optimization |
| Queue | Redis + Celery + RabbitMQ | Async processing, DLQ, retry |
| Vector DB | Qdrant (K8s) | Tenant memories, semantic search |
| Memory | Redis + PostgreSQL | Tenant context, conversation history |
| Monitoring | Prometheus + Grafana + OpenTelemetry | Full observability |
| Fine-tuning | Axolotl / LLaMA-Factory | Per-tenant model customization |
| CI/CD for Models | Custom pipeline | Model versioning, A/B testing, rollback |

---

## TL;DR

| Подход | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| **OpenClaw Engine** | ❌ Не подходит | ❌ Не подходит | ❌ Не подходит |
| **Собственный Router** | ✅ **Выбор** | ✅ База | ✅ База + hybrid |
| **Внешние API** | ⚠️ Fallback | ✅ Overflow | ✅ Часть hybrid |

**Stage 1 (MVP):** Собственный lightweight inference router на FastAPI с драйверным слоем (ai-ops паттерн). Локальные модели для приватности. OpenAI API как опциональный fallback.

**Stage 3 (Target):** Гибридная архитектура — локальные GPU-кластеры + CPU workers + внешний API pool. Smart routing по стоимости/латентности/приватности. Fine-tuned модели per tenant. Full observability.

**Почему не OpenClaw:** Не создан для мультитенантности, нет native queue, overhead Gateway → session → inference. Отлично подходит как tool для разработки, но не как production AI engine для SaaS.

---

*Анализ составлен: июнь 2026*
*Основано на: ai-ops driver архитектура, stack-analysis.md (Python/FastAPI), channels-analysis.md*
