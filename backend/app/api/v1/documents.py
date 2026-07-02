"""Document API v1 — CRUD, status transitions, versioning, tags, search."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.services.document_service import (
    DocumentCreate,
    DocumentNotFoundError,
    DocumentService,
    DocumentStatusTransition,
    DocumentUpdate,
    InvalidStatusTransitionError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# ── Pydantic Schemas ─────────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    """Public document representation."""

    id: UUID
    tenant_id: UUID
    type: str
    template_id: UUID | None
    status: str
    title: str | None
    number: str | None
    fields: dict
    field_confidence: dict | None
    overall_confidence: float | None
    source: str
    company_id: UUID | None
    creator_id: UUID | None
    linked_document_ids: list[UUID] | None
    version: int
    is_deleted: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, doc) -> "DocumentResponse":
        return cls(
            id=doc.id,
            tenant_id=doc.tenant_id,
            type=doc.type,
            template_id=doc.template_id,
            status=doc.status,
            title=doc.title,
            number=doc.number,
            fields=doc.fields,
            field_confidence=doc.field_confidence,
            overall_confidence=doc.overall_confidence,
            source=doc.source,
            company_id=doc.company_id,
            creator_id=doc.creator_id,
            linked_document_ids=doc.linked_document_ids,
            version=doc.version,
            is_deleted=doc.is_deleted,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        )


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    documents: list[DocumentResponse]
    has_more: bool
    total: int | None = None


class DocumentCreateRequest(BaseModel):
    """Request body for creating a document."""

    type: str = Field(..., min_length=1, max_length=50, description="Document type key")
    title: str | None = Field(None, max_length=500)
    fields: dict | None = Field(default_factory=dict)
    company_id: UUID | None = None
    source: str = Field("manual", max_length=50)
    template_id: UUID | None = None


class DocumentUpdateRequest(BaseModel):
    """Request body for updating document fields."""

    title: str | None = Field(None, max_length=500)
    fields: dict | None = None
    company_id: UUID | None = None


class StatusTransitionRequest(BaseModel):
    """Request body for status transitions."""

    new_status: str = Field(..., min_length=1, max_length=50)
    comment: str | None = None


class VersionResponse(BaseModel):
    """Document version representation."""

    id: UUID
    document_id: UUID
    version: int
    fields_snapshot: dict
    status: str
    change_description: str | None
    changed_by: UUID | None
    created_at: str

    @classmethod
    def from_orm(cls, ver) -> "VersionResponse":
        return cls(
            id=ver.id,
            document_id=ver.document_id,
            version=ver.version,
            fields_snapshot=ver.fields_snapshot,
            status=ver.status,
            change_description=ver.change_description,
            changed_by=ver.changed_by,
            created_at=ver.created_at.isoformat() if ver.created_at else "",
        )


# ── Dependencies ─────────────────────────────────────────────────────────────


async def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentService:
    """Provide DocumentService with current DB session."""
    return DocumentService(session)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreateRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Create a new document.

    Creates the document, an initial version snapshot, and an operation record.
    """
    data = DocumentCreate(
        tenant_id=current_user.tenant_id,
        type=body.type,
        title=body.title,
        fields=body.fields,
        company_id=body.company_id,
        source=body.source,
    )
    document = await service.create(data, user_id=current_user.id)
    return DocumentResponse.from_orm(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
    type: str | None = Query(None, description="Filter by document type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    company_id: UUID | None = Query(None, description="Filter by company"),
    source: str | None = Query(None, description="Filter by source channel"),
    search: str | None = Query(None, description="Full-text search query"),
    cursor: UUID | None = Query(None, description="Pagination cursor (document ID)"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
) -> DocumentListResponse:
    """List documents with filtering, search, and cursor-based pagination."""
    documents, has_more = await service.list_documents(
        tenant_id=current_user.tenant_id,
        type=type,
        status=status_filter,
        company_id=company_id,
        source=source,
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm(d) for d in documents],
        has_more=has_more,
        total=None,  # Total count is expensive; omit for performance
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Get a single document by ID."""
    try:
        document = await service.get(document_id, current_user.tenant_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    body: DocumentUpdateRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Update document fields. Triggers version snapshot and operation record."""
    data = DocumentUpdate(
        title=body.title,
        fields=body.fields,
        company_id=body.company_id,
    )
    try:
        document = await service.update(document_id, current_user.tenant_id, data, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


@router.post("/{document_id}/transition", response_model=DocumentResponse)
async def transition_document(
    document_id: UUID,
    body: StatusTransitionRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Transition document to a new status.

    Validates against template's status machine. Creates version + operation.
    """
    transition = DocumentStatusTransition(new_status=body.new_status, comment=body.comment)
    try:
        document = await service.transition_status(
            document_id, current_user.tenant_id, transition, current_user.id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete a document (moves to Trash, recoverable for 30 days)."""
    try:
        await service.soft_delete(document_id, current_user.tenant_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/restore", response_model=DocumentResponse)
async def restore_document(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Restore a soft-deleted document from Trash."""
    try:
        document = await service.restore(document_id, current_user.tenant_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


# ── Version History ──────────────────────────────────────────────────────────


@router.get("/{document_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> list[VersionResponse]:
    """List all versions for a document, newest first."""
    try:
        versions = await service.get_versions(document_id, current_user.tenant_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [VersionResponse.from_orm(v) for v in versions]


@router.post("/{document_id}/versions/{version}/restore", response_model=DocumentResponse)
async def rollback_version(
    document_id: UUID,
    version: int,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Restore document to a historical version."""
    try:
        document = await service.rollback_to_version(
            document_id, version, current_user.tenant_id, current_user.id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


# ── Tags ─────────────────────────────────────────────────────────────────────


@router.post("/{document_id}/tags", response_model=DocumentResponse)
async def add_tag(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
    tag_name: str = Query(..., description="Tag name to add"),
) -> DocumentResponse:
    """Add a tag to a document. Creates the tag if it doesn't exist."""
    try:
        document = await service.add_tag(document_id, current_user.tenant_id, tag_name)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)


@router.delete("/{document_id}/tags", response_model=DocumentResponse)
async def remove_tag(
    document_id: UUID,
    service: Annotated[DocumentService, Depends(get_document_service)],
    current_user: User = Depends(get_current_user),
    tag_name: str = Query(..., description="Tag name to remove"),
) -> DocumentResponse:
    """Remove a tag from a document."""
    try:
        document = await service.remove_tag(document_id, current_user.tenant_id, tag_name)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.from_orm(document)
