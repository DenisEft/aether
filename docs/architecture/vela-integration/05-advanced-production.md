# Vela Integration — Advanced Production Concerns

> **Version:** 2.0 — Second improvement pass
> **Covers:** Metrics, iterative generation, data migration, observability, reflexivity, competitive positioning, block evolution

---

## Gap 8: Business KPIs & Success Metrics

### 8.1 Pirate Metrics (AARRR) for Vela

| Stage | Metric | Target (6mo) | Measurement |
|-------|--------|-------------|-------------|
| **Acquisition** | New Vela signups/week | 20 | Auth events |
| **Activation** | Users who generate first process | ≥60% | First ProcessBot call within 7d |
| **Retention** | WAU/MAU | ≥40% | Active sessions/week |
| **Revenue** | MRR | $500/mo | Stripe/billing events |
| **Referral** | Viral coefficient | ≥0.3 | Invite links used |

### 8.2 ProcessBot-Specific KPIs

| Metric | Target | Why |
|--------|--------|-----|
| Vision→Process accuracy (blocks) | ≥85% | Below this, users don't trust the AI |
| Time-to-process (manual vs AI) | 3x faster | Core value prop |
| First-try acceptance rate | ≥60% | Users save AI output without major edits |
| Iterations-to-accept | ≤2 | Average corrections before saving |
| Credits utilization (Pro tier) | ≥70% | Users find AI valuable enough to use credits |
| Pro→Enterprise upgrade rate | ≥15% | Enterprise is where the money is |

### 8.3 AARRR Funnel Dashboard (SQL)

```sql
-- Weekly cohort analysis for Vela
WITH cohort AS (
    SELECT
        date_trunc('week', created_at) AS cohort_week,
        tenant_id,
        -- Activation: generated process within 7 days
        EXISTS(
            SELECT 1 FROM process_definitions
            WHERE tenant_id = t.id
              AND created_at <= t.created_at + INTERVAL '7 days'
              AND source = 'processbot'
        ) AS activated,
        -- Retention: active in week N
        ...
    FROM tenants t
    WHERE created_at >= NOW() - INTERVAL '6 months'
)
SELECT
    cohort_week,
    COUNT(*) AS signups,
    ROUND(100.0 * SUM(CASE WHEN activated THEN 1 ELSE 0 END) / COUNT(*), 1) AS activation_pct,
    ...
FROM cohort
GROUP BY cohort_week
ORDER BY cohort_week;
```

---

## Gap 9: Iterative Generation — Multi-Pass Vision Refinement

### 9.1 The Problem

User uploads photo → gets 70% accuracy → manually fixes 5 blocks → uploads a better photo of the same diagram.

**Naive:** Discard first result, generate from scratch. Loses user's manual fixes.

**Smart:** Merge: keep user's manual fixes, re-run vision only on what changed.

### 9.2 Iterative Generation Protocol

