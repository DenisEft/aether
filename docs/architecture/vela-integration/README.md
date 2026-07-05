# Vela Integration — Document Index

**Package:** `docs/architecture/vela-integration/`
**Created:** 2026-07-05 | **Updated:** 2026-07-05 (v3.0 — operational readiness)
**Status:** Draft — pending review
**Total:** 8 documents, ~4,700 lines, ~144KB + OpenAPI contract

---

## Documents

| # | Document | Description | Lines |
|---|----------|-------------|-------|
| 1 | [`01-ecosystem-vision.md`](./01-ecosystem-vision.md) | Ecosystem vision, architecture, gap analysis, revenue model | 306 |
| 2 | [`02-processbot-spec.md`](./02-processbot-spec.md) | ProcessBot AI: API, vision/NLP pipelines, billing, errors | 584 |
| 3 | [`03-deploy-bridge.md`](./03-deploy-bridge.md) | Vela→Aether deploy: manifest, API, auth, DB migration | 712 |
| 4 | [`04-critical-additions.md`](./04-critical-additions.md) | Sequence diagrams, poor-image strategy, SAGA, tests, COGS, threat model | 649 |
| 5 | [`05-advanced-production.md`](./05-advanced-production.md) | KPIs, iterative gen, data migration, observability, reflexivity, marketplace, competitors | 812 |
| 6 | [`06-adr.md`](./06-adr.md) | **NEW** Architecture Decision Records — 8 decisions with context, alternatives, consequences | 320 |
| 7 | [`07-operations.md`](./07-operations.md) | **NEW** Effort estimates (225h), runbook, acceptance criteria (33 items), env config, v1 scope boundaries, post-launch checklist | 470 |
| 8 | [`openapi.yaml`](./openapi.yaml) | OpenAPI 3.1 contract — 8 endpoints, 30+ schemas | 877 |

## Document Purpose Matrix

| If you need to... | Read |
|-------------------|------|
| Understand the big picture | `01` |
| See the API contract | `openapi.yaml` |
| Implement ProcessBot | `02` + `04` (image quality section) |
| Implement Deploy Bridge | `03` + `04` (SAGA section) |
| Understand architectural decisions | `06` |
| Estimate effort or plan sprint | `07` Section A |
| Handle production incidents | `07` Section B |
| Know when something is "done" | `07` Section C |
| Set up dev/staging/prod | `07` Section D |
| Push back on scope creep | `07` Section E |
| Launch checklist | `07` Section F |
| Monitor production | `05` Section 11 |
| Understand business model | `01` + `05` Section 8 |
| Compare to competitors | `05` Section 14 |

## Coverage Map (28 Concerns × 8 Documents)

| Concern | 01 | 02 | 03 | 04 | 05 | 06 | 07 | API |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|
| Architecture vision | ✅ | | | | | ✅ | | |
| Revenue & COGS | ✅ | | | ✅ | ✅ | | | |
| Gap analysis | ✅ | | | | | | | |
| ProcessBot API | | ✅ | | | | | | ✅ |
| Vision pipeline | | ✅ | | ✅ | ✅ | | | |
| NLP pipeline | | ✅ | | | | | | |
| Block matching | | ✅ | | | | | | |
| Auto-layout | | ✅ | | | | | | |
| Billing integration | | ✅ | | | | | | ✅ |
| Deploy manifest | | | ✅ | | | | | ✅ |
| DeployService | | | ✅ | | | | | |
| M2M auth | | | ✅ | ✅ | | ✅ | | |
| DB migration | | | ✅ | | | | | |
| Sequence diagrams | | | | ✅ | | | | |
| Poor image strategy | | | | ✅ | | | | |
| SAGA recovery | | | | ✅ | | | | |
| Test strategy | | | | ✅ | | | | |
| Threat model | | | | ✅ | | | | |
| Business KPIs | | | | | ✅ | | | |
| Iterative generation | | | | | ✅ | | | |
| Data migration | | | | | ✅ | | | |
| Observability | | | | | ✅ | | | |
| Reflexivity | | | | | ✅ | | | |
| Block versioning | | | | | ✅ | | | |
| Marketplace | | | | | ✅ | | | |
| Competitors | | | | | ✅ | | | |
| ADRs | | | | | | ✅ | | |
| Effort estimates | | | | | | | ✅ | |
| Runbook | | | | | | | ✅ | |
| Acceptance criteria | | | | | | | ✅ | |
| Env config | | | | | | | ✅ | |
| v1 scope boundaries | | | | | | | ✅ | |
| Post-launch | | | | | | | ✅ | |

## Key Numbers

| Metric | Value |
|--------|-------|
| **Total effort** | 225 hours (~6 weeks, 2 devs) |
| **Critical path** | 76 hours |
| **Break-even** | 16 Pro subscribers ($150/mo infrastructure) |
| **Gross margin** | 97-98% on AI features |
| **Acceptance criteria** | 33 items across ProcessBot, Deploy, Observability |
| **ADR decisions** | 8 (framework, pricing, auth, models, SAGA, grid, RLS, monolith) |
| **Production alerts** | 4 (latency, errors, compensation failure, key compromise) |
| **v1 excluded features** | 12 (explicitly scoped out) |

## Next Action

Review → approve → begin Phase 1 execution:
1. `07-operations.md` Section A — sprint plan
2. `06-adr.md` — decisions ratified
3. `openapi.yaml` → code generation
