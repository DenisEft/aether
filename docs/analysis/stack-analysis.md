# Stack Analysis для Aether SaaS

> **Aether** — универсальная AI-воронка «канал → AI-ядро → услуга → канал»
> Дата: 2026-06-25 | Статус: Анализ для принятия архитектурного решения

---

## 1. Производительность под нагрузкой

| Критерий | Python (FastAPI + Uvicorn) | Go (Gin/Fiber) | Node.js (Express/Fastify) |
|---|---|---|---|
| **HTTP RPS (baseline)** | ~5 000–15 000 (1 воркер) | ~50 000–200 000 | ~20 000–60 000 (Fastify) |
| **HTTP RPS (оптимизировано)** | ~30 000–50 000 (worker pool) | ~300 000+ (auto-tuned) | ~80 000–120 000 (cluster) |
| **WebSocket connections** | ~10 000–15 000/процесс | ~50 000–100 000/процесс | ~30 000–50 000/процесс |
| **Streaming (SSE)** | ✅ Native async generators | ✅ io.Writer streams | ✅ ReadableStream / SSE |
| **CPU-bound** | ❌ GIL bottleneck | ✅ True goroutines, full CPU | ❌ Single-threaded event loop |
| **I/O-bound** | ✅ async/await (Starlette) | ✅ goroutine multiplexing | ✅ Native event loop |
| **Tail latency (p99)** | ~50–200 ms (переменная) | ~2–10 ms (стабильная) | ~10–50 ms |
| **Подходит для Aether?** | ✅ Достаточно для SaaS-воронки | ✅ Избыточно, но надёжно | ✅ Достаточно при Fastify |

### Ключевые наблюдения

- **FastAPI** — в реальных SaaS-нагрузках (8 000 RPS пик) разница между FastAPI и Go практически незаметна. Для Aether, где основная задержка — AI inference (секунды), а не HTTP roundtrip, производительность HTTP-слоя вторична.
- **Go** — доминирует при CPU-bound нагрузках и миллионах concurrent connections. Для Aether это избыточно, если не планируется 100k+ одновременных WebSocket-соединений.
- **Node.js (Fastify)** — производительность близка к FastAPI для I/O-bound, но хуже при CPU-интенсивных операциях (JSON parsing, data transformation для AI payloads).

**Вердикт:** Для Aether производительность HTTP-слоя — не bottleneck. Реальный bottleneck — AI inference latency. Все три варианта покрывают требования воронки.

---

## 2. Экосистема AI/ML

| Критерий | Python (FastAPI) | Go | Node.js |
|---|---|---|---|
| **LLM frameworks** | 🔥🔥🔥 LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen | 🔥 Go-ai, golang-ml (развитие идёт) | 🔥🔥 @langchain/core, Vercel AI SDK |
| **Embedding** | 🔥🔥🔥 sentence-transformers, OpenAI embeddings, FAISS, Chroma | 🔥 gofaid, go-embed (ограничено) | 🔥🔤 @xenova/transformers, vectorise |
| **Vector search** | 🔥🔥🔥 FAISS, Chroma, Qdrant (Python client), Weaviate | 🔥 Qdrant/Weaviate client (HTTP) | 🔥🔤 Qdrant/Weaviate client (HTTP) |
| **Model inference** | 🔥🔥🔤 PyTorch, TensorFlow, ONNX, Ollama API | 🔥 Ollama API, ggergonn (GGUF) | 🔥 Ollama API, Transformers.js |
| **Data processing** | 🔥🔥🔤 Pandas, NumPy, Polars | 🔥 limited | 🔥🔤 limited (no NumPy equivalent) |
| **AI Agent orchestration** | 🔥🔥🔤 LangGraph, CrewAI, SmythOS | 🔤 go-ai (early) | 🔥🔤 Vercel AI SDK, LangChain JS |
| **MCP (Model Context Protocol)** | ✅ Python SDK (official) | ✅ Go SDK (official) | ✅ Node SDK (official) |

### Ключевые наблюдения

- **Python — абсолютный лидер AI-экосистемы.** 90%+ AI/ML библиотек написаны на Python. LangChain, LangGraph, CrewAI — индустриальные стандарты. Для Aether с AI-ядром это критическое преимущество.
- **Node.js — сильный второй.** Vercel AI SDK и @langchain/core покрывают большинство use cases. Хорошая интеграция с React-фронтендом. Нет NumPy/Pandas — ограничение для data processing.
- **Go — слабый игрок.** Экосистема AI/ML минимальна. Go подходит для оркестрации вызовов к внешним AI API, но не для встраивания ML-моделей. Придётся вызывать Python-сервисы через gRPC/HTTP.

