"""Entity type endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.ai import EntityType
from app.schemas.ai import (
    EntityTypeCreate,
    EntityTypeResponse,
    EntityTypeUpdate,
)

logger = logging.getLogger("aether.api.ai.entities")
router = APIRouter(tags=["entities"])


# ─────────────────────────────────────────────────────────────
# ENTITY TYPES (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[EntityTypeResponse])
async def list_entity_types(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[EntityTypeResponse]:
    """List entity types for the current tenant."""
    stmt = (
        select(EntityType)
        .where(
            EntityType.tenant_id == current_user.tenant_id,
        )
        .order_by(EntityType.name)
    )
    result = await db.execute(stmt)
    return [EntityTypeResponse.model_validate(e) for e in result.scalars().all()]


@router.post("", response_model=EntityTypeResponse, status_code=201)
async def create_entity_type(
    body: EntityTypeCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Create a new entity type."""
    entity_type = EntityType(
        tenant_id=current_user.tenant_id,
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(entity_type)
    await db.commit()
    await db.refresh(entity_type)
    return EntityTypeResponse.model_validate(entity_type)


@router.get("/{entity_type_id}", response_model=EntityTypeResponse)
async def get_entity_type(
    entity_type_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Get entity type details."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_type_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity_type = result.scalar_one_or_none()
    if entity_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")
    return EntityTypeResponse.model_validate(entity_type)


@router.put("/{entity_type_id}", response_model=EntityTypeResponse)
async def update_entity_type(
    entity_type_id: uuid.UUID,
    body: EntityTypeUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Update an entity type."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_type_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity_type = result.scalar_one_or_none()
    if entity_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")

    if body.display_name is not None:
        entity_type.display_name = body.display_name
    if body.description is not None:
        entity_type.description = body.description
    if body.is_builtin is not None:
        entity_type.is_builtin = body.is_builtin
    if body.plugin_ids is not None:
        entity_type.plugin_ids = body.plugin_ids

    await db.commit()
    await db.refresh(entity_type)
    return EntityTypeResponse.model_validate(entity_type)


@router.delete("/{entity_type_id}", status_code=200)
async def delete_entity_type(
    entity_type_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an entity type."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_type_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity_type = result.scalar_one_or_none()
    if entity_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")

    await db.delete(entity_type)
    await db.commit()
    return {"message": "Entity type deleted"}
