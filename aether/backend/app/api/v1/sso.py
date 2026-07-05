"""SSO admin endpoints: manage OIDC/SAML configurations (Stage 3)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentSuperuser, DBDep
from app.models.auth import SSOConfig
from app.schemas.sso import SSOConfigCreate, SSOConfigResponse, SSOConfigUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/sso", tags=["sso"])


@router.post("", response_model=SSOConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_sso_config(
    config: SSOConfigCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> SSOConfigResponse:
    """Create a new SSO configuration (superadmin only)."""
    db_config = SSOConfig(**config.model_dump())
    db.add(db_config)
    await db.commit()
    await db.refresh(db_config)
    return SSOConfigResponse.model_validate(db_config)


@router.get("", response_model=list[SSOConfigResponse])
async def list_sso_configs(
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[SSOConfigResponse]:
    """List all SSO configurations (superadmin only)."""
    result = await db.execute(select(SSOConfig))
    configs = result.scalars().all()
    return [SSOConfigResponse.model_validate(c) for c in configs]


@router.patch("/{config_id}", response_model=SSOConfigResponse)
async def update_sso_config(
    config_id: uuid.UUID,
    config: SSOConfigUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> SSOConfigResponse:
    """Update an SSO configuration (superadmin only)."""
    result = await db.execute(select(SSOConfig).where(SSOConfig.id == config_id))
    db_config = result.scalar_one_or_none()
    if db_config is None:
        raise HTTPException(status_code=404, detail="SSO config not found")

    update_data = config.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    await db.commit()
    await db.refresh(db_config)
    return SSOConfigResponse.model_validate(db_config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sso_config(
    config_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> None:
    """Delete an SSO configuration (superadmin only)."""
    result = await db.execute(select(SSOConfig).where(SSOConfig.id == config_id))
    db_config = result.scalar_one_or_none()
    if db_config is None:
        raise HTTPException(status_code=404, detail="SSO config not found")

    await db.delete(db_config)
    await db.commit()