**Вердикт:** Python безальтернативен для AI-ядра Aether. Node.js — приемлемая альтернатива для orchestration. Go требует гибридной архитектуры (Go + Python sidecar).

---

## 3. Скорость разработки

| Критерий | Python (FastAPI) | Go | Node.js (Fastify) |
|---|---|---|---|
| **Type safety** | 🔥🔤 Pydantic v2 (runtime validation) | 🔥🔤🔥 Compile-time, strong | 🔥🔤 TypeScript (compile-time) |
| **Auto API docs** | 🔥🔥🔤 OpenAPI/Swagger (built-in) | 🔤 Swagger (manual setup) | 🔤 Swagger (manual setup) |
| **Hot reload (dev)** | ✅ uvicorn --reload | ❌ No native HMR (air) | ✅ nodemon / ts-node-dev |
| **Kode generacija** | 🔥🔥 Pydantic → OpenAPI → frontend SDK | 🔤 limited | 🔥🔤 tRPC, OpenAPI generators |
| **Testing** | ✅ pytest, hypothesis, pytest-asyncio | ✅ go test (built-in) | ✅ jest, vitest, mocha |
| **Dev velocity (субъективно)** | ⚡⚡⚡ Быстро | ⚡⚡ Средне | ⚡⚡⚡ Быстро |
| **Boilerplate** | Минимум (FastAPI decorators) | Средне (interfaces + structs) | Средне (middleware + routes) |
| **AI-код AI-агентами** | 🔥🔤 Лучшая поддержка (Copilot, Cursor) | 🔥🔤 Хорошая | 🔥🔤🔤 Лучшая (JS/TS доминирует) |

### Ключевые наблюдения

- **FastAPI** — минимальный boilerplate, встроенные OpenAPI-доки, Pydantic v2 для валидации. Скорость прототипирования AI-сервисов максимальна.
- **Node.js (TypeScript + Fastify)** — схожая скорость для API, но лучше интеграция с фронтендом (общие типы через tRPC/Zod).
- **Go** — больше boilerplate, но компиляция даёт безопасность. Для стартапа скорость Go проигрывает.

**Вердикт:** FastAPI ≈ Node.js (TS) > Go по скорости разработки. Для AI-прототипов FastAPI лучший выбор.

---

## 4. DevOps Footprint

| Метрика | Python (FastAPI) | Go | Node.js (Fastify) |
|---|---|---|---|
| **Docker image (minimal)** | ~180 MB (slim + deps) | ~10–40 MB (scratch/distroless) | ~180 MB (alpine, production-only) |
| **Docker image (standard)** | ~500–800 MB (с AI deps) | ~20–60 MB | ~200–400 MB (с node_modules) |
| **Docker image (AI-полный)** | ~1.5–4 GB (PyTorch + numpy) | ~40 MB (не использует AI deps) | ~300–500 MB |
| **RAM consumption (idle)** | ~50–150 MB | ~10–30 MB | ~40–100 MB |
| **RAM consumption (под нагрузкой)** | ~200–500 MB (worker pool) | ~50–100 MB (goroutines) | ~150–400 MB (cluster) |
| **Cold start** | ~1–3 сек (uvicorn) | ~20–100 ms (static binary) | ~500 ms–2 сек (node_modules) |
| **CPU cores usage** | Множественные воркеры | Мульти-поточные goroutines | Single thread (cluster = множ. proc) |
| **K8s fit** | ✅ Хороший (horz. scale) | 🔥🔤 Best (маленькие, лёгкие) | ✅ Хороший |

### Ключевые наблюдения

- **Go — король DevOps.** Образы ~10–40 MB, RAM ~10–30 MB, cold start <100 ms. Идеально для serverless, edge, K8s.
- **Python** — тяжёлый. С AI-библиотеками образ легко растёт до 1.5–4 GB. Cold start 1–3 сек. Но для SaaS с постоянными инстансами это не проблема.
- **Node.js** — середина. Alpine образ ~180 MB, но node_modules раздувают. Cold start медленнее Go, быстрее Python.