```python
@dataclass
class IterativeGenerationContext:
    """Tracks state across multiple generation attempts."""
    session_id: str
    process_definition_id: str | None  # Once saved
    attempts: list[GenerationAttempt]
    user_edits: list[UserEdit]         # Manual changes after AI generation
    merged_state: ProcessDefinition     # Current merged state (AI + user edits)

@dataclass
class GenerationAttempt:
    attempt_number: int
    input_type: str                    # "image_v1", "image_v2" (better photo)
    model_used: str
    raw_output: ProcessDefinition      # Pure AI output
    confidence_scores: dict[str, float] # Per-block confidence
    user_actions: list[str]            # "accepted", "edited", "rejected"

async def iterative_generate(
    ctx: IterativeGenerationContext,
    new_input: bytes
) -> ProcessDefinition:
    """Smart merge: re-run vision, preserve user edits."""

    # 1. Run vision on new image
    new_result = await processbot_vision_pipeline(new_input)

    # 2. Diff: which blocks changed between old AI output and new AI output?
    diff = compute_process_diff(
        old=ctx.attempts[-1].raw_output,
        new=new_result
    )

    # 3. For each changed block, check if user had edited it
    merged = copy.deepcopy(ctx.merged_state)

    for block_diff in diff.changed_blocks:
        user_edited = any(
            edit.block_id == block_diff.id
            for edit in ctx.user_edits
        )

        if user_edited:
            # User explicitly changed this — keep their version
            logger.info(f"Block {block_diff.id}: keeping user edit over AI update")
            continue
        else:
            # User didn't touch it — accept AI improvement
            merged.update_block(block_diff.id, block_diff.new_version)

    # 4. For new blocks (AI found something it previously missed):
    for new_block in diff.added_blocks:
        confidence = new_result.confidence_scores.get(new_block.id, 0.0)
        if confidence > 0.7:
            merged.add_block(new_block, position="suggested")
        else:
            merged.add_block(new_block, position="pending_review")

    # 5. Record attempt
    ctx.attempts.append(GenerationAttempt(
        attempt_number=len(ctx.attempts) + 1,
        input_type="image_v2",
        model_used=new_result.model_used,
        raw_output=new_result,
        confidence_scores=new_result.confidence_scores,
    ))

    return merged


@dataclass
class ProcessDiff:
    changed_blocks: list[BlockChange]
    added_blocks: list[ProcessBlock]
    removed_blocks: list[str]          # Block IDs
    changed_connections: list[ConnectionChange]


def compute_process_diff(
    old: ProcessDefinition,
    new: ProcessDefinition
) -> ProcessDiff:
    """Compute semantic diff between two process definitions."""
    old_blocks = {b.key: b for b in old.blocks}
    new_blocks = {b.key: b for b in new.blocks}

    changed = []
    added = []
    removed = []

    for key, new_block in new_blocks.items():
        if key not in old_blocks:
            added.append(new_block)
        elif not blocks_equal(old_blocks[key], new_block):
            changed.append(BlockChange(
                id=key,
                old_version=old_blocks[key],
                new_version=new_block,
                changed_fields=diff_fields(old_blocks[key], new_block)
            ))

    for key in old_blocks:
        if key not in new_blocks:
            removed.append(key)

    return ProcessDiff(
        changed_blocks=changed,
        added_blocks=added,
        removed_blocks=removed,
        changed_connections=diff_connections(old.connections, new.connections),
    )
```

### 9.3 UX for Iterative Generation

```
┌──────────────────────────────────────────────────────────────────┐
│  🤖 ProcessBot — Попытка #2                                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  📸 Новое фото обработано                                 │   │
│  │                                                          │   │
│  │  Найдено изменений:                                       │   │
│  │  ✅ "Проверка накладной" — улучшено (AI), было 60%→92%   │   │
│  │  🔒 "Отправка уведомления" — сохранено (ваша правка)     │   │
│  │  🆕 "Возврат поставщику" — новый блок (добавить?)       │   │
│  │  ⚠️ "Согласование" — удалено из новой версии (удалить?) │   │
│  │                                                          │   │
│  │  Ваши ручные правки (#3 блока) сохранены.                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [Принять все AI изменения]  [Выбрать вручную]  [Отмена]       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Gap 10: Data Migration Strategy — Process Version Updates

### 10.1 The Problem

Vela updates a process from v1 to v2. But tenants have 500 active process instances running on v1. Those instances have data in v1's block fields. v2 changed some fields — added one, removed another, renamed a third.

### 10.2 Migration Strategies

```python
class MigrationStrategy(Enum):
    AUTO = "auto"          # Try automatic migration, flag issues
    MANUAL = "manual"      # Admin provides migration script
    DRY_RUN = "dry_run"    # Validate, don't execute
    DUAL_WRITE = "dual_write"  # Both versions active during migration window


@dataclass
class FieldMigration:
    """Describes a field change between process versions."""
    block_key: str
    field_key: str
    change_type: str  # "added", "removed", "renamed", "type_changed", "required_changed"
    old_value: Any | None = None
    new_value: Any | None = None
    migration_fn: str | None = None  # Python expression for complex migrations


