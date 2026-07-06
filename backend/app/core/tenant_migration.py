"""Tenant migration runner.

C1 Fix: When schema migrations add new tenant-specific resources
(RLS policies, plugin data, seed data), this runner applies them
to each existing tenant.

Architecture:
  - Alembic handles global DDL (add columns, create tables)
  - TenantMigrationRunner handles per-tenant DML (RLS policies, seed data)
  - Runs in post-migration hook or via CLI: `python -m app.core.tenant_migration`
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Type for migration callbacks
TenantMigrationFn = Callable[[AsyncSession, str], Awaitable[None]]

# Registry of tenant-specific migrations by version
_registry: dict[str, list[TenantMigrationFn]] = {}


def register_tenant_migration(version: str):
    """Decorator to register a tenant-specific migration for a version."""

    def decorator(fn: TenantMigrationFn) -> TenantMigrationFn:
        if version not in _registry:
            _registry[version] = []
        _registry[version].append(fn)
        return fn

    return decorator


async def run_tenant_migrations(db: AsyncSession, from_version: str | None = None) -> int:
    """Run pending tenant migrations for all active tenants.

    Args:
        db: Database session
        from_version: Apply migrations from this version (None = all)

    Returns:
        Number of tenants processed
    """
    # Get all active tenant IDs
    result = await db.execute(text("SELECT id FROM tenants WHERE is_active = true"))
    tenant_ids = [row[0] for row in result.fetchall()]

    versions_to_run = sorted(_registry.keys())
    if from_version:
        versions_to_run = [v for v in versions_to_run if v >= from_version]

    for tenant_id in tenant_ids:
        tenant_id_str = str(tenant_id)
        await db.execute(text("SET app.current_tenant_id = :tid"), {"tid": tenant_id_str})

        for version in versions_to_run:
            for migration_fn in _registry[version]:
                try:
                    await migration_fn(db, tenant_id_str)
                    logger.info("Tenant migration %s applied to tenant %s", version, tenant_id_str)
                except Exception as exc:
                    logger.error(
                        "Tenant migration %s failed for tenant %s: %s", version, tenant_id_str, exc
                    )
                    raise

        await db.execute(text("RESET app.current_tenant_id"))

    await db.commit()
    return len(tenant_ids)


# ── Example tenant migrations ────────────────────────────────


@register_tenant_migration("1.0.0")
async def _seed_default_roles(db: AsyncSession, tenant_id: str) -> None:
    """Seed default roles for each tenant."""
    from sqlalchemy import text as sqltext

    roles = [
        ("owner", "Full access to organisation"),
        ("admin", "Manage settings and members"),
        ("member", "Standard workspace access"),
        ("viewer", "Read-only access"),
    ]
    for name, description in roles:
        await db.execute(
            sqltext(
                "INSERT INTO roles (tenant_id, name, description, is_builtin) "
                "VALUES (:tid, :name, :desc, true) "
                "ON CONFLICT (tenant_id, name) DO NOTHING"
            ),
            {"tid": tenant_id, "name": name, "desc": description},
        )
