# 🔗 Vela→Aether Deploy Bridge — Specification

**Version:** 1.0.0
**Created:** 2026-07-05
**Status:** Draft — pending review

---

## 1. Overview

Vela→Aether Deploy Bridge — интеграционный слой, превращающий готовый процесс из Vela FlowEditor в полноценный инстанс Aether:

```
Vela ProcessDefinition → Aether Tenant API → Provisioned Instance
```

Это ключевая «магия»: пользователь конструирует процесс визуально → нажимает «Опубликовать» → получает работающий SaaS с tenant-изоляцией, биллингом и каналами.

---

## 2. Current State Analysis

### 2.1 What Vela Has

| Component | Status | Notes |
|-----------|--------|-------|
| ProcessDefinition CRUD | ✅ | Full API: create, read, update, delete, graph save |
| BlockType catalog | ✅ | `/api/block-types` — 10+ types with categories |
| PageBuilder (grid) | ✅ | Layouts stored as JSON in `process_pages.layout_config` |
| Process validation | ✅ | Graph integrity, entry points, orphan checks |
| Versioning | ✅ | Snapshots + rollback |
| Auth | ✅ | JWT (own secret, not Aether-compatible) |

### 2.2 What Aether Has

| Component | Status | Notes |
|-----------|--------|-------|
| Tenant CRUD | ✅ | `/api/v1/tenants` — full admin API |
| TenantProvisioningService | ✅ | `provision_tenant()` — creates DB, Redis, roles |
| Subscription/billing | ✅ | Plans, subscriptions, usage tracking |
| Organisations | ✅ | Multi-org per tenant |
| Users + roles | ✅ | owner, admin, member, viewer |
| Channels | ✅ | Telegram, Email, Web Widget |
| Plugin system | ✅ | BaseServicePlugin, registry |

### 2.3 What's Missing (The Bridge)

| # | Gap | Priority |
|---|-----|----------|
| 1 | Vela auth ≠ Aether auth (different JWT secrets) | P0 |
| 2 | Vela SQLite ≠ Aether PostgreSQL | P0 |
| 3 | No process seeding in Aether TenantProvisioning | P0 |
| 4 | No page-to-route mapping in Vela→Aether | P0 |
| 5 | No deployment status tracking | P1 |
| 6 | No rollback/undeploy | P1 |

---

## 3. Integration Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  VELA (constructor)                                              │
│                                                                  │
│  FlowEditor ──► ProcessDefinition (blocks+connections)          │
│                    │                                             │
│  PageBuilder ──► ProcessPages (layout_config)                   │
│                    │                                             │
│         ┌──────────▼──────────┐                                  │
│         │  DEPLOY BUTTON      │                                  │
│         │  "Опубликовать"     │                                  │
│         └──────────┬──────────┘                                  │
│                    │                                             │
│         ┌──────────▼──────────┐                                  │
│         │  DEPLOY SERVICE     │                                  │
│         │  (new module)       │                                  │
│         └──────────┬──────────┘                                  │
└────────────────────┼────────────────────────────────────────────┘
                     │
         ┌───────────▼───────────────┐
         │  DEPLOY MANIFEST JSON     │
         │  {                        │
         │    tenant: {...},         │
         │    process: {...},        │
         │    pages: [...],          │
         │    channels: [...],       │
         │    billing: {...}         │
         │  }                        │
         └───────────┬───────────────┘
                     │
         ┌───────────▼───────────────┐
         │  AETHER API               │
         │  POST /api/v1/deploy      │
         └───────────┬───────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│  AETHER (platform)                                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. DeployService (new)                                   │  │
