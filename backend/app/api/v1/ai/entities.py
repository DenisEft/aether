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


@router.get("/entities", response_model=list[EntityTypeResponse])
async def list_entity_types(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[EntityTypeResponse]:
    """List entity types for the current tenant."""
    result = await db.execute(
        select(EntityType)
        .where(EntityType.tenant_id == current_user.tenant_id)
        .order_by(EntityType.name)
    )
    return [EntityTypeResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/entities", response_model=EntityTypeResponse, status_code=201)
async def create_entity_type(
    body: EntityTypeCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Create a new entity type."""
    entity = EntityType(
        tenant_id=current_user.tenant_id,
        name=body.name,
        display_name=body.display_name,
        value_type=body.value_type,
        pattern=body.pattern,
        examples=body.examples,
        lookup_table=body.lookup_table,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return EntityTypeResponse.model_validate(entity)


@router.get("/entities/{entity_id}", response_model=EntityTypeResponse)
async def get_entity_type(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Get entity type details."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")
    return EntityTypeResponse.model_validate(entity)


@router.patch("/entities/{entity_id}", response_model=EntityTypeResponse)
async def update_entity_type(
    entity_id: uuid.UUID,
    body: EntityTypeUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> EntityTypeResponse:
    """Update an entity type."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")

    if body.display_name is not None:
        entity.display_name = body.display_name
    if body.value_type is not None:
        entity.value_type = body.value_type
    if body.pattern is not None:
        entity.pattern = body.pattern
    if body.examples is not None:
        entity.examples = body.examples
    if body.lookup_table is not None:
        entity.lookup_table = body.lookup_table

    await db.commit()
    await db.refresh(entity)
    return EntityTypeResponse.model_validate(entity)


@router.delete("/entities/{entity_id}", status_code=200)
async def delete_entity_type(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an entity type."""
    result = await db.execute(
        select(EntityType).where(
            EntityType.id == entity_id,
            EntityType.tenant_id == current_user.tenant_id,
        )
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")

    await db.delete(entity)
    await db.commit()
    return {"message": "Entity type deleted"}
