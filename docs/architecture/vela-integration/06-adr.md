# Vela Integration — ADR (Architecture Decision Records)

> **Status:** Accepted
> **Governance:** Denis Eftimitsa (final approval), Lora (proposal + analysis)

---

## ADR-001: Aether as Framework, Vela as Constructor

**Date:** 2026-07-02
**Status:** Accepted

### Context
MTK needed a system to automate business processes. Two options:
1. Build processes directly in Logicore (monolith approach)
2. Extract process engine into Vela, with Aether providing multi-tenant infrastructure

### Decision
**Option 2 — Aether as framework, Vela as constructor.**

### Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **Monolith** (all in Logicore) | Simple, fast to build | Cannot sell separately, no multi-tenant, couples logistics to process engine | ❌ |
| **Standalone Vela** (no Aether) | Independent product | Must rebuild auth, billing, tenants from scratch. Duplication. | ❌ |
| **Aether framework** (chosen) | Reuse auth, billing, tenants, AI router. Logicore is just one instance. Platform effect. | More complex integration, requires M2M auth | ✅ |

### Consequences
- Vela must migrate from SQLite to PostgreSQL (RLS requirement)
- M2M auth needed between Vela and Aether
- Aether must be production-ready before Vela can deploy instances

---

## ADR-002: ProcessBot as Paid VIP Feature

**Date:** 2026-07-02
**Status:** Accepted

### Context
Vela has two user paths: manual FlowEditor (free) and AI-assisted generation. AI generation costs money (API calls, GPU time). Question: bundle or unbundle?

### Decision
**ProcessBot is a paid bolt-on. Free tier gets manual FlowEditor only.**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **All free** | Maximum adoption | Burns money on API costs, no revenue | ❌ |
| **All paid** | Revenue from day 1 | No adoption, no network effect, no free tier to upsell from | ❌ |
| **Freemium + VIP** (chosen) | Free tier drives adoption, VIP monetizes power users. 97%+ margins on AI. | Must implement usage tracking + billing before launch | ✅ |

### Cost Analysis
- Cloud vision call: $0.012-0.022
- Local NLP call: $0.002
- Pro plan price: $9.90/mo for 30 generations → COGS $0.16 → 98.4% margin
- Break-even: 16 Pro subscribers cover $150/mo infrastructure

### Consequences
- Must integrate streaming billing before ProcessBot launch
- Credit system needed (50 credits/image, 30 credits/text)
- Graceful degradation when credits exhausted (402 response, not feature removal)

---

## ADR-003: Machine-to-Machine Auth (JWT, not OAuth2)

**Date:** 2026-07-05
**Status:** Accepted

### Context
Vela needs to call Aether APIs to deploy instances. Two auth patterns: OAuth2 client credentials or shared JWT secret.

### Decision
**Shared JWT secret with short TTL (5min), jti nonce, and scope restrictions.**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **OAuth2 Client Credentials** | Industry standard, token introspection | Requires OAuth2 server (complexity), more moving parts | ❌ for MVP |
| **API Key (static)** | Simplest | No expiry, no rotation, no granular scopes. Security nightmare. | ❌ |
| **Shared JWT** (chosen) | Simple, self-contained, expirable, scope-able, auditable | Must share secret securely, no dynamic revocation (solved by 5min TTL) | ✅ |

### Security Properties
- HS256 signed, TTL 5 minutes
- jti stored in Redis for anti-replay (TTL 5min)
- Scopes: `deploy:write`, `deploy:read`, `deploy:delete`, `processbot:generate`
- Key rotation every 30 days, 24h grace period
- Emergency rotation via admin API

### Future
Migrate to RS256 (asymmetric) when multi-service ecosystem grows beyond 3 services. JWT approach is forward-compatible — just swap signing key type.

---

## ADR-004: Local Model as Default for NLP, Cloud for Vision

**Date:** 2026-07-05
**Status:** Accepted

### Context
ProcessBot needs AI for both vision (image→BPMN) and NLP (text→BPMN). Qwen 35B is local (free but cannot do vision), DeepSeek V4 Pro is cloud (vision-capable but costs money).

### Decision
**NLP → local Qwen by default. Vision → DeepSeek cloud. User can override.**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **All cloud** | Always best quality | NLP costs $0.013/call vs $0.002 local. 6.5x cost increase for no quality gain. | ❌ |
| **All local** | Zero cost | No vision capability. Qwen 35B can't process images. | ❌ |
| **Hybrid** (chosen) | NLP cheap, vision cloud, user override | Must implement AI Router with cost/quality routing | ✅ |

### Routing Logic
```
Input type = "image" → always cloud (DeepSeek or GPT-4V fallback)
Input type = "text"  → local Qwen by default
                       → cloud if user prefers (model_preference: "cloud")
                       → cloud if local model is down (CircuitBreaker triggers)
Input type = "events" → local Qwen (background processing, cost-sensitive)
```

### Consequences
- AI Router must monitor local model health (CircuitBreaker already exists in Aether)
- Must track cost savings from local routing (Prometheus counter)