│  │     ├── Validate manifest                                 │  │
│  │     ├── Create Tenant                                     │  │
│  │     ├── Provision tenant (DB, Redis, roles)               │  │
│  │     ├── Seed process definition                           │  │
│  │     ├── Seed pages (routes)                               │  │
│  │     ├── Configure channels                                │  │
│  │     ├── Activate subscription                             │  │
│  │     └── Return admin URL + workspace URL                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. Instance Manager (UI)                                  │  │
│  │     ├── List deployed instances                           │  │
│  │     ├── Instance health/status                            │  │
│  │     ├── Update (new process version)                      │  │
│  │     ├── Suspend/Resume                                    │  │
│  │     └── Delete (with data retention policy)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Deploy Manifest Schema

```json
{
  "$schema": "https://aether.local/schemas/deploy-manifest/v1",
  "version": "1.0.0",

  "tenant": {
    "slug": "coalstar-logistics",
    "name": "Логистика Coalstar",
    "timezone": "Asia/Vladivostok",
    "locale": "ru",
    "primary_color": "#1a73e8",
    "domain": "logistics.coalstar.ru"
  },

  "owner": {
    "email": "admin@coalstar.ru",
    "name": "Администратор"
  },

  "process": {
    "id": "source-process-uuid",
    "name": "Управление перевозками",
    "slug": "transport-management",
    "version": 1,
    "blocks": [...],       // Full block definitions from Vela
    "connections": [...],  // Full connection definitions from Vela
    "fields": [...],       // Form field definitions
    "stages": [...]        // Process stage definitions
  },

  "pages": [
    {
      "route": "/dashboard",
      "title": "Панель управления",
      "component_type": "dashboard",
      "layout_config": "{...}",  // vue-grid-layout JSON
      "blocks_visible": ["b1", "b2", "b5"]
    },
    {
      "route": "/documents",
      "title": "Документы",
      "component_type": "list",
      "layout_config": "{...}",
      "blocks_visible": ["b3"]
    },
    {
      "route": "/create-shipment",
      "title": "Новая перевозка",
      "component_type": "form",
      "layout_config": "{...}",
      "blocks_visible": ["b1"]
    }
  ],

  "channels": [
    {
      "type": "telegram",
      "name": "Логистика Коалстар Бот",
      "config": {
        "welcome_message": "Добро пожаловать в систему управления перевозками!",
        "allowed_commands": ["/status", "/documents", "/help"]
      }
    },
    {
      "type": "web_widget",
      "name": "Чат поддержки",
      "config": {
        "position": "bottom-right",
        "primary_color": "#1a73e8"
      }
    }
  ],

  "subscription": {
    "plan_id": "pro",
    "trial_days": 14
  },

  "ai_config": {
    "enabled_features": ["document_classification", "eta_prediction"],
    "preferred_model": "auto",
    "max_monthly_tokens": 100000
  }
}
```

---

## 5. API Specification

### 5.1 POST /api/v1/deploy

**Auth:** Vela service account (machine-to-machine JWT)

#### Request: DeployManifest (JSON, see §4)

#### Response (201 — Created)

```json
{
  "status": "deployed",
  "tenant_id": "uuid",
  "tenant_slug": "coalstar-logistics",
  "urls": {
    "workspace": "https://coalstar-logistics.aether.local/workspace",
    "admin": "https://coalstar-logistics.aether.local/admin",
    "telegram_bot": "https://t.me/coalstar_logistics_bot"
  },
  "owner_invite": {
    "email": "admin@coalstar.ru",
    "invite_url": "https://coalstar-logistics.aether.local/accept-invite?token=xxx",
    "expires_at": "2026-07-12T00:00:00Z"
  },
  "subscription": {
    "plan": "pro",
    "trial_ends_at": "2026-07-19T00:00:00Z",
    "status": "trialing"
  },
  "deployed_at": "2026-07-05T03:30:00Z"
}
```

#### Response (409 — Conflict)

```json
{
  "status": "error",
  "error": "slug_taken",
  "message": "Tenant slug 'coalstar-logistics' уже занят",
  "available_suggestions": ["coalstar-logistics-2", "coalstar-transport"]
}
```

### 5.2 GET /api/v1/deploy/status/{tenant_id}

Check deployment health and process version.

