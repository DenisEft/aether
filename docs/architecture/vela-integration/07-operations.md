# Vela Integration — Operational Documentation

> **Contents:** Effort estimates, runbook, acceptance criteria, environment config, v1 scope boundaries

---

## Section A: Effort Estimation & Critical Path

### A.1 Task Breakdown with Estimates

**Total estimated effort: 225 hours (~5.6 weeks for 2 full-time developers)**

```
Phase 1: Foundation (Week 1-2) — 80h
├── 1.1  Vela PG migration (SQLite→PostgreSQL)             16h
├── 1.2  Vela auth → Aether JWT (shared secret)             8h
├── 1.3  Aether Docker Compose validation + fix            8h
├── 1.4  M2M auth implementation (both sides)              12h
├── 1.5  OpenAPI → Pydantic models generation               4h
├── 1.6  OpenAPI → TypeScript types generation               4h
├── 1.7  CI/CD pipeline (GitHub Actions + self-hosted)      12h
├── 1.8  Dev/staging environment setup                       8h
└── 1.9  Contract tests (Schemathesis)                       8h

Phase 2: ProcessBot Core (Week 3-4) — 80h
├── 2.1  Vision endpoint POST /generate (image)            16h
├── 2.2  Image preprocessing pipeline (4-tier quality)      12h
├── 2.3  AI Router integration (model selection)            8h
├── 2.4  Vision prompt engineering + testing                 8h
├── 2.5  Block matching (fuzzy, catalog)                     8h
├── 2.6  Auto-layout (Dagre algorithm)                       8h
├── 2.7  Billing middleware (credits check + deduction)      8h
├── 2.8  Streaming billing integration                       4h
└── 2.9  Error handling (all HTTP codes)                     8h

Phase 3: Frontend Integration (Week 5) — 40h
├── 3.1  Upload UI + preview in FlowEditor                  12h
├── 3.2  Iterative generation UX (multi-pass, diff view)     8h
├── 3.3  Billing UI (credit balance, upgrade prompt)         8h
├── 3.4  Deploy button + modal in Vela                       8h
└── 3.5  Error states + loading skeletons                    4h

Phase 4: Deploy Bridge (Week 5-6) — 40h
├── 4.1  DeployService (validate + create tenant)           12h
├── 4.2  SAGA orchestrator (8 steps + compensation)         12h
├── 4.3  Process seeding (blocks, pages, channels)           8h
└── 4.4  Instance manager UI (status, update, delete)        8h

Phase 5: Polish + Ship (Week 6) — 40h
├── 5.1  Observability (logs, metrics, traces)              12h
├── 5.2  Accuracy benchmark suite                             8h
├── 5.3  Dataset collection + labeling (10 samples initial)   8h
├── 5.4  Documentation (API docs, user guide)                8h
└── 5.5  Security review + threat model validation            4h
```

### A.2 Dependency Graph (Critical Path)

```
                    ┌─────────────────┐
                    │ 1.1 PG Migration│ (16h)
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
         │1.2 Auth │   │1.4 M2M  │   │1.7 CI/CD│
         │  (8h)   │   │  (12h)  │   │  (12h)  │
         └────┬────┘   └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │ 2.1 Vision API  │ (16h) ────── CRITICAL PATH
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
         │2.2 Prepr│   │2.3 Route│   │2.5 Match│
         │  (12h)  │   │  (8h)   │   │  (8h)   │
         └────┬────┘   └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │ 3.1 Upload UI   │ (12h)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 4.1 Deploy Svc  │ (12h)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ 5.2 Benchmarks  │ (8h)
                    └─────────────────┘

CRITICAL PATH: 1.1 → 1.2/1.4 → 2.1 → 3.1 → 4.1 → 5.2 = 76h
SLACK on non-critical tasks: 149h

Parallelization possible:
- 2.2, 2.3, 2.5 can run in parallel (different devs)
- 1.7, 1.8 (CI/CD + env) parallel to everything
- 3.2, 3.3, 3.4 (UI) can run in parallel
- Phase 5 items parallel to deploy bridge
```

### A.3 Staffing Model

| Scenario | Devs | Duration | Weekly Cost (est) |
|----------|------|----------|-------------------|
| Solo developer | 1 | 11 weeks | $400 (local) |
| Pair (recommended) | 2 | 6 weeks | $800 (local) |
| Small team | 3 | 4 weeks | $1,200 (local) |

---

## Section B: Runbook — Incident Response

### B.1 ProcessBot Vision Returns Garbage

**Symptom:** Users report nonsensical process definitions from photos.

**Triage:**
```bash
# 1. Check AI model availability
curl -s http://localhost:8000/api/v1/health/ai | jq .

# 2. Check recent generation errors
docker compose logs backend | grep "processbot.*error" | tail -20

# 3. Check if model was changed/updated recently
git log --oneline --since="24 hours ago" -- aether/backend/app/services/ai/

# 4. Run accuracy benchmark
python -m benchmarks.vision_accuracy --samples 10
```