**Вердикт:** Если Aether разворачивается как всегда-работающий сервис (не serverless), разница в образе и cold start не критична. Go выигрывает только в serverless/edge-сценариях.

---

## 5. Командная доступность

| Критерий | Python (FastAPI) | Go | Node.js |
|---|---|---|---|
| **Общий пул разработчиков** | 🔥🔤🔤 Огромный (#1 язык) | 🔤 Средний (рост) | 🔥🔤🔤 Огромный (#1 веб-язык) |
| **AI/ML специализация** | 🔥🔤🔤 Абсолютный лидер | 🔤 Минимальный | 🔤 Средний |
| **Зарубежный рынок** | 🔥🔤🔤 Самый востребованный | 🔤 Дефицит | 🔥🔤🔤 Много |
| **Российский рынок** | 🔥🔤🔤 Много | 🔤 Средне | 🔥🔤 Средне |
| **Freelance доступность** | 🔥🔤🔤 Лучшая | 🔤 Средняя | 🔥🔤🔤 Лучшая |
| **Зарплата (средняя)** | $$ | $$–$$$ | $$ |
| **Обучаемость (для бэкенда)** | Быстро (синтаксис) | Средне (GOPATH, generics, interfaces) | Быстро (если JS-фон) |
| **Заменяемость** | 🔥🔤🔤 Высокая | 🔤 Средняя | 🔥🔤🔤 Высокая |

### Ключевые наблюдения

- **Python** — самый простой стек для найма. Каждый AI-разработчик знает Python. FastAPI-специалистов меньше, но порог входа низкий.
- **Node.js** — аналогично. Огромный пул, но меньше AI-специалистов в JS.
- **Go** — разработчики дороже, меньше на рынке. Для маленького стартапа это риск.

**Вердикт:** Python ≈ Node.js > Go. Для AI-стартапа Python даёт лучший доступ к талантам.

---

## 6. Риски

| Риск | Python (FastAPI) | Go | Node.js |
|---|---|---|---|
| **GIL (Global Interpreter Lock)** | ⚠️ Ограничивает CPU-bound задачи. Решается: multiprocessing, asyncio для I/O, Rust-extensions (Pydantic v2, polars) | ✅ Нет GIL. True parallelism | ✅ Нет GIL (но event loop однопоточен) |
| **Async model** | ⚠️ Async в Python молод. Миксин sync/async сложен. Некоторые библиотеки не async-compatible | ✅ Goroutines — простые и надёжные | ⚠️ Callback hell ушёл, но race conditions в async/await возможны. Unhandled promise rejection |
| **Type safety** | ⚠️ Pydantic v2 — runtime validation. Нет compile-time гарантий. MyPy помогает | ✅ Compile-time type checking. Строгая система | ✅ TypeScript — compile-time (если настроен строго) |
| **Memory leaks** | ⚠️ Python GC не deterministic. Circular refs. C-extensions могут утекать | ✅ Garbage collector (tracing). Предсказуемый. Rare leaks | ⚠️ V8 GC. Memory leaks через closures, event listeners. Harder to debug |
| **Performance regression** | ⚠️ Python 3.13 JIT в разработке. Улучшения возможны | ✅ Стабильная производительность | ✅ V8 оптимизации постоянны |
| **Dependency hell** | ⚠️ pip dependency resolution сложный. С AI-библиотеками — ад | ✅ Go modules — простые и предсказуемые | ⚠️ npm dependency tree — дерево боли |
| **Long-term maintenance** | ✅ Стабильный. 30+ лет. Backwards compatibility | ✅ Стабильный. 10+ лет. No breaking changes | ⚠️ Breaking changes в Node.js мажорных версиях. npm ecosystem fragmented |
| **AI-специфичные риски** | ⚠️ AI-библиотеки быстро меняются. Breaking changes в LangChain, Pydantic | ✅ Минимум AI-deps = минимум риска | ⚠️ AI SDK immature. Vercel AI SDK может измениться |

### Ключевые наблюдения

- **GIL** — главный риск Python. Для Aether это не проблема, так как основная нагрузка — I/O (API calls, WebSocket, DB). CPU-bound задачи (если будут) решаются multiprocessing или выносом в отдельный сервис.
- **Async model Python** — слабое место. Миксин sync/async библиотек — источник багов. Нужно строго async-first дизайн.
- **Memory leaks Node.js** — классическая проблема production. Требует хорошего monitoring (clinic.js, 0x).
- **Go** — наименьшая поверхность рисков. Compile-time проверки, простые goroutines, предсказуемый GC.

**Вердикт:** Go имеет наименьшую поверхность рисков. Python и Node.js требуют дисциплины в async и memory management.

---

## 7. Сводная матрица

| Критерий | Python (FastAPI) | Go | Node.js (Fastify) |
|---|---|---|---|
| Производительность | 7/10 | 10/10 | 8/10 |
| AI/ML экосистема | **10/10** | 3/10 | 6/10 |
| Скорость разработки | 9/10 | 6/10 | 9/10 |
| DevOps footprint | 5/10 | **10/10** | 7/10 |
| Командная доступность | **10/10** | 5/10 | 9/10 |
| Минимальные риски | 6/10 | **9/10** | 6/10 |
| **Взвешенный итог** | **8.5/10** | **6.5/10** | **7.5/10** |

### Взвешивание для Aether

| Критерий | Вес | Обоснование |
|---|---|---|
| AI/ML экосистема | 30% | Ядро Aether — AI-воронка. Без экосистемы нет продукта |
| Скорость разработки | 20% | Start-up phase. Time-to-market критичен |
| Командная доступность | 20% | Малая команда. Найм и замена — риск |
| Производительность | 15% | AI latency — главный bottleneck, не HTTP |
| DevOps footprint | 5% | SaaS, не serverless. Не критично |
| Риски | 10% | Важно, но управляемо |

---

## 8. Рекомендация

### 🏆 Выбор: Python (FastAPI)

**Причины:**

1. **AI-экосистема — решающий фактор.** Aether — AI-воронка. Python владеет 90%+ AI/ML инструментов. LangChain, LangGraph, CrewAI, sentence-transformers, FAISS — всё на Python. На Go или Node.js придётся писать glue-код или вызывать Python-сервисы, что усложняет архитектуру.

2. **Скорость разработки.** FastAPI даёт минимальный boilerplate, встроенные OpenAPI-доки, Pydantic v2 для валидации. Для start-up фазы скорость критична.

3. **Командная доступность.** Python — самый доступный стек. Каждый AI-инженер знает Python. На Go для AI-задач — дефицит.

4. **Производительность достаточна.** Для Aether bottleneck — AI inference (секунды), а не HTTP (миллисекунды). FastAPI справляется с нагрузкой SaaS-воронки.

5. **Существующий опыт Logicore.** Уже есть production-опыт с FastAPI. Переиспользование знаний и паттернов.

### Митигация рисков Python

| Риск | Митигация |
|---|---|
| GIL / CPU-bound | Async-first дизайн. CPU-heavy задачи через multiprocessing или отдельный worker |
| Memory leaks | Structured logging + monitoring (Prometheus). Regular profiling |
| Async complexity | Строго async-first. Избегать sync/async миксина. Библиотеки — только async-compatible |
| Dependency hell | Docker slim образы. Pin versions. Poetry/pip-tools для deterministic builds |
| Type safety | Pydantic v2 (Rust-backed). MyPy в CI. Type hints повсеместно |

### Альтернативная стратегия (гибридная)

Если производительность HTTP-слоя станет проблемой:

```
┌─────────────────────────────────────────────┐
│  API Gateway (Go / NGINX)                   │
│  — WebSocket routing                         │
│  — Rate limiting                             │
│  — Auth / CORS                               │
└──────────┬──────────────────┬────────────────┘
           │                  │
     ┌─────▼─────┐    ┌──────▼──────┐
     │ FastAPI   │    │ FastAPI     │
     │ AI Core   │    │ Channels    │
     │ Service   │    │ Service     │
     └───────────┘    └─────────────┘
```

Этот подход откладывается до появления реальной проблемы (premature optimization).

---

## 9. TL;DR

| | Python (FastAPI) | Go | Node.js |
|---|---|---|---|
| **Лучше для** | AI-сервисы, ML pipelines, быстрая разработка | High-performance gateway, microservices, embedded | Full-stack JS, real-time apps, frontend sharing |
| **Выбрать если** | AI — ядро продукта (✅ Aether) | Скорость критична, AI внешний | Единый стек JS full-stack |
| **Не выбирать если** | Нужна максимальная производительность HTTP | Нужна AI/ML экосистема | Нужна CPU-bound обработка |

**→ Python (FastAPI) — правильный выбор для Aether.**