```json
{
  "tenant_id": "uuid",
  "status": "healthy",
  "process_version": 1,
  "latest_source_version": 3,
  "update_available": true,
  "pages_count": 5,
  "active_users": 3,
  "channels_active": {
    "telegram": true,
    "web_widget": true
  },
  "billing": {
    "plan": "pro",
    "status": "active",
    "usage_this_month": {
      "credits": 120,
      "ai_tokens": 45000
    }
  },
  "last_deployed": "2026-07-05T03:30:00Z",
  "uptime_hours": 72
}
```

### 5.3 POST /api/v1/deploy/update/{tenant_id}

Update instance with new process version.

#### Request:

```json
{
  "source_process_id": "uuid",
  "new_version": 2,
  "process": {...},
  "pages": [...],
  "migrate_strategy": "auto"
}
```

#### Response (200):

```json
{
  "status": "updated",
  "previous_version": 1,
  "new_version": 2,
  "migrated_instances": 15,
  "pages_updated": 3,
  "pages_added": 1,
  "pages_removed": 0
}
```

### 5.4 DELETE /api/v1/deploy/{tenant_id}

Undeploy instance.

#### Query Parameters:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `hard` | bool | `false` | Hard delete all data |
| `retention_days` | int | `30` | Data retention before permanent delete |

#### Response (200):

```json
{
  "status": "suspended",
  "tenant_id": "uuid",
  "data_retention_until": "2026-08-04T00:00:00Z",
  "reactivation_possible": true
}
```

---

## 6. DeployService Implementation

```python
# aether/backend/app/services/deploy_service.py

from dataclasses import dataclass
from uuid import UUID

from app.services.tenant_provisioning import TenantProvisioningService
from app.models.tenants import Tenant
from app.models.billing import Subscription, SubscriptionPlan


@dataclass
class DeployManifest:
    tenant: dict
    owner: dict
    process: dict
    pages: list[dict]
    channels: list[dict]
    subscription: dict
    ai_config: dict


class DeployService:
    """Orchestrates full instance deployment from Vela manifest."""

    def __init__(self, session):
        self._session = session
        self._provisioning = TenantProvisioningService(session)

    async def deploy(self, manifest: DeployManifest) -> dict:
        """Deploy a new Aether instance from a Vela manifest."""

        # 1. Validate manifest
        self._validate_manifest(manifest)

        # 2. Create Tenant
        tenant = await self._create_tenant(manifest.tenant)

        # 3. Provision tenant resources
        await self._provisioning.provision_tenant(tenant.id)

        # 4. Create owner user + invite
        owner = await self._create_owner(tenant.id, manifest.owner)

        # 5. Seed process definition
        await self._seed_process(tenant.id, manifest.process)

        # 6. Seed pages
        await self._seed_pages(tenant.id, manifest.pages)

        # 7. Configure channels
        await self._configure_channels(tenant.id, manifest.channels)

        # 8. Activate subscription
        subscription = await self._activate_subscription(
            tenant.id, manifest.subscription
        )

        # 9. Configure AI features
        await self._configure_ai(tenant.id, manifest.ai_config)

        # 10. Generate invite
        invite = await self._generate_invite(owner)

        return {
            "status": "deployed",
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "urls": {
                "workspace": f"https://{tenant.slug}.aether.local/workspace",
                "admin": f"https://{tenant.slug}.aether.local/admin",
            },
            "owner_invite": invite,
            "subscription": {
                "plan": subscription.plan_id,
                "status": subscription.status,
                "trial_ends_at": subscription.trial_ends_at.isoformat(),
            },
            "deployed_at": datetime.utcnow().isoformat(),
        }

    async def _seed_process(self, tenant_id: UUID, process_def: dict):
        """Seed Vela process definition into Aether tenant."""
        # Create process_instances table records
        # Map block types → plugin actions
        # Create stage definitions
        # Seed initial data if provided
        pass

    async def _seed_pages(self, tenant_id: UUID, pages: list[dict]):
        """Seed PageBuilder layouts as frontend routes."""
        # Create route registrations
        # Map layout_config → Vue components
        # Configure navigation/menu
        pass

    async def _configure_channels(self, tenant_id: UUID, channels: list[dict]):
        """Activate and configure communication channels."""
        for ch in channels:
            # Create channel record
            # Apply config (webhook URLs, Telegram tokens, etc.)
            # Activate channel
            pass

    async def _validate_manifest(self, manifest: DeployManifest):
        """Validate manifest completeness and constraints."""
        errors = []

        # Required fields
        if not manifest.tenant.get("slug"):
            errors.append("tenant.slug is required")
        if not manifest.tenant.get("name"):
            errors.append("tenant.name is required")
        if not manifest.owner.get("email"):
            errors.append("owner.email is required")

        # Constraints
        if len(manifest.process.get("blocks", [])) > 100:
            errors.append("Max 100 blocks per process")
        if len(manifest.pages) > 50:
            errors.append("Max 50 pages per instance")

        if errors:
            raise ValidationError(errors)
```