**Actions:**
1. If accuracy < 60%: **IMMEDIATE ROLLBACK** of model/prompt changes
2. If model is down: AI Router should auto-fallback to GPT-4V (check: `ai_router_fallback_total` metric)
3. If prompt was changed: revert to last known-good prompt version (stored in `block_types.prompt_version`)
4. Notify users via status page: "ProcessBot испытывает временные трудности с распознаванием"
5. Post-mortem: why did this reach production? Where was the accuracy gate?

### B.2 Deploy Partially Fails (SAGA Compensation Error)

**Symptom:** Alert: `CRITICAL: deploy_compensation_failed for tenant <uuid>`

**Triage:**
```bash
# 1. Check deploy status
curl -H "Authorization: Bearer $M2M_TOKEN" \
  http://localhost:8000/api/v1/deploy/status/$TENANT_ID | jq .

# 2. Check which step failed
docker compose logs backend | grep "deploy.*$TENANT_ID" | grep -E "failed|compensat"

# 3. Check what resources were created (orphaned?)
psql $AETHER_DB -c "
  SELECT * FROM tenants WHERE id = '$TENANT_ID';
  SELECT * FROM subscriptions WHERE tenant_id = '$TENANT_ID';
  SELECT * FROM channels WHERE tenant_id = '$TENANT_ID';
"
```

**Actions:**
1. If tenant exists but subscription doesn't → manual cleanup: `DELETE FROM tenants WHERE id = '$TENANT_ID'`
2. If channels configured but not in Redis → `redis-cli KEYS "tenant:$TENANT_ID:*" | xargs redis-cli DEL`
3. If uncertain → mark tenant as "zombie", file cleanup ticket for next business day
4. Re-run deploy after fixing root cause
5. Post-mortem: add specific compensation for the failing step

### B.3 M2M Key Compromised

**Symptom:** Security alert or suspicious deploy activity.

**Actions (IMMEDIATE — <5 minutes):**
```bash
# 1. EMERGENCY KEY ROTATION
python -m scripts.rotate_m2m_key --emergency

# 2. Verify old key is revoked
curl -H "Authorization: Bearer $OLD_M2M_TOKEN" \
  http://localhost:8000/api/v1/deploy/status/any-id
# Must return 401

# 3. Update Vela's key
ssh vela-host "echo 'AETHER_M2M_SECRET=new-key' >> .env && docker compose restart vela"

# 4. Audit: list all deploys in last 24h
python -m scripts.audit_deploys --since "24h" --output audit-report.json

# 5. If malicious deploys found → suspend affected tenants, notify admins
```

### B.4 Credit Exhaustion Attack

**Symptom:** Single tenant consuming >1000 credits/hour (normal: 10-50/hour)

**Actions:**
```bash
# 1. Identify tenant
curl http://localhost:8000/api/v1/admin/metrics/credits?limit=10 | jq '.top_consumers'

# 2. Check if legitimate (enterprise client doing bulk import) or abuse
# Look at input diversity: same image uploaded 500 times = abuse

# 3. Rate limit (temporary)
curl -X POST http://localhost:8000/api/v1/admin/tenants/$TENANT_ID/limits \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"limit_key": "processbot_daily_credits", "hard_limit": 200}'

# 4. Notify tenant: "Ваш лимит генераций повышен. Для продолжения обновите тариф."
```

---

## Section C: Acceptance Criteria (Definition of Done)

### C.1 ProcessBot Vision — Acceptance Criteria

```
☐ ACC-01: Photo of clean digital diagram → ProcessDefinition with ≥85% block accuracy
☐ ACC-02: Photo of whiteboard (good lighting) → ProcessDefinition with ≥75% block accuracy
☐ ACC-03: Unusable image (dark, blurry, no diagram) → HTTP 422 with Russian guidance text
☐ ACC-04: Image with >50 blocks → HTTP 422 with suggestion to split
☐ ACC-05: 5MB JPEG → processed <10 seconds (p95)
☐ ACC-06: Generation with 0 credits → HTTP 402 + upgrade URL
☐ ACC-07: All generated blocks matched to BlockType catalog (unmatched = warning)
☐ ACC-08: Auto-layout produces no overlapping blocks
☐ ACC-09: End-to-end: upload → preview → edit → save in FlowEditor
☐ ACC-10: Streaming billing records exact token counts (±5%)
☐ ACC-11: Handwritten Russian text → OCR fallback chain (digital → handwriting → flag)
☐ ACC-12: Face in uploaded photo → redacted before processing (if enabled)
☐ ACC-13: EXIF metadata stripped from uploaded images
☐ ACC-14: Images deleted after processing (not stored)
☐ ACC-15: Generation timeout (30s) → HTTP 503 with fallback model info
```

