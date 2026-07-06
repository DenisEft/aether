"""AI model endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
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


@router.get("/models", response_model=list[AIModelResponse])
async def list_ai_models(
    db: DBDep,
    current_user: CurrentActiveUser,
    provider: str | None = Query(None),
) -> list[AIModelResponse]:
    """List AI models (tenant or global)."""
    stmt = select(AIModel).where(
        (AIModel.tenant_id == current_user.tenant_id) | (AIModel.tenant_id.is_(None))
    )
    if provider is not None:
        stmt = stmt.where(AIModel.provider == provider)
    stmt = stmt.order_by(AIModel.provider, AIModel.default_priority.desc())
    result = await db.execute(stmt)
    return [AIModelResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/models", response_model=AIModelResponse, status_code=201)
async def create_ai_model(
    body: AIModelCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> AIModelResponse:
    """Register an AI model."""
    model = AIModel(
        tenant_id=current_user.tenant_id,
        model_id=body.model_id,
        provider=body.provider,
        display_name=body.display_name,
        capability=body.capability,
        is_active=body.is_active,
        default_priority=body.default_priority,
        config=body.config,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.patch("/models/{model_id}", response_model=AIModelResponse)
async def update_ai_model(
    model_id: uuid.UUID,
    body: AIModelUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> AIModelResponse:
    """Update an AI model."""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    if body.provider is not None:
        model.provider = body.provider
    if body.display_name is not None:
        model.display_name = body.display_name
    if body.capability is not None:
        model.capability = body.capability
    if body.is_active is not None:
        model.is_active = body.is_active
    if body.default_priority is not None:
        model.default_priority = body.default_priority
    if body.config is not None:
        model.config = body.config

    await db.commit()
    await db.refresh(model)
    return AIModelResponse.model_validate(model)


@router.delete("/models/{model_id}", status_code=200)
async def delete_ai_model(
    model_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an AI model."""
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    await db.delete(model)
    await db.commit()
    return {"message": "Model deleted"}