async def plan_migration(
    old_version: ProcessDefinition,
    new_version: ProcessDefinition,
    strategy: MigrationStrategy
) -> MigrationPlan:
    """Analyze what changed and plan data migration."""

    changes = compute_field_changes(old_version, new_version)

    plan = MigrationPlan(
        source_version=old_version.version,
        target_version=new_version.version,
        affected_blocks=set(c.block_key for c in changes),
        estimated_instances=await count_active_instances(old_version.id),
        changes=changes,
    )

    for change in changes:
        if change.change_type == "removed":
            plan.warnings.append(
                f"Поле '{change.field_key}' удалено. "
                f"Данные будут сохранены в audit_log на 90 дней."
            )
        elif change.change_type == "renamed":
            plan.auto_migrations.append(
                AutoMigration(
                    field=change.field_key,
                    action="rename",
                    from_name=change.old_value,
                    to_name=change.new_value,
                )
            )
        elif change.change_type == "added" and change.new_value:
            plan.auto_migrations.append(
                AutoMigration(
                    field=change.field_key,
                    action="set_default",
                    default_value=change.new_value,
                )
            )
        elif change.change_type == "type_changed":
            plan.requires_manual_review.append(change)

    return plan


async def execute_migration(plan: MigrationPlan, strategy: MigrationStrategy):
    """Execute migration with rollback capability."""

    if strategy == MigrationStrategy.DRY_RUN:
        return await validate_migration(plan)

    if strategy == MigrationStrategy.DUAL_WRITE:
        # Phase 1: Start writing to both v1 and v2 schemas
        await enable_dual_write(plan)
        # Phase 2: Backfill v2 from v1 data
        await backfill_v2_data(plan)
        # Phase 3: Switch reads to v2
        await switch_reads_to_v2(plan)
        # Phase 4: Stop v1 writes
        await disable_v1_writes(plan)
        return

    # AUTO or MANUAL
    snapshot = await create_pre_migration_snapshot(plan)

    try:
        for migration in plan.auto_migrations:
            await migration.execute()

        if strategy == MigrationStrategy.MANUAL:
            await plan.manual_script.execute()

        await verify_migration(plan)

    except MigrationError as e:
        logger.error(f"Migration failed: {e}")
        await rollback_migration(snapshot)
        raise
```

### 10.3 Migration UI in Vela

```
┌──────────────────────────────────────────────────────────────────┐
│  🔄 Обновление процесса "Логистика" v1 → v2                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Анализ изменений                                        │   │
│  │                                                          │   │
│  │  Поля:                                                   │   │
│  │  ✅ "номер_накладной" → "tracking_number" (авто)        │   │
│  │  ✅ "дата_доставки" — новый тип Date (авто)             │   │
│  │  🟡 "ответственный" — удалено (архивируется)            │   │
│  │  🔴 "сумма_ндс" — тип изменён (ручная проверка)         │   │
│  │                                                          │   │
│  │  Затронуто: 147 активных заявок                          │   │
│  │  Ожидаемое время миграции: ~30 сек                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Стратегия:                                                      │
│  ○ Dry Run — проверить без изменений                            │
│  ● Dual Write — без даунтайма (рекомендуется)                  │
│  ○ Auto — автоматически (если нет 🔴 полей)                    │
│                                                                  │
│  [Отмена]                           [🔄 Начать миграцию]        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Gap 11: Observability — Production Monitoring

### 11.1 Three Pillars

```
                        OBSERVABILITY
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │  LOGS   │          │ METRICS │          │ TRACES  │
   │         │          │         │          │         │
   │ Struct. │          │ Prometh.│          │ Jaeger  │
   │ JSON    │          │ counters│          │ spans   │
   │ via     │          │ histogr.│          │ across  │
   │ stdout  │          │ gauges  │          │ services│
   └─────────┘          └─────────┘          └─────────┘
```