---

## 7. Auth Integration Strategy

### Problem
Vela and Aether currently use different JWT secrets. Vela needs to call Aether APIs as a trusted service.

### Solution: Machine-to-Machine (M2M) Service Account

```
Vela Backend                    Aether Backend
     │                               │
     │  1. Generate M2M JWT          │
     │  (signed with shared secret)  │
     │                               │
     │  2. POST /api/v1/deploy ──────►│
     │     Authorization: Bearer <jwt>│
     │                               │
     │                        ┌──────▼──────┐
     │                        │ Validate JWT│
     │                        │ Check scope │
     │                        │ (deploy:wr) │
     │                        └──────┬──────┘
     │                               │
     │  3. Response ◄────────────────┘
```

**Implementation:**

```python
# aether/backend/app/core/security.py

# Shared config
AETHER_M2M_SECRET = os.getenv("AETHER_M2M_SECRET")
AETHER_M2M_ISSUER = "vela.aether.local"

async def verify_m2m_token(token: str) -> M2MContext:
    """Verify Vela→Aether machine-to-machine JWT."""
    payload = jwt.decode(
        token,
        AETHER_M2M_SECRET,
        algorithms=["HS256"],
        options={"require": ["sub", "iss", "scope"]}
    )

    assert payload["iss"] == AETHER_M2M_ISSUER
    assert "deploy:write" in payload.get("scope", "").split()

    return M2MContext(
        service="vela",
        tenant_id=None,  # M2M — no tenant context
        scope=payload["scope"].split()
    )
```

**Configuration:**

```bash
# aether/.env
AETHER_M2M_SECRET=shared-secret-between-vela-and-aether

# vela/.env
VITE_AETHER_API_URL=http://localhost:8000/api/v1
AETHER_M2M_SECRET=shared-secret-between-vela-and-aether
```

---

## 8. Database Migration: SQLite → PostgreSQL

### Why
Vela currently uses SQLite. Aether uses PostgreSQL with RLS. For Vela to be a proper Aether service, it needs PG.

### Strategy: Alembic-based migration

```python
# vela/backend/scripts/migrate_to_postgres.py

async def migrate_sqlite_to_postgres():
    """One-shot migration: Vela SQLite → PostgreSQL."""

    # 1. Create PG schema from Vela models
    # 2. Copy data table-by-table
    # 3. Add tenant_id columns where needed
    # 4. Enable RLS policies
    # 5. Verify row counts match

    tables = [
        "block_types",
        "process_definitions",
        "process_blocks",
        "process_connections",
        "process_stage_defs",
        "process_fields",
        "process_pages",
        "process_versions",
    ]

    for table in tables:
        rows = await sqlite_fetch_all(table)
        await pg_insert_batch(table, rows)
        logger.info(f"Migrated {len(rows)} rows from {table}")
```

