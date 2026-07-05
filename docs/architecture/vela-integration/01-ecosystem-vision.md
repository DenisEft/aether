# 🌐 Aether Ecosystem — Vision & Architecture

**Version:** 1.0.0
**Created:** 2026-07-05
**Status:** Draft — pending review
**Audience:** Architecture, Development, Product

---

## 1. Executive Summary

### What We're Building

Aether — единая SaaS-экосистема для построения бизнес-инстансов:

- **Aether Core** — AI-инфраструктура: tenants, auth (passwordless-first), billing (streaming), AI router, channels (Telegram/Email/Web)
- **Vela** — конструктор инстансов Aether: визуальное создание бизнес-процессов через FlowEditor + PageBuilder, AI-ассистент (ProcessBot) для генерации из графики/текста/событий
- **Logicore** — инстанс Aether: логистическая CRM
- **AI-OPS** — инстанс Aether: мониторинг AI-инфраструктуры

### Core Principle

> **Vela — фабрика инстансов Aether.**
> Человек рисует процесс на доске → ProcessBot (AI Vision) генерирует BPMN → Vela создаёт tenant в Aether → пользователь получает готовый SaaS-инстанс.

```
                          AETHER — AI SaaS Framework
              ┌──────────────────────────────────────────────┐
              │  Tenants · Auth (passwordless) · Billing     │
              │  AI Router (multi-driver) · Streaming Billing │
              │  Channels (TG/Email/Web) · Plugin Arch       │
              │  Tenant Isolation (RLS + ContextVar + Redis) │
              └──────────────────┬───────────────────────────┘
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
  ┌────▼──────────┐    ┌────────▼────────┐    ┌───────────▼──────┐
  │    LOGICORE   │    │      VELA       │    │     AI-OPS       │
  │  Aether Inst. │    │  Aether Inst.   │    │  Aether Inst.    │
  │  (логистика)  │    │  (конструктор)  │    │  (мониторинг)    │
  │               │    │                 │    │                  │
  │  • CRM        │    │  • FlowEditor   │    │  • GPU tracking  │
  │  • Контрагенты│    │  • PageBuilder  │    │  • Tokens usage  │
  │  • Перевозки  │    │  • ProcessBot   │    │  • Cost analysis │
  │  • Счета      │    │  • Фабрика      │    │  • Alerts        │
  │  • Грузы      │    │    инстансов    │    │                  │
  └───────────────┘    └────────┬────────┘    └──────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
               ┌────▼─────┐ ┌──▼──────┐ ┌──▼──────┐
               │ Процесс A │ │Процесс B│ │Процесс C│
               │ Инстанс   │ │Инстанс  │ │Инстанс  │
               │ Aether    │ │Aether   │ │Aether   │
               └───────────┘ └─────────┘ └─────────┘
```

---

## 2. Architecture Principles

### 2.1 Zero Hardcode
No hardcoded model paths, ports, URLs, API keys, filesystem paths, or environment-specific values. Everything configurable through env vars (with dev defaults), YAML/JSON configs, CLI flags, or DB runtime settings.

### 2.2 Tenant Isolation (RLS + ContextVar + Redis Prefix)
Three levels of isolation for every Aether instance:
- **Application:** `ContextVar[TenantContext]` — per-request tenant binding
- **Database:** PostgreSQL Row-Level Security — `tenant_id` column on every table
- **Cache:** Redis key prefix `tenant:{tenant_id}:*`

### 2.3 Plugin Architecture
All business logic lives in plugins. Vela ProcessBot is a plugin. Logicore logistics is a plugin pack. Zero core changes for new domains.

### 2.4 AI-Native Design
Every component can consume and produce AI. AI Router selects optimal model per task. Streaming billing tracks costs in real-time.

### 2.5 Contract-First API
OpenAPI 3.1 specs → generated Pydantic models. JSON Schema for all I/O. End-to-end type safety.

---

## 3. Vela as Constructor: Core Flow

### 3.1 Manual Path (Core, Free)
1. User opens Vela FlowEditor
2. Drags blocks from palette → creates process graph
3. Opens PageBuilder → arranges UI grid
4. Clicks "Deploy" → Vela calls Aether Tenant Provisioning
5. Aether creates tenant, provisions DB, activates billing
6. User gets URL and works

### 3.2 AI-Assisted Path (VIP, Paid)
1. User uploads photo/scan of hand-drawn process diagram
2. ProcessBot (Vision) → recognizes boxes, arrows, text → produces ProcessDefinition JSON
3. User validates and edits in FlowEditor
4. ProcessBot generates pages via PageBuilder
5. One-click deploy → Aether instance provisioned
6. Every ProcessBot call = billing event

### 3.3 Autonomous Path (Enterprise)
1. Vela connected to Logicore (or other data source)
2. ProcessBot analyzes event stream: status changes, document flows, user actions
3. Detects patterns → proposes process definitions
4. Human approves → auto-deploys Aether instance
5. Instance self-optimizes over time