### 11.2 Structured Logging

```python
# aether/backend/app/core/logging_config.py

import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Usage
logger = structlog.get_logger()

# Every log has tenant context automatically
logger.info(
    "processbot.generation.started",
    tenant_id=str(ctx.tenant_id),
    input_type="image",
    image_size_bytes=len(image_data),
    model="deepseek-v4-pro",
    attempt_number=ctx.attempt_count,
)

# Key events logged:
# - processbot.generation.{started,completed,failed}
# - deploy.{started,step_completed,compensating,completed,failed}
# - migration.{planned,started,step_executed,verified,rolled_back}
# - billing.{credit_check,deduction,insufficient,refund}
# - security.{m2m_auth_success,m2m_auth_failed,key_rotated}
```

### 11.3 Prometheus Metrics

```python
# aether/backend/app/core/metrics.py

from prometheus_client import Counter, Histogram, Gauge, Info

# ── ProcessBot ──
processbot_generations_total = Counter(
    "vela_processbot_generations_total",
    "Total ProcessBot generation requests",
    ["input_type", "model", "status"],  # status: success|failed|rejected
)

processbot_generation_duration_seconds = Histogram(
    "vela_processbot_generation_duration_seconds",
    "ProcessBot generation latency",
    ["input_type", "model"],
    buckets=[1, 2, 5, 10, 15, 30, 60],
)

processbot_credit_consumption = Counter(
    "vela_processbot_credits_total",
    "Total credits consumed",
    ["tenant_tier"],
)

processbot_accuracy = Gauge(
    "vela_processbot_block_accuracy",
    "Current accuracy rate from user feedback (per day)",
    ["input_type"],
)

# ── Deploy ──
deploy_total = Counter(
    "vela_deploy_total",
    "Total deploys",
    ["status"],  #: deployed|failed|rolled_back
)

deploy_duration_seconds = Histogram(
    "vela_deploy_duration_seconds",
    "Deploy duration",
    buckets=[5, 10, 30, 60, 120, 300],
)

active_instances = Gauge(
    "vela_active_instances",
    "Currently active Aether instances",
    ["tier"],
)

# ── Business ──
mrr_usd = Gauge(
    "vela_mrr_usd",
    "Monthly recurring revenue",
)

trial_conversion_rate = Gauge(
    "vela_trial_conversion_rate",
    "Trial → paid conversion rate (7-day rolling)",
)

# ── AI Router ──
ai_router_model_usage = Counter(
    "vela_ai_router_model_usage_total",
    "Model selection count",
    ["model", "reason"],  # reason: cheapest|fastest|fallback|user_preference
)

ai_router_cost_saved = Counter(
    "vela_ai_router_cost_saved_usd_total",
    "Estimated USD saved by using local models over cloud",
)
```

### 11.4 Distributed Tracing

```python
# OpenTelemetry spans across Vela → AI Router → Aether Deploy

# Span: ProcessBot Generation
with tracer.start_as_current_span("processbot.generate") as span:
    span.set_attribute("input_type", "image")
    span.set_attribute("tenant.id", str(ctx.tenant_id))

    # Sub-span: Vision Call
    with tracer.start_as_current_span("processbot.vision.inference") as vision_span:
        vision_span.set_attribute("model", "deepseek-v4-pro")
        vision_span.set_attribute("tokens.input", 1250)
        result = await call_vision_model(image)
        vision_span.set_attribute("tokens.output", result.tokens_output)

    # Sub-span: Block Matching
    with tracer.start_as_current_span("processbot.block_matching") as match_span:
        match_span.set_attribute("blocks.detected", len(result.blocks))
        matched = await match_blocks_to_catalog(result.blocks)
        match_span.set_attribute("blocks.matched", len(matched))

    # Sub-span: Auto-layout
    with tracer.start_as_current_span("processbot.auto_layout") as layout_span:
        await auto_layout(matched)
        layout_span.set_attribute("layout.algorithm", "dagre")

# W3C Trace Context propagated via HTTP headers:
# traceparent: 00-{trace_id}-{span_id}-01
```