**Note:** Migration only needed for Vela's own process editor data. Generated Aether instances get their own PG schemas.

---

## 9. Frontend Integration

### 9.1 Deploy Button in Vela FlowEditor

```vue
<!-- Vela FlowEditor toolbar addition -->
<button
  class="flow-btn flow-btn-deploy"
  :disabled="!canDeploy"
  @click="handleDeploy"
>
  <AppIcon icon="rocket" :size="14" />
  Опубликовать
</button>

<!-- Deploy modal -->
<DeployModal
  v-if="showDeployModal"
  :process="currentProcess"
  :pages="currentPages"
  @deploy="onDeploy"
  @cancel="showDeployModal = false"
/>
```

### 9.2 Deploy Modal Flow

```
┌─────────────────────────────────────────────────┐
│  🚀 Публикация процесса                         │
│                                                 │
│  ┌─────────────────────────────────────────────┐│
│  │ 1. Настройки инстанса                      ││
│  │    Название: [Логистика Coalstar      ]    ││
│  │    Slug:     [coalstar-logistics      ]    ││
│  │    Домен:    [logistics.coalstar.ru   ]    ││
│  │    Часовой пояс: [Asia/Vladivostok  ▼]    ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  ┌─────────────────────────────────────────────┐│
│  │ 2. Администратор                           ││
│  │    Email: [admin@coalstar.ru          ]    ││
│  │    Имя:   [Администратор              ]    ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  ┌─────────────────────────────────────────────┐│
│  │ 3. Каналы                                  ││
│  │    ☑ Telegram бот                         ││
│  │    ☑ Веб-виджет                           ││
│  │    ☐ Email                                ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  ┌─────────────────────────────────────────────┐│
│  │ 4. Тариф                                   ││
│  │    ○ Pro (990₽/мес)                        ││
│  │    ● Enterprise (2,990₽/мес)               ││
│  │    Пробный период: 14 дней                  ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  ┌─────────────────────────────────────────────┐│
│  │ 5. Страницы (3 шт.)                        ││
│  │    ✓ /dashboard — Панель управления        ││
│  │    ✓ /documents — Документы                ││
│  │    ✓ /create-shipment — Новая перевозка    ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  [Отмена]              [🚀 Опубликовать]       │
└─────────────────────────────────────────────────┘
```

---

## 10. Implementation Plan

### Week 1: Foundation

| Day | Task |
|-----|------|
| 1 | M2M auth setup: shared JWT secret between Vela and Aether |
| 2 | DeployService skeleton in Aether |
| 3 | POST /api/v1/deploy endpoint |
| 4 | Tenant creation + provisioning from manifest |
| 5 | Process seeding + pages seeding |

### Week 2: Integration

| Day | Task |
|-----|------|
| 1 | Vela deploy button + modal UI |
| 2 | Vela deploy service → Aether API call |
| 3 | Instance manager UI in Vela (list deployed, status) |
| 4 | Update flow (new process version → instance update) |
| 5 | Testing: end-to-end deploy + use |

### Week 3: Polish

| Day | Task |
|-----|------|
| 1-2 | Error handling, retry logic, rollback |
| 3-4 | Channel auto-configuration (Telegram webhook) |
| 5 | Documentation, deployment guide |

---

## Appendix A: Configuration Reference

```yaml
# aether/config/deploy.yaml
deploy:
  max_blocks_per_process: 100
  max_pages_per_instance: 50
  max_channels_per_instance: 5
  trial_days_default: 14
  retention_days_default: 30

  m2m:
    allowed_services:
      - service: vela
        scopes: [deploy:write, deploy:read, deploy:delete]

  limits:
    free_tier:
      max_processes: 1
      max_users: 3
      channels: [web_widget]
    pro_tier:
      max_processes: 10
      max_users: 20
      channels: [web_widget, telegram, email]
    enterprise:
      max_processes: -1  # unlimited
      max_users: -1
      channels: [all]
```
