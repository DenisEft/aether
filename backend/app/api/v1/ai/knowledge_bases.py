"""Knowledge base endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.models.ai import KnowledgeBase, KnowledgeDocument
from app.schemas.ai import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
)

logger = logging.getLogger("aether.api.ai.knowledge_bases")
router = APIRouter(tags=["knowledge_bases"])


# ─────────────────────────────────────────────────────────────
# KNOWLEDGE BASES (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[KnowledgeBaseResponse]:
    """List knowledge bases for the current tenant."""
    stmt = (
        select(KnowledgeBase)
        .where(
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
        .order_by(KnowledgeBase.name)
    )
    result = await db.execute(stmt)
    return [KnowledgeBaseResponse.model_validate(kb) for kb in result.scalars().all()]


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Create a new knowledge base."""
    knowledge_base = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    knowledge_base_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Get knowledge base details."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    knowledge_base_id: uuid.UUID,
    body: KnowledgeBaseUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Update a knowledge base."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )

    if body.display_name is not None:
        knowledge_base.display_name = body.display_name
    if body.description is not None:
        knowledge_base.description = body.description
    if body.is_builtin is not None:
        knowledge_base.is_builtin = body.is_builtin
    if body.plugin_ids is not None:
        knowledge_base.plugin_ids = body.plugin_ids

    await db.commit()
    await db.refresh(knowledge_base)
    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.delete("/{knowledge_base_id}", status_code=200)
async def delete_knowledge_base(
    knowledge_base_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete a knowledge base."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    knowledge_base = result.scalar_one_or_none()
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found"
        )

    await db.delete(knowledge_base)
    await db.commit()
    return {"message": "Knowledge base deleted"}


# ── Knowledge Documents ─────────────────────────────────────────


@router.get("/{knowledge_base_id}/documents", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    knowledge_base_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[KnowledgeDocumentResponse]:
    """List documents in a knowledge base."""
    stmt = (
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeDocument.tenant_id == current_user.tenant_id,
        )
        .order_by(KnowledgeDocument.name)
    )
    result = await db.execute(stmt)
    return [KnowledgeDocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.post(
    "/{knowledge_base_id}/documents", response_model=KnowledgeDocumentResponse, status_code=201
)
async def create_knowledge_document(
    knowledge_base_id: uuid.UUID,
    body: KnowledgeDocumentCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeDocumentResponse:
    """Add a new document to a knowledge base."""
    document = KnowledgeDocument(
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        name=body.name,
        content=body.content,
        url=body.url,
        is_builtin=body.is_builtin,
        plugin_ids=body.plugin_ids,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return KnowledgeDocumentResponse.model_validate(document)
