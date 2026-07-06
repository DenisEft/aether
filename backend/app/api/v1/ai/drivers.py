"""Driver endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, CurrentSuperuser, DBDep
from app.models.ai import DriverConfig, DriverMetric
from app.schemas.ai import (
    DriverConfigCreate,
    DriverConfigResponse,
    DriverConfigUpdate,
    DriverMetricResponse,
)

logger = logging.getLogger("aether.api.ai.drivers")
router = APIRouter(tags=["drivers"])


# ─────────────────────────────────────────────────────────────
# DRIVER CONFIGS (global — superuser only)
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[DriverConfigResponse])
async def list_driver_configs(
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[DriverConfigResponse]:
    """List driver configs (global)."""
    stmt = select(DriverConfig).order_by(DriverConfig.name)
    result = await db.execute(stmt)
    return [DriverConfigResponse.model_validate(d) for d in result.scalars().all()]


@router.post("", response_model=DriverConfigResponse, status_code=201)
async def create_driver_config(
    body: DriverConfigCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Create a new driver config."""
    driver_config = DriverConfig(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        driver_type=body.driver_type,
        config=body.config,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(driver_config)
    await db.commit()
    await db.refresh(driver_config)
    return DriverConfigResponse.model_validate(driver_config)


@router.get("/{driver_config_id}", response_model=DriverConfigResponse)
async def get_driver_config(
    driver_config_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Get driver config details."""
    result = await db.execute(
        select(DriverConfig).where(
            DriverConfig.id == driver_config_id,
        )
    )
    driver_config = result.scalar_one_or_none()
    if driver_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Driver config not found"
        )
    return DriverConfigResponse.model_validate(driver_config)


@router.put("/{driver_config_id}", response_model=DriverConfigResponse)
async def update_driver_config(
    driver_config_id: uuid.UUID,
    body: DriverConfigUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Update a driver config."""
    result = await db.execute(
        select(DriverConfig).where(
            DriverConfig.id == driver_config_id,
        )
    )
    driver_config = result.scalar_one_or_none()
    if driver_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Driver config not found"
        )

    if body.display_name is not None:
        driver_config.display_name = body.display_name
    if body.description is not None:
        driver_config.description = body.description
    if body.driver_type is not None:
        driver_config.driver_type = body.driver_type
    if body.config is not None:
        driver_config.config = body.config
    if body.is_builtin is not None:
        driver_config.is_builtin = body.is_builtin
    if body.plugin_ids is not None:
        driver_config.plugin_ids = body.plugin_ids

    await db.commit()
    await db.refresh(driver_config)
    return DriverConfigResponse.model_validate(driver_config)


@router.delete("/{driver_config_id}", status_code=200)
async def delete_driver_config(
    driver_config_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a driver config."""
    result = await db.execute(
        select(DriverConfig).where(
            DriverConfig.id == driver_config_id,
        )
    )
    driver_config = result.scalar_one_or_none()
    if driver_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Driver config not found"
        )

    await db.delete(driver_config)
    await db.commit()
    return {"message": "Driver config deleted"}


# ── Driver Metrics (read-only) ─────────────────────────────────────────


@router.get("/{driver_config_id}/metrics", response_model=list[DriverMetricResponse])
async def list_driver_metrics(
    driver_config_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[DriverMetricResponse]:
    """List metrics for a driver."""
    stmt = (
        select(DriverMetric)
        .where(
            DriverMetric.driver_config_id == driver_config_id,
        )
        .order_by(DriverMetric.created_at.desc())
    )
    result = await db.execute(stmt)
    return [DriverMetricResponse.model_validate(m) for m in result.scalars().all()]
