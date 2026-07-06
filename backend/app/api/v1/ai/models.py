"""AI model endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.ai import AIModel
from app.schemas.ai import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
)

logger = logging.getLogger("aether.api.ai.models")
router = APIRouter(tags=["models"])


# ─────────────────────────────────────────────────────────────
# AI MODELS (tenant-optional)
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[AIModelResponse])
async def list_ai_models(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[AIModelResponse]:
    """List AI models for the current tenant."""
    stmt = (
        select(AIModel)
        .where(
            AIModel.tenant_id == current_user.tenant_id,
        )
        .order_by(AIModel.name)
    )
    result = await db.execute(stmt)
    return [AIModelResponse.model_validate(m) for m in result.scalars().all()]


@router.post("", response_model=AIModelResponse, status_code=201)
async def create_ai_model(
    body: AIModelCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> AIModelResponse:
    """Create a new AI model."""
    model = AIModel(
        tenant_id=current_user.tenant_id,
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        provider=body.provider,
        model_id=body.model_id,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.put("/{model_id}", response_model=AIModelResponse)
async def update_ai_model(
    model_id: uuid.UUID,
    body: AIModelUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> AIModelResponse:
    """Update an AI model."""
    result = await db.execute(
        select(AIModel).where(
            AIModel.id == model_id,
            AIModel.tenant_id == current_user.tenant_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model not found")

    if body.display_name is not None:
        model.display_name = body.display_name
    if body.description is not None:
        model.description = body.description
    if body.provider is not None:
        model.provider = body.provider
    if body.model_id is not None:
        model.model_id = body.model_id
    if body.is_builtin is not None:
        model.is_builtin = body.is_builtin
    if body.plugin_ids is not None:
        model.plugin_ids = body.plugin_ids

    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.delete("/{model_id}", status_code=200)
async def delete_ai_model(
    model_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an AI model."""
    result = await db.execute(
        select(AIModel).where(
            AIModel.id == model_id,
            AIModel.tenant_id == current_user.tenant_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model not found")

    await db.delete(model)
    await db.commit()
    return {"message": "AI model deleted"}
