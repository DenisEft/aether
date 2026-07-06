"""Tenant management endpoints (admin/superuser)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentSuperuser, DBDep
from app.models.tenants import (
    Tenant,
    TenantConfig,
    TenantDomain,
    TenantFeature,
    TenantLimit,
)
from app.schemas.tenants import (
    TenantConfigCreate,
    TenantConfigResponse,
    TenantConfigUpdate,
    TenantCreate,
    TenantDomainCreate,
    TenantDomainResponse,
    TenantDomainUpdate,
    TenantFeatureCreate,
    TenantFeatureResponse,
    TenantFeatureUpdate,
    TenantLimitCreate,
    TenantLimitResponse,
    TenantLimitUpdate,
    TenantResponse,
    TenantUpdate,
)

router = APIRouter(tags=["tenants"])


# ─────────────────────────────────────────────────────────────
# TENANTS (superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[TenantResponse]:
    """List all tenants (superuser only)."""
    result = await db.execute(select(Tenant).order_by(Tenant.name))
    return [TenantResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantResponse:
    """Create a new tenant (superuser only)."""
    tenant = Tenant(
        slug=body.slug,
        name=body.name,
        domain=body.domain,
        logo_url=body.logo_url,
        primary_color=body.primary_color,
        timezone=body.timezone,
        locale=body.locale,
        settings=body.settings,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantResponse:
    """Get tenant details (superuser only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantResponse.model_validate(tenant)


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantResponse:
    """Update a tenant (superuser only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if body.name is not None:
        tenant.name = body.name
    if body.domain is not None:
        tenant.domain = body.domain
    if body.logo_url is not None:
        tenant.logo_url = body.logo_url
    if body.primary_color is not None:
        tenant.primary_color = body.primary_color
    if body.timezone is not None:
        tenant.timezone = body.timezone
    if body.locale is not None:
        tenant.locale = body.locale
    if body.is_active is not None:
        tenant.is_active = body.is_active
    if body.settings is not None:
        tenant.settings = body.settings

    await db.commit()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)


@router.delete("/tenants/{tenant_id}", status_code=200)
async def delete_tenant(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a tenant (superuser only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    tenant.is_active = False
    await db.commit()
    return {"message": "Tenant deactivated"}


# ─────────────────────────────────────────────────────────────
# TENANT CONFIGS (superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}/configs", response_model=list[TenantConfigResponse])
async def list_tenant_configs(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[TenantConfigResponse]:
    """List configs for a tenant."""
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id).order_by(TenantConfig.key)
    )
    return [TenantConfigResponse.model_validate(c) for c in result.scalars().all()]


@router.post("/tenants/{tenant_id}/configs", response_model=TenantConfigResponse, status_code=201)
async def create_tenant_config(
    tenant_id: uuid.UUID,
    body: TenantConfigCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantConfigResponse:
    """Set a tenant config."""
    config = TenantConfig(
        tenant_id=tenant_id,
        key=body.key,
        value=body.value,
        description=body.description,
        updated_by=current_user.id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return TenantConfigResponse.model_validate(config)


@router.patch("/tenants/{tenant_id}/configs/{config_id}", response_model=TenantConfigResponse)
async def update_tenant_config(
    tenant_id: uuid.UUID,
    config_id: uuid.UUID,
    body: TenantConfigUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantConfigResponse:
    """Update a tenant config."""
    result = await db.execute(
        select(TenantConfig).where(
            TenantConfig.id == config_id,
            TenantConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    if body.value is not None:
        config.value = body.value
    if body.description is not None:
        config.description = body.description
    config.updated_by = current_user.id

    await db.commit()
    await db.refresh(config)
    return TenantConfigResponse.model_validate(config)


@router.delete("/tenants/{tenant_id}/configs/{config_id}", status_code=200)
async def delete_tenant_config(
    tenant_id: uuid.UUID,
    config_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a tenant config."""
    result = await db.execute(
        select(TenantConfig).where(
            TenantConfig.id == config_id,
            TenantConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    await db.delete(config)
    await db.commit()
    return {"message": "Config deleted"}


# ─────────────────────────────────────────────────────────────
# TENANT FEATURES (superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}/features", response_model=list[TenantFeatureResponse])
async def list_tenant_features(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[TenantFeatureResponse]:
    """List features for a tenant."""
    result = await db.execute(
        select(TenantFeature)
        .where(TenantFeature.tenant_id == tenant_id)
        .order_by(TenantFeature.feature_key)
    )
    return [TenantFeatureResponse.model_validate(f) for f in result.scalars().all()]


@router.post(
    "/tenants/{tenant_id}/features", response_model=TenantFeatureResponse, status_code=201
)
async def toggle_tenant_feature(
    tenant_id: uuid.UUID,
    body: TenantFeatureCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantFeatureResponse:
    """Enable a feature for a tenant."""
    feature = TenantFeature(
        tenant_id=tenant_id,
        feature_key=body.feature_key,
        is_enabled=body.is_enabled,
        config=body.config,
    )
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return TenantFeatureResponse.model_validate(feature)


@router.patch("/tenants/{tenant_id}/features/{feature_id}", response_model=TenantFeatureResponse)
async def update_tenant_feature(
    tenant_id: uuid.UUID,
    feature_id: uuid.UUID,
    body: TenantFeatureUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantFeatureResponse:
    """Update a tenant feature."""
    result = await db.execute(
        select(TenantFeature).where(
            TenantFeature.id == feature_id,
            TenantFeature.tenant_id == tenant_id,
        )
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")

    if body.is_enabled is not None:
        feature.is_enabled = body.is_enabled
    if body.config is not None:
        feature.config = body.config

    await db.commit()
    await db.refresh(feature)
    return TenantFeatureResponse.model_validate(feature)


@router.delete("/tenants/{tenant_id}/features/{feature_id}", status_code=200)
async def delete_tenant_feature(
    tenant_id: uuid.UUID,
    feature_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Disable (delete) a tenant feature."""
    result = await db.execute(
        select(TenantFeature).where(
            TenantFeature.id == feature_id,
            TenantFeature.tenant_id == tenant_id,
        )
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")

    await db.delete(feature)
    await db.commit()
    return {"message": "Feature disabled"}


# ─────────────────────────────────────────────────────────────
# TENANT LIMITS (superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}/limits", response_model=list[TenantLimitResponse])
async def list_tenant_limits(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[TenantLimitResponse]:
    """List limits for a tenant."""
    result = await db.execute(
        select(TenantLimit)
        .where(TenantLimit.tenant_id == tenant_id)
        .order_by(TenantLimit.limit_key)
    )
    return [TenantLimitResponse.model_validate(l) for l in result.scalars().all()]


@router.post("/tenants/{tenant_id}/limits", response_model=TenantLimitResponse, status_code=201)
async def set_tenant_limit(
    tenant_id: uuid.UUID,
    body: TenantLimitCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantLimitResponse:
    """Set a limit for a tenant."""
    limit = TenantLimit(
        tenant_id=tenant_id,
        limit_key=body.limit_key,
        hard_limit=body.hard_limit,
        soft_limit=body.soft_limit,
        current_value=body.current_value,
    )
    db.add(limit)
    await db.commit()
    await db.refresh(limit)
    return TenantLimitResponse.model_validate(limit)


@router.patch("/tenants/{tenant_id}/limits/{limit_id}", response_model=TenantLimitResponse)
async def update_tenant_limit(
    tenant_id: uuid.UUID,
    limit_id: uuid.UUID,
    body: TenantLimitUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantLimitResponse:
    """Update a tenant limit."""
    result = await db.execute(
        select(TenantLimit).where(
            TenantLimit.id == limit_id,
            TenantLimit.tenant_id == tenant_id,
        )
    )
    limit = result.scalar_one_or_none()
    if limit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Limit not found")

    if body.hard_limit is not None:
        limit.hard_limit = body.hard_limit
    if body.soft_limit is not None:
        limit.soft_limit = body.soft_limit
    if body.current_value is not None:
        limit.current_value = body.current_value

    await db.commit()
    await db.refresh(limit)
    return TenantLimitResponse.model_validate(limit)


# ─────────────────────────────────────────────────────────────
# TENANT DOMAINS (superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}/domains", response_model=list[TenantDomainResponse])
async def list_tenant_domains(
    tenant_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[TenantDomainResponse]:
    """List custom domains for a tenant."""
    result = await db.execute(
        select(TenantDomain)
        .where(TenantDomain.tenant_id == tenant_id)
        .order_by(TenantDomain.domain)
    )
    return [TenantDomainResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/tenants/{tenant_id}/domains", response_model=TenantDomainResponse, status_code=201)
async def add_tenant_domain(
    tenant_id: uuid.UUID,
    body: TenantDomainCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantDomainResponse:
    """Add a custom domain to a tenant."""
    domain = TenantDomain(
        tenant_id=tenant_id,
        domain=body.domain,
        ssl_enabled=body.ssl_enabled,
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return TenantDomainResponse.model_validate(domain)


@router.patch("/tenants/{tenant_id}/domains/{domain_id}", response_model=TenantDomainResponse)
async def update_tenant_domain(
    tenant_id: uuid.UUID,
    domain_id: uuid.UUID,
    body: TenantDomainUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> TenantDomainResponse:
    """Update a tenant domain."""
    result = await db.execute(
        select(TenantDomain).where(
            TenantDomain.id == domain_id,
            TenantDomain.tenant_id == tenant_id,
        )
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    if body.is_verified is not None:
        domain.is_verified = body.is_verified
    if body.verified_at is not None:
        domain.verified_at = body.verified_at
    if body.ssl_enabled is not None:
        domain.ssl_enabled = body.ssl_enabled

    await db.commit()
    await db.refresh(domain)
    return TenantDomainResponse.model_validate(domain)


@router.delete("/tenants/{tenant_id}/domains/{domain_id}", status_code=200)
async def remove_tenant_domain(
    tenant_id: uuid.UUID,
    domain_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Remove a custom domain from a tenant."""
    result = await db.execute(
        select(TenantDomain).where(
            TenantDomain.id == domain_id,
            TenantDomain.tenant_id == tenant_id,
        )
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    await db.delete(domain)
    await db.commit()
    return {"message": "Domain removed"}