### 11.5 Grafana Dashboard Sketch

```
┌──────────────────────────────────────────────────────────────────┐
│  VELA — Production Dashboard                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────┐│
│  │ Active       │ │ Generations  │ │ MRR          │ │ Errors  ││
│  │ Instances    │ │ Today        │ │              │ │ Rate    ││
│  │     12       │ │     47       │ │   $188.70    │ │  2.3%   ││
│  │  ↑3 this wk  │ │  ↑12 vs yday │ │  ↑$30 vs Jun │ │  ↓0.5%  ││
│  └──────────────┘ └──────────────┘ └──────────────┘ └─────────┘│
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Generation Latency (p50, p95, p99) — 24h               │   │
│  │  ▁▁▁▂▂▂▃▃▃▅▅▅▃▃▃▂▂▂▁▁▁▁▁▁▂▂▂▃▃▃▃▃▅▅▅▇▇▇▂▂▂              │   │
│  │  00  02  04  06  08  10  12  14  16  18  20  22          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────┐ ┌──────────────────────────────┐  │
│  │  Model Usage (24h)       │ │  Credit Consumption by Tier  │  │
│  │  ████████████ Qwen local │ │  Pro ██████████ 320 credits  │  │
│  │  ████ DeepSeek cloud     │ │  Ent ██████████████ 580 cr   │  │
│  │  █ GPT-4V (fallback)     │ │  Free ▌ 0 credits           │  │
│  └──────────────────────────┘ └──────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Recent Deploys                                          │   │
│  │  ✅ coalstar-logistics    v3    2026-07-05 03:15:00Z    │   │
│  │  ✅ mtk-procurement       v1    2026-07-05 02:45:00Z    │   │
│  │  ❌ test-tenant           v1    2026-07-05 02:30:00Z    │   │
│  │     └─ Compensated: seed_pages failed, rolled back       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Alerts                                                   │   │
│  │  🟡 Generation p95 > 10s (current: 8.3s)                │   │
│  │  🟢 All services healthy                                  │   │
│  │  🟢 M2M key rotation: 23 days until next                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Gap 12: Reflexivity — Who Builds the Builder?

### 12.1 The Meta Question

If Vela is a constructor of Aether instances, and Vela *itself* is an Aether instance... then Vela should be able to build another Vela. This is both philosophically interesting and practically useful: **white-label constructors for partners.**

### 12.2 Three Levels of Reflexivity

```
LEVEL 1 — Self-hosting:
  Vela builds Vela's own process definitions in Vela FlowEditor.
  (Meta: we dogfood our own tool to model our own development process)

LEVEL 2 — White-label constructors:
  Partner X gets their own Vela-branded instance (partner.vela.io).
  They build processes → deploy Aether instances for THEIR customers.
  (Revenue: platform fee + % of their customer subscriptions)

LEVEL 3 — Recursive construction:
  Partner X's Vela instance can spawn a sub-Vela for their enterprise client.
  Enterprise client builds processes on THEIR Vela.
  (Revenue: volume discounts, enterprise licensing)
```

### 12.3 Architecture for White-Label

```yaml
# Deployment manifest for white-label Vela instance
tenant:
  slug: "partner-logistics"
  name: "LogisticsFlow by PartnerX"
  domain: "app.partner-logistics.ru"
  white_label:
    logo_url: "https://partnerx.ru/logo.png"
    primary_color: "#ff6600"
    custom_domain: true
    hide_aether_branding: true

subscription:
  plan_id: "white_label"
  price_monthly_usd: 299  # Platform fee to us
  revenue_share: 20       # We take 20% of their customer revenue

features:
  - processbot_vision
  - processbot_nlp
  - custom_block_types
  - white_label_deploy
  - api_access