---

## 4. Data Flow: Photo → Aether Instance

```
┌─────────────────────────────────────────────────────────────────┐
│  1. INPUT                                                        │
│     Photo/scan of board/schema → Vela ProcessBot UI              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  2. PROCESSBOT — Vision Pipeline                                 │
│     ┌──────────────────────────────────────────────────────┐    │
│     │ Image → AI Router selects model (cost/quality)       │    │
│     │   ├── Local: Qwen 35B (free)                         │    │
│     │   └── Cloud: DeepSeek V4 Pro (billed)                │    │
│     │                                                      │    │
│     │ Vision Model extracts:                               │    │
│     │   ├── Rectangles → ProcessBlock[]                    │    │
│     │   ├── Arrows → ProcessConnection[]                   │    │
│     │   ├── Labels → block.label, block.key                │    │
│     │   └── Groups → nesting (parent_block_id)             │    │
│     │                                                      │    │
│     │ Output: ProcessDefinition JSON (blocks + connections)│    │
│     └──────────────────────────────────────────────────────┘    │
│                                                                  │
│     Billing: streaming billing middleware counts tokens/credits  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  3. VELA — FlowEditor + PageBuilder                              │
│     ┌──────────────────────────────────────────────────────┐    │
│     │ Load ProcessDefinition into FlowEditor canvas        │    │
│     │ User validates, adjusts connections, configures      │    │
│     │ User opens PageBuilder → arranges page layout        │    │
│     │ User sets: page routes, styles, block visibility     │    │
│     │ Save → POST /api/process-definitions/{id}/pages      │    │
│     └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  4. DEPLOY — Vela → Aether Tenant Provisioning                  │
│     ┌──────────────────────────────────────────────────────┐    │
│     │ Vela calls: POST /api/v1/tenants (Aether API)        │    │
│     │   {                                                  │    │
│     │     "slug": "logistics-coalstar",                    │    │
│     │     "name": "Логистика Coalstar",                    │    │
│     │     "process_def_id": "uuid-of-process",             │    │
│     │     "subscription_plan": "pro"                       │    │
│     │   }                                                  │    │
│     │                                                      │    │
│     │ Aether TenantProvisioningService:                    │    │
│     │   ├── Creates Tenant record                          │    │
│     │   ├── Creates DB schema (RLS policies)               │    │
│     │   ├── Creates Redis keyspace                         │    │
│     │   ├── Creates default roles (owner/admin/member)     │    │
│     │   ├── Activates trial subscription                   │    │
│     │   ├── Seeds process definition                       │    │
│     │   ├── Generates frontend pages from PageBuilder      │    │
│     │   └── Returns: tenant_id, admin_url, workspace_url   │    │
│     └──────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  5. LIVE — Ready-to-use SaaS Instance                            │
│     ┌──────────────────────────────────────────────────────┐    │
│     │ User opens: https://coalstar.aether.local/           │    │
│     │ Logs in (passwordless magic link)                    │    │
│     │ Sees: Process Dashboard with pages from PageBuilder  │    │
│     │ Starts working: creates records, changes statuses    │    │
│     │ Processes flow through stages                        │    │
│     │ AI channels active (Telegram bot, Web widget)        │    │
│     │ Billing tracks usage in real-time                    │    │
│     └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Component Inventory

| Component | Project | Status | Key Files |
|-----------|---------|--------|-----------|
| **Tenant Provisioning** | Aether | ✅ Code (needs process seeding) | `services/tenant_provisioning.py` |
| **Multi-Tenant Models** | Aether | ✅ Code | `models/tenants.py`, `organisations.py` |
| **Subscription/Billing** | Aether | ✅ Code | `models/billing.py`, `services/billing_service.py` |
| **Streaming Billing** | Aether | ✅ Code | `services/streaming_billing.py` |
| **AI Router** | Aether | ✅ Code | `services/ai_pipeline.py` (CircuitBreaker + ContextManager) |
| **Channel System** | Aether | ✅ Code | `channels/{base,telegram,email,widget}.py` |
| **Plugin Architecture** | Aether | ✅ Code | `services/plugins/{base,registry,loader}.py` |
| **Auth (passwordless)** | Aether | ✅ Code | `api/v1/auth.py`, `services/oauth_service.py` |
| **FlowEditor (BPMN)** | Vela | ✅ Code | `components/process-editor/FlowEditor.vue` |
| **PageBuilder (Grid)** | Vela | ✅ Code | `components/process-editor/PageBuilder.vue` |
| **Block Types Catalog** | Vela | ✅ Code | `routers/processes.py` (`/block-types`) |
| **Process API** | Vela | ✅ Code | `routers/processes.py` (full CRUD) |
| **Pages API** | Vela | ✅ Code | `routers/processes.py` (`/pages`) |
| **Process Validation** | Vela | ✅ Code | `routers/processes.py` (`/validate`) |
| **Versioning + Snapshots** | Vela | ✅ Code | `routers/processes.py` (`/versions`) |
| **ProcessBot (Vision→BPMN)** | — | ❌ NOT STARTED | — |
| **ProcessBot (NLP→BPMN)** | — | ❌ NOT STARTED | — |
| **ProcessBot (Events→BPMN)** | — | ❌ NOT STARTED | — |
| **Vela→Aether Deploy Bridge** | — | ❌ NOT STARTED | — |
| **Marketplace (templates)** | Aether | ⚠️ Concept only | — |
| **AI-OPS unified monitoring** | AI-OPS | ⚠️ Partial | — |
| **Mobile (Capacitor)** | AI-OPS Mobile | ⚠️ Partial | — |

---

## 6. Gap Analysis: What's Missing for MVP

### Critical Path (ProcessBot Vision MVP)

| # | Task | Effort | Priority |
|---|------|--------|----------|
| 1 | **ProcessBot Vision Service** — new Vela API endpoint that accepts image → returns ProcessDefinition | 3d | P0 |
| 2 | **AI Router Integration** — Vela calls Aether AI Router for model selection | 1d | P0 |
| 3 | **ProcessBot UI** — upload widget in Vela FlowEditor with preview of recognized process | 2d | P0 |
| 4 | **Vela→Aether Deploy API** — Vela calls Aether `/tenants` + provisions process | 2d | P0 |
| 5 | **Process Seeding** — Aether TenantProvisioning seeds ProcessDefinition into new tenant | 1d | P0 |
| 6 | **Billing Integration** — streaming billing for ProcessBot calls | 1d | P0 |

### Foundation (before MVP)

| # | Task | Effort | Priority |
|---|------|--------|----------|
| 7 | **Aether Docker Compose** — tested, working dev environment | — | P1 |
| 8 | **Vela Auth → Aether Auth** — Vela uses Aether JWT (same secret) | 1d | P1 |
| 9 | **Vela DB migration to PostgreSQL** — currently SQLite, needs PG for RLS | 2d | P1 |
| 10 | **API Contract** — OpenAPI spec for Vela→Aether integration | 1d | P1 |

---

## 7. Revenue Model

```
FREE Tier (Core):
  • Manual FlowEditor + PageBuilder
  • 1 active process
  • 3 users
  • Community block types