---

## ADR-005: SAGA Pattern for Deploy (not 2PC)

**Date:** 2026-07-05
**Status:** Accepted

### Context
Deploy has 8 steps across multiple services (tenant, provisioning, process, pages, subscription, channels, owner). Need atomicity: all succeed or all roll back.

### Decision
**SAGA with compensating transactions, not distributed transaction (2PC).**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **2PC (XA)** | True atomicity | Requires XA-compatible drivers, locks resources, doesn't work well across HTTP boundaries | ❌ |
| **Best-effort (no rollback)** | Simplest | Leaves garbage on failure. Manual cleanup. | ❌ |
| **SAGA** (chosen) | Eventual consistency, each step has explicit compensation, no long-lived locks | Compensation can fail (needs alerting + manual runbook) | ✅ |

### Compensation Chain
```
Step 1: validate_manifest    → compensate: noop
Step 2: create_tenant        → compensate: delete_tenant
Step 3: provision_tenant     → compensate: deprovision
Step 4: seed_process         → compensate: unseed
Step 5: seed_pages           → compensate: unseed
Step 6: activate_sub         → compensate: cancel_sub
Step 7: config_channels      → compensate: deconfig
Step 8: create_owner         → compensate: delete_owner
```

### Failure Mode
If compensation fails → **CRITICAL alert to operations** with full context. Manual runbook required. This is an accepted risk for v1; auto-retry with exponential backoff in v2.

---

## ADR-006: vue-grid-layout for PageBuilder (Not Custom Grid)

**Date:** 2026-07-01
**Status:** Accepted

### Context
PageBuilder needs a drag-and-drop responsive grid for arranging process blocks into pages. Options: build custom or use existing library.

### Decision
**vue-grid-layout (Vue 3 port of react-grid-layout).**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **Custom grid** | Full control, no dependency | Weeks of dev, bug-prone, no responsive breakpoints out of box | ❌ |
| **CSS Grid + interact.js** | Lightweight | Must build layout algorithm, serialize/deserialize, undo/redo ourselves | ❌ |
| **vue-grid-layout** (chosen) | 12-col responsive, drag/resize, serialize to JSON, 2.8K stars, mature | External dependency, CSS transforms can conflict with some Vue patterns | ✅ |

### Consequences
- Layout stored as JSON in `process_pages.layout_config` → easy to version, diff, migrate
- Breakpoints configured: LG(12), MD(10), SM(6), XS(4)
- If vue-grid-layout is abandoned, JSON format is simple enough to migrate to custom implementation

---

## ADR-007: PostgreSQL + RLS for Tenant Isolation (Not Separate DBs)

**Date:** 2026-07-02
**Status:** Accepted

### Context
Multi-tenant isolation strategy. Options: database-per-tenant, schema-per-tenant, or shared database with RLS.

### Decision
**Shared PostgreSQL with Row-Level Security (RLS) + ContextVar + Redis key prefix.**

### Alternatives

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **DB per tenant** | Strongest isolation | Cannot scale (1000 tenants = 1000 DBs), connection pool explosion, migration hell | ❌ |
| **Schema per tenant** | Good isolation | PG schema limits, complex migrations, ORM pains | ❌ |
| **Shared + RLS** (chosen) | Single DB to manage, PG enforces isolation at row level, scales to 10K+ tenants | Requires discipline (every query must set tenant context), RLS policy maintenance | ✅ |

### Implementation
```sql
-- Every table
ALTER TABLE process_instances ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON process_instances
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Application layer
tenant_ctx: ContextVar[TenantContext]  -- set by middleware
db_session.execute("SET app.current_tenant_id = :tid", {"tid": ctx.tenant_id})
```

### Consequences
- SQLite cannot do RLS → Vela must migrate to PostgreSQL
- Every new table must have `tenant_id` column + RLS policy
- Performance: RLS adds ~1-3% overhead (acceptable)

---

## ADR-008: Python FastAPI for All Backends (No Microservice Split Yet)

**Date:** 2026-07-01
**Status:** Accepted

### Context
Aether, Vela, Logicore all use Python FastAPI. Question: split into microservices now or keep as modular monoliths?

### Decision
**Modular monoliths (one FastAPI per domain) with clear boundaries. No microservice split until needed.**

### Rationale
- Current load: <100 users. Microservice overhead (service discovery, distributed tracing, eventual consistency) would slow development by 3-5x with zero benefit.
- FastAPI's dependency injection and router mounting give us clean module boundaries without network calls.
- We CAN split later: each router/module is independently deployable.

### Split Triggers (when to reconsider)
1. Any single service needs independent scaling (CPU/memory isolation)
2. Different deployment cadences (Vela updates weekly, Logicore never)
3. Different security boundaries (external vs internal)
4. Team grows beyond 5 developers

### Consequences
- All services share same FastAPI patterns, Pydantic models, error handling
- Cross-service communication via HTTP (not message queue) for now
- Accept eventual duplication of shared code until extraction is justified