limits:
  max_tenants: 100        # They can deploy up to 100 customer instances
  max_users_per_tenant: 500
```

### 12.4 Meta-Process: Vela's Own Development

```
Vela itself uses Vela FlowEditor to model:

Process: "Feature Development"
  ├── Block: "Spec Review" (assignee: architect)
  ├── Block: "Implementation" (assignee: developer)
  │   ├── Sub-process: "Code Review"
  │   └── Sub-process: "Testing"
  ├── Condition: "Passes CI?"
  │   ├── Yes → Block: "Deploy to Staging"
  │   └── No → Block: "Fix Issues"
  ├── Block: "QA Validation"
  └── Block: "Release to Production"

This IS the actual development workflow. Eat our own dogfood.
```

---

## Gap 13: Block Type Evolution & Marketplace

### 13.1 Block Type Versioning

Block types MUST be versioned because changing a block type can break existing processes.

```python
class BlockType(Base):
    __tablename__ = "block_types"

    id: Mapped[str]
    name: Mapped[str]
    key: Mapped[str]          # stable identifier across versions
    version: Mapped[int]       # 1, 2, 3...
    category: Mapped[str]
    icon: Mapped[str]
    config_schema: Mapped[str] # JSON Schema for config validation
    semantic_version: Mapped[str]  # "1.2.0" — semver

    # Deprecation
    is_deprecated: Mapped[bool]
    deprecated_at: Mapped[datetime | None]
    replaced_by_key: Mapped[str | None]  # Key of replacement block type

    # Marketplace
    is_public: Mapped[bool]          # Visible in marketplace
    author: Mapped[str | None]       # Who created it
    price: Mapped[str]               # "free" | "990" | "2990"
    downloads: Mapped[int]           # Popularity metric
    rating: Mapped[float]            # Average rating

    # Compatibility
    min_aether_version: Mapped[str | None]  # "1.0.0"
    dependencies: Mapped[dict]       # {"other_block_key": ">=1.2.0"}
```

### 13.2 Block Compatibility Matrix

```python
async def check_block_compatibility(
    process: ProcessDefinition,
    available_blocks: list[BlockType]
) -> CompatibilityReport:
    """Check if all blocks in a process are compatible with current block types."""

    issues = []

    for block in process.blocks:
        current = find_block_type(available_blocks, block.block_type)

        if not current:
            issues.append(CompatibilityIssue(
                severity="critical",
                block_key=block.key,
                message=f"Block type '{block.block_type}' no longer exists",
                suggestion="Replace with compatible block or restore block type",
            ))
            continue

        if current.is_deprecated:
            replacement = current.replaced_by_key
            issues.append(CompatibilityIssue(
                severity="warning",
                block_key=block.key,
                message=f"Block type '{block.block_type}' is deprecated",
                suggestion=f"Migrate to '{replacement}'" if replacement else "No replacement available",
                auto_fix_available=bool(replacement),
            ))

        # Check config schema compatibility
        schema_diff = diff_json_schema(
            old_schema=json.loads(block.config_schema or "{}"),
            new_schema=json.loads(current.config_schema or "{}"),
        )

        if schema_diff.breaking_changes:
            issues.append(CompatibilityIssue(
                severity="error",
                block_key=block.key,
                message=f"Block config incompatible with current version",
                details=schema_diff.breaking_changes,
            ))

    return CompatibilityReport(
        compatible=not any(i.severity == "critical" for i in issues),
        issues=issues,
        auto_fixable=sum(1 for i in issues if i.auto_fix_available),
    )