### C.2 Deploy Bridge — Acceptance Criteria

```
☐ ACC-16: Valid manifest → tenant created, provisioned, process seeded <60 seconds
☐ ACC-17: Invalid manifest → HTTP 400 with field-level errors
☐ ACC-18: Duplicate slug → HTTP 409 with suggestions
☐ ACC-19: Deploy fails at step 5/8 → steps 1-4 compensated (no orphan resources)
☐ ACC-20: Compensation fails → CRITICAL alert within 30 seconds
☐ ACC-21: GET /deploy/status → accurate health, version, page count
☐ ACC-22: POST /deploy/update → migrates data with dual-write strategy
☐ ACC-23: DELETE /deploy → soft delete, retention period, reactivation possible
☐ ACC-24: M2M token expired → HTTP 401, not 500
☐ ACC-25: M2M token wrong scope → HTTP 403 with required scope
☐ ACC-26: JTI replay → HTTP 401 (anti-replay working)
☐ ACC-27: Deploy with 100 blocks → succeeds (no arbitrary block limit)
```

### C.3 Observability — Acceptance Criteria

```
☐ ACC-28: All ProcessBot generations logged with tenant_id, model, tokens, duration
☐ ACC-29: Prometheus metrics: generations_total, duration_seconds, credits_consumed
☐ ACC-30: Grafana dashboard shows: active instances, generation latency, model usage
☐ ACC-31: OpenTelemetry spans for: generate → vision → block_match → auto_layout
☐ ACC-32: Alert fires when: p95 latency > 10s for 5min, error rate > 5% for 5min
☐ ACC-33: Alert fires when: deploy compensation fails
```

---

## Section D: Environment Configuration

### D.1 Environment Matrix

| Setting | dev | staging | prod |
|---------|-----|---------|------|
| **Aether DB** | PostgreSQL in Docker (port 5432) | PostgreSQL in Docker | Managed PG / separate VM |
| **Redis** | Docker (port 6379) | Docker | Separate VM / ElastiCache |
| **Vela DB** | PostgreSQL in Docker (port 5433) | Same as Aether PG, different DB name | Same as prod Aether |
| **AI — NLP** | Qwen 35B local (:8085) | Qwen 35B local | Qwen 35B local |
| **AI — Vision** | DeepSeek V4 Pro API | DeepSeek V4 Pro API | DeepSeek V4 Pro API |
| **File storage** | Local `/tmp/vela-uploads` | MinIO (S3-compatible) | MinIO / S3 |
| **Logs** | stdout (JSON) | stdout → Loki | stdout → Loki |
| **Metrics** | Prometheus (Docker) | Prometheus | Prometheus + Grafana |
| **Traces** | Jaeger (Docker) | Jaeger | Jaeger / Grafana Tempo |
| **CI/CD** | GitHub Actions + self-hosted runner | Same | Same |
| **SSL** | None | Self-signed | Let's Encrypt / commercial |
| **Backups** | None | Daily PG dump | Hourly PG dump + WAL archiving |

### D.2 Environment Variables

```bash
# === Aether Backend ===
AETHER_DATABASE_URL=postgresql+asyncpg://aether:aether_dev@localhost:5432/aether
AETHER_REDIS_URL=redis://localhost:6379/0
AETHER_JWT_SECRET_KEY=<generate-256bit>
AETHER_JWT_ALGORITHM=HS256
AETHER_ENCRYPTION_KEY=<generate-256bit>
AETHER_M2M_SECRET=<generate-256bit>
AETHER_ENVIRONMENT=development  # development|staging|production
AETHER_CORS_ORIGINS=["http://localhost:5173","http://localhost:5176"]
AETHER_LOG_LEVEL=DEBUG  # DEBUG|INFO|WARNING|ERROR
AETHER_METRICS_ENABLED=true
AETHER_TRACING_ENABLED=false  # true in staging/prod
AETHER_DEEPSEEK_API_KEY=<from RouterAI>
AETHER_DEEPSEEK_API_URL=https://api.routerai.ai/v1

# === Vela Backend ===
VELA_DATABASE_URL=postgresql+asyncpg://vela:vela_dev@localhost:5433/vela
VELA_AETHER_API_URL=http://localhost:8000/api/v1
VELA_AETHER_M2M_SECRET=<same as AETHER_M2M_SECRET>
VELA_JWT_SECRET_KEY=<same as AETHER_JWT_SECRET_KEY>  # Shared for auth
VELA_ENVIRONMENT=development
VELA_UPLOAD_DIR=/tmp/vela-uploads
VELA_MAX_UPLOAD_SIZE_MB=10
```

### D.3 Docker Compose Dev (Full Stack)

