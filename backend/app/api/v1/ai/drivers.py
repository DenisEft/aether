"""Driver endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentSuperuser, DBDep
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


@router.get("/drivers", response_model=list[DriverConfigResponse])
async def list_drivers(
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[DriverConfigResponse]:
    """List all AI driver configs (superuser only)."""
    result = await db.execute(select(DriverConfig).order_by(DriverConfig.driver_type))
    return [DriverConfigResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/drivers", response_model=DriverConfigResponse, status_code=201)
async def create_driver(
    body: DriverConfigCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Register a new AI driver (superuser only)."""
    driver = DriverConfig(
        driver_type=body.driver_type,
        endpoint=body.endpoint,
        config=body.config,
    )
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return DriverConfigResponse.model_validate(driver)


@router.get("/drivers/{driver_id}", response_model=DriverConfigResponse)
async def get_driver(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Get driver config details (superuser only)."""
    result = await db.execute(select(DriverConfig).where(DriverConfig.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    return DriverConfigResponse.model_validate(driver)


@router.patch("/drivers/{driver_id}", response_model=DriverConfigResponse)
async def update_driver(
    driver_id: uuid.UUID,
    body: DriverConfigUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Update a driver config (superuser only)."""
    result = await db.execute(select(DriverConfig).where(DriverConfig.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    if body.endpoint is not None:
        driver.endpoint = body.endpoint
    if body.is_healthy is not None:
        driver.is_healthy = body.is_healthy
    if body.error_message is not None:
        driver.error_message = body.error_message
    if body.config is not None:
        driver.config = body.config

    await db.commit()
    await db.refresh(driver)
    return DriverConfigResponse.model_validate(driver)


@router.delete("/drivers/{driver_id}", status_code=200)
async def delete_driver(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a driver config (superuser only)."""
    result = await db.execute(select(DriverConfig).where(DriverConfig.id == driver_id))
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    await db.delete(driver)
    await db.commit()
    return {"message": "Driver deleted"}


# ── Driver Metrics (read-only) ───────────────────────────────


@router.get("/drivers/{driver_id}/metrics", response_model=list[DriverMetricResponse])
async def get_driver_metrics(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
    limit: int = Query(default=100, le=1000),
) -> list[DriverMetricResponse]:
    """Get recent metrics for a driver (superuser only)."""
    result = await db.execute(
        select(DriverMetric)
        .where(DriverMetric.driver_config_id == driver_id)
        .order_by(DriverMetric.recorded_at.desc())
        .limit(limit)
    )
    return [DriverMetricResponse.model_validate(m) for m in result.scalars().all()]