```

### 13.3 Block Marketplace

```
┌──────────────────────────────────────────────────────────────────┐
│  🧩 Block Marketplace                                            │
│                                                                  │
│  Поиск: [______________________]  Категория: [Все ▼]             │
│                                                                  │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────┐│
│  │ 📦 ETRAN Integration │ │ 📄 GU-12 Generator  │ │ 📊 Analytics ││
│  │                     │ │                     │ │             ││
│  │ Работа с системой   │ │ Генерация формы     │ │ Дашборд     ││
│  │ ЭТРАН (жд перевозки)│ │ ГУ-12 из данных     │ │ метрик      ││
│  │                     │ │                     │ │ процесса    ││
│  │ ⭐ 4.8 (23)         │ │ ⭐ 4.5 (18)         │ │ ⭐ 4.2 (7)  ││
│  │ 📥 1.2K установок   │ │ 📥 890 установок    │ │ 📥 340 уст. ││
│  │ 💰 990₽             │ │ 🆓 Бесплатно        │ │ 🆓 Бесплатно││
│  │                     │ │                     │ │             ││
│  │ [Установить]        │ │ [Установить]        │ │ [Установить]││
│  └─────────────────────┘ └─────────────────────┘ └─────────────┘│
│                                                                  │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────┐│
│  │ 📱 Telegram Notifier│ │ ✉️ Email Pipeline   │ │ 🔐 OAuth SSO││
│  │ ...                 │ │ ...                 │ │ ...         ││
│  └─────────────────────┘ └─────────────────────┘ └─────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

---

## Gap 14: Competitive Positioning

### 14.1 Landscape

| Product | What It Is | Vela vs. Them |
|---------|-----------|---------------|
| **Retool** | Internal tools builder (UI) | Retool = apps, Vela = business PROCESSES. We're workflow-first, they're UI-first. |
| **Bubble** | No-code web apps | Bubble = generic apps, Vela = domain-specific processes with AI generation |
| **Zapier** | Workflow automation | Zapier = connect APIs, Vela = build entire business domains. We're a level above. |
| **AppSmith** | Low-code internal tools | Same as Retool. No AI process generation, no tenant isolation out of the box. |
| **n8n** | Open-source workflow automation | n8n = technical users, Vela = business users (photo → process). Our AI pivot is unique. |
| **Airtable** | Spreadsheet-database hybrid | Airtable = data, Vela = processes AROUND data. Complementary, not competing. |

### 14.2 Unique Selling Proposition (USP)

> **Vela — единственная платформа, где бизнес-процесс создаётся с фотографии доски, а на выходе получается полноценный SaaS с tenant-изоляцией, AI-каналами и биллингом.**

Three things nobody else does:
1. **Photo → Process** (AI Vision pipeline)
2. **Process → SaaS Instance** (one-click deploy with full tenant isolation)
3. **Russian-language native** (all prompts, OCR, NLP trained on Russian business terminology)

### 14.3 Positioning Statement

```
Для:       Руководителей отделов и владельцев бизнеса в России
Которые:   Хотят автоматизировать процессы без программистов
Vela — это: Платформа-конструктор бизнес-процессов
Которая:   Превращает нарисованную схему в готовую рабочую систему за минуты
В отличие: От Retool/Bubble, где нужно собирать UI вручную
Наш секрет: AI ProcessBot — фото доски → BPMN → SaaS-инстанс
```

---

## Summary: What This Pass Adds

| # | Gap | Solution | Impact |
|---|------|----------|--------|
| 8 | No business KPIs | AARRR funnel, ProcessBot-specific targets, SQL dashboard | Measure what matters |
| 9 | No iterative refinement | Multi-pass merge with user edit preservation, diff engine | Users don't lose work |
| 10 | No data migration strategy | 4 strategies (auto/manual/dry_run/dual_write), snapshot+rollback | Safe version upgrades |
| 11 | No observability | Structured logging + Prometheus metrics + OpenTelemetry tracing + Grafana dashboard | Production confidence |
| 12 | No reflexivity strategy | 3-level recursion, white-label architecture, meta-process dogfooding | Platform effect |
| 13 | No block type lifecycle | Semver versioning, compatibility matrix, marketplace with ratings/pricing | Sustainable ecosystem |
| 14 | No competitive analysis | 6-product comparison, USP articulation, positioning statement | Go-to-market clarity |