```yaml
# docker-compose.dev.yml — full development stack
services:
  # Aether infrastructure
  aether-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: aether
      POSTGRES_PASSWORD: aether_dev
      POSTGRES_DB: aether
    ports: ["5432:5432"]

  aether-redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  # Vela infrastructure (separate DB for development)
  vela-postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: vela
      POSTGRES_PASSWORD: vela_dev
      POSTGRES_DB: vela
    ports: ["5433:5432"]

  # Observability
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
    volumes: ["./infra/prometheus.yml:/etc/prometheus/prometheus.yml"]

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin

  jaeger:
    image: jaegertracing/all-in-one
    ports: ["16686:16686", "4317:4317"]

  # Local AI (Qwen 35B)
  llama-server:
    image: ghcr.io/ggerganov/llama.cpp:server
    command: [
      "-m", "/models/Qwen3.6-35B-A3B-APEX-I-Quality.gguf",
      "--host", "0.0.0.0", "--port", "8085",
      "--ctx-size", "131072", "--cache-ram", "14336",
      "-ngl", "99"
    ]
    ports: ["8085:8085"]
    volumes: ["/mnt/models_big:/models"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["1"]  # RTX 3090
```

---

## Section E: v1 Scope Boundaries (What We Are NOT Doing)

### E.1 Explicitly Excluded from v1

| Feature | Reason for Exclusion | Target Version |
|---------|---------------------|----------------|
| NLP text-to-process | Higher priority: vision pipeline proves the concept visually | v1.1 |
| Events-to-process (Logicore mining) | Requires stable Logicore API + event schema | v1.2 |
| Block marketplace (public) | Needs moderation, payment splitting, review system | v2.0 |
| White-label Velas (Level 2-3 reflexivity) | Premature without 50+ paying tenants | v2.0 |
| Custom block type builder (visual) | Block types created in Python for v1 | v1.1 |
| OAuth2/SSO for tenants | Passwordless magic link is sufficient for MVP | v1.1 |
| Custom domains with auto-SSL | Significant DevOps complexity | v2.0 |
| Mobile app (Capacitor) | Web responsive is sufficient for v1 | v2.0 |
| Multi-language UI (English) | Russian-first market, add English when proven | v1.1 |
| Process simulation/testing mode | Nice to have, not MVP-critical | v1.2 |
| Automated process optimization suggestions | Requires data from live instances first | v2.0 |
| Blockchain audit trail | Overengineering for current needs | v3.0 |

### E.2 Known Technical Debt (Accepted for v1)

| Item | Risk | Mitigation |
|------|------|------------|
| M2M: symmetric key (HS256) not asymmetric (RS256) | Key compromise = full access | 5min TTL, jti anti-replay, emergency rotation runbook |
| No message queue for async deploys | Deploy blocks HTTP request for 30-60s | Acceptable for v1 (<100 tenants). Add Celery in v1.1 |
| OCR: no custom TrOCR model for Russian handwriting | Lower accuracy on handwritten text | Flag for manual input, collect data to train model later |
| No A/B testing framework for ProcessBot prompts | Can't scientifically improve prompts | Manual prompt versioning in DB, track accuracy per version |
| Single region deployment | No geo-redundancy | Daily backups, acceptable for B2B Russian market |
| No WebApplication Firewall (WAF) | DDoS protection gap | Cloudflare free tier for prod (when domain is set up) |

### E.3 Migration Path to v1.1+

```
v1.0: Vision ProcessBot + Deploy Bridge (MVP)
  └─ v1.1: NLP text-to-process + custom block types + English UI
      └─ v1.2: Events mining + process simulation + async deploys (Celery)
          └─ v2.0: Block marketplace + white-label + custom domains + mobile
```

---

## Section F: Post-Launch Checklist

```
WEEK 1 (Monitoring):
☐ All Prometheus metrics reporting
☐ All Grafana panels rendering
☐ Alert rules tested (triggered intentionally)
☐ First real user generation — verify full flow in logs
☐ Backup verified: restore from backup to clean instance

WEEK 2 (Stabilization):
☐ Top 5 errors from logs → fix or add to known issues
☐ Accuracy benchmark: compare real user results to test dataset
☐ User feedback: first 10 users surveyed
☐ Performance: p95 latency < targets?
☐ Billing: first real credit deductions verified

WEEK 4 (Growth):
☐ Conversion funnel: signup → first generation → saved process → deploy?
☐ Where do users drop off? Add instrumentation if missing
☐ First paying customer?
☐ Iteration on prompts based on real accuracy data

MONTH 3 (Scale):
☐ >50 active tenants?
☐ M2M key rotated at least once (proving rotation procedure works)
☐ First process version migration done (v1→v2 with live data)
☐ Decision: start v1.1 or continue stabilizing v1.0?
```