PRO Tier (VIP):
  • Unlimited processes
  • 10 AI ProcessBot generations/month
  • AI Router: local model (free generations)
  • 10 users

ENTERPRISE:
  • Unlimited AI generations
  • AI Router: cloud models (DeepSeek, GPT-4V)
  • Autonomous process discovery (Events→BPMN)
  • Custom block types
  • SSO, dedicated tenant
  • SLA

ProcessBot Pay-Per-Use (bolt-on):
  • Photo→Process: 50 credits
  • Text→Process: 30 credits
  • Events→Process: 100 credits/month passive monitoring
  • Credits: 1 credit ≈ $0.01 (tiered volume discounts)
```

---

## 8. Next Steps

1. **Approve architecture** — this document
2. **Implement ProcessBot Vision MVP** — separate spec
3. **Vela→Aether Deploy Bridge** — separate spec
4. **Pilot with Logicore** — first real Aether instance from existing data
5. **Dogfooding** — use Vela to build Vela's own processes (meta!)

---

## Appendix A: Related Documents

- `docs/architecture/overview.md` — Aether architecture overview
- `docs/architecture/tenant.md` — Tenant isolation, billing, rate limiting
- `docs/architecture/services.md` — Plugin system
- `docs/architecture/channels.md` — Channel abstraction
- `docs/architecture/ai-core.md` — AI drivers, routing
- `docs/architecture/frontend.md` — Admin + Client workspaces
- `docs/AUDIT.md` — Architecture audit (28 issues)
- `memory/projects/vela.md` — Vela project card
- `memory/projects/logicore.md` — Logicore project card

## Appendix B: Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend Framework | FastAPI (Python 3.11+) | Async, OpenAPI-native, type-safe |
| Database | PostgreSQL 16 + RLS | Tenant isolation, JSONB, full-text |
| Cache | Redis 7 | Session, rate limiting, pub/sub |
| AI Inference | Multi-driver: LlamaCpp, Ollama, OpenAI | Cost/quality routing |
| Frontend | Vue 3 + TypeScript + Vite | Composition API, ecosystem |
| Flow Editor | @vue-flow/core | BPMN-like, extensible |
| Page Builder | vue-grid-layout | Responsive grid, drag-drop |
| Mobile | Capacitor 6 | Cross-platform from Vue |
| DevOps | Docker + Docker Compose | Reproducible dev/prod |
| CI/CD | GitHub Actions (+ local pre-commit) | Automated pipeline |
