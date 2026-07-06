"""Knowledge base endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
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


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[KnowledgeBaseResponse]:
    """List knowledge bases for the current tenant."""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.tenant_id == current_user.tenant_id)
        .order_by(KnowledgeBase.name)
    )
    return [KnowledgeBaseResponse.model_validate(k) for k in result.scalars().all()]


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=201)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Create a new knowledge base."""
    kb = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
        vector_dim=body.vector_dim,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Get knowledge base details."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    return KnowledgeBaseResponse.model_validate(kb)


@router.patch("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    body: KnowledgeBaseUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseResponse:
    """Update a knowledge base."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.embedding_model is not None:
        kb.embedding_model = body.embedding_model
    if body.document_count is not None:
        kb.document_count = body.document_count
    if body.vector_dim is not None:
        kb.vector_dim = body.vector_dim

    await db.commit()
    await db.refresh(kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.delete("/knowledge-bases/{kb_id}", status_code=200)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete a knowledge base."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.tenant_id == current_user.tenant_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    await db.delete(kb)
    await db.commit()
    return {"message": "Knowledge base deleted"}


# ── Knowledge Documents ──────────────────────────────────────


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    kb_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[KnowledgeDocumentResponse]:
    """List documents in a knowledge base."""
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.tenant_id == current_user.tenant_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [KnowledgeDocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
)
async def create_knowledge_document(
    kb_id: uuid.UUID,
    body: KnowledgeDocumentCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> KnowledgeDocumentResponse:
    """Upload a document to a knowledge base."""
    doc = KnowledgeDocument(
        tenant_id=current_user.tenant_id,
        knowledge_base_id=kb_id,
        title=body.title,
        content=body.content,
        source_url=body.source_url,
        file_type=body.file_type,
        chunk_count=body.chunk_count,
        tokens_total=body.tokens_total,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return KnowledgeDocumentResponse.model_validate(doc)


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}", status_code=200)
async def delete_knowledge_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete a document from a knowledge base."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.tenant_id == current_user.tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted"}
