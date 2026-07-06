"""Intent endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.ai import Intent, IntentTemplate
from app.schemas.ai import (
    IntentCreate,
    IntentResponse,
    IntentTemplateCreate,
    IntentTemplateResponse,
    IntentUpdate,
)

logger = logging.getLogger("aether.api.ai.intents")
router = APIRouter(tags=["intents"])


# ─────────────────────────────────────────────────────────────
# INTENTS (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[IntentResponse])
async def list_intents(
    db: DBDep,
    current_user: CurrentActiveUser,
    category: str | None = Query(None),
    is_builtin: bool | None = Query(None),
) -> list[IntentResponse]:
    """List intents for the current tenant."""
    stmt = select(Intent).where(
        Intent.tenant_id == current_user.tenant_id,
    )
    if category is not None:
        stmt = stmt.where(Intent.category == category)
    if is_builtin is not None:
        stmt = stmt.where(Intent.is_builtin == is_builtin)
    stmt = stmt.order_by(Intent.category, Intent.name)
    result = await db.execute(stmt)
    return [IntentResponse.model_validate(i) for i in result.scalars().all()]


@router.post("", response_model=IntentResponse, status_code=201)
async def create_intent(
    body: IntentCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> IntentResponse:
    """Create a new intent."""
    intent = Intent(
        tenant_id=current_user.tenant_id,
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        category=body.category,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(intent)
    await db.commit()
    await db.refresh(intent)
    return IntentResponse.model_validate(intent)


@router.get("/{intent_id}", response_model=IntentResponse)
async def get_intent(
    intent_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> IntentResponse:
    """Get intent details."""
    result = await db.execute(
        select(Intent).where(
            Intent.id == intent_id,
            Intent.tenant_id == current_user.tenant_id,
        )
    )
    intent = result.scalar_one_or_none()
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found")
    return IntentResponse.model_validate(intent)


@router.patch("/{intent_id}", response_model=IntentResponse)
async def update_intent(
    intent_id: uuid.UUID,
    body: IntentUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> IntentResponse:
    """Update an intent."""
    result = await db.execute(
        select(Intent).where(
            Intent.id == intent_id,
            Intent.tenant_id == current_user.tenant_id,
        )
    )
    intent = result.scalar_one_or_none()
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found")

    if body.display_name is not None:
        intent.display_name = body.display_name
    if body.description is not None:
        intent.description = body.description
    if body.category is not None:
        intent.category = body.category
    if body.is_builtin is not None:
        intent.is_builtin = body.is_builtin
    if body.plugin_ids is not None:
        intent.plugin_ids = body.plugin_ids

    await db.commit()
    await db.refresh(intent)
    return IntentResponse.model_validate(intent)


@router.delete("/{intent_id}", status_code=200)
async def delete_intent(
    intent_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an intent."""
    result = await db.execute(
        select(Intent).where(
            Intent.id == intent_id,
            Intent.tenant_id == current_user.tenant_id,
        )
    )
    intent = result.scalar_one_or_none()
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found")

    await db.delete(intent)
    await db.commit()
    return {"message": "Intent deleted"}


# ── Intent Templates ─────────────────────────────────────────


@router.get("/{intent_id}/templates", response_model=list[IntentTemplateResponse])
async def list_intent_templates(
    intent_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[IntentTemplateResponse]:
    """List templates for an intent."""
    result = await db.execute(
        select(IntentTemplate)
        .where(
            IntentTemplate.tenant_id == current_user.tenant_id,
            IntentTemplate.intent_id == intent_id,
        )
        .order_by(IntentTemplate.language)
    )
    return [IntentTemplateResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/{intent_id}/templates", response_model=IntentTemplateResponse, status_code=201)
async def create_intent_template(
    intent_id: uuid.UUID,
    body: IntentTemplateCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> IntentTemplateResponse:
    """Add a new example template to an intent."""
    tmpl = IntentTemplate(
        tenant_id=current_user.tenant_id,
        intent_id=intent_id,
        example_text=body.example_text,
        language=body.language,
        is_default=body.is_default,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return IntentTemplateResponse.model_validate(tmpl)
