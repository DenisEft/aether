"""Template API v1 — CRUD, activation/deactivation, validation."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.database import get_db
from app.models import User
from app.services.template_service import (
    SystemTemplateProtectedError,
    TemplateCreate,
    TemplateNotFoundError,
    TemplateService,
    TemplateUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


# ── Pydantic Schemas ─────────────────────────────────────────────────────────


class TemplateResponse(BaseModel):
    """Public template representation."""

    id: UUID
    tenant_id: UUID | None
    name: str
    description: str | None
    document_type: str
    icon: str | None
    fields: list[dict]
    statuses: list[dict]
    parsing_config: dict
    pdf_template: str | None
    is_system: bool
    is_public: bool
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, template) -> TemplateResponse:
        return cls(
            id=template.id,
            tenant_id=template.tenant_id,
            name=template.name,
            description=template.description,
            document_type=template.document_type,
            icon=template.icon,
            fields=template.fields,
            statuses=template.statuses,
            parsing_config=template.parsing_config,
            pdf_template=template.pdf_template,
            is_system=template.is_system,
            is_public=template.is_public,
            is_active=template.is_active,
            created_at=template.created_at.isoformat() if template.created_at else "",
            updated_at=template.updated_at.isoformat() if template.updated_at else "",
        )


class TemplateListResponse(BaseModel):
    """Paginated template list."""

    items: list[TemplateResponse]
    total: int


class TemplateCreateRequest(BaseModel):
    """Request body for creating a template."""

    name: str = Field(..., min_length=1, max_length=200)
    document_type: str = Field(..., min_length=1, max_length=50)
    fields: list[dict] = Field(default_factory=list)
    description: str | None = None
    icon: str | None = None
    statuses: list[dict] | None = None
    parsing_config: dict | None = None
    pdf_template: str | None = None
    is_public: bool = False


class TemplateUpdateRequest(BaseModel):
    """Request body for updating a template."""

    name: str | None = None
    description: str | None = None
    icon: str | None = None
    fields: list[dict] | None = None
    statuses: list[dict] | None = None
    parsing_config: dict | None = None
    pdf_template: str | None = None
    is_public: bool | None = None
    is_active: bool | None = None


class TemplateValidateRequest(BaseModel):
    """Request body for validating document fields."""

    fields: dict[str, object] = Field(...)


class TemplateValidateResponse(BaseModel):
    """Response for template validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


# ── Dependencies ─────────────────────────────────────────────────────────────


async def get_template_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateService:
    """Provide TemplateService with current DB session."""
    return TemplateService(session)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreateRequest,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    """Create a new template."""
    data = TemplateCreate(
        tenant_id=current_user.tenant_id,
        name=body.name,
        document_type=body.document_type,
        fields=body.fields,
        description=body.description,
        icon=body.icon,
        statuses=body.statuses,
        parsing_config=body.parsing_config,
        pdf_template=body.pdf_template,
        is_public=body.is_public,
    )
    template = await service.create(data)
    return TemplateResponse.from_orm(template)


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
    document_type: str | None = Query(None, description="Filter by document type"),
    is_active: bool | None = Query(True, description="Filter by active status"),
    search: str | None = Query(None, description="Full-text search query"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
) -> TemplateListResponse:
    """List templates with filtering, search, and pagination."""
    templates, total = await service.list(
        tenant_id=current_user.tenant_id,
        document_type=document_type,
        is_active=is_active,
        search=search,
        offset=offset,
        limit=limit,
    )
    return TemplateListResponse(
        items=[TemplateResponse.from_orm(t) for t in templates],
        total=total,
    )


@router.get("/library", response_model=TemplateListResponse)
async def list_public_templates(
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
    document_type: str | None = Query(None, description="Filter by document type"),
    search: str | None = Query(None, description="Full-text search query"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
) -> TemplateListResponse:
    """List public templates (including system templates)."""
    # For public templates, we use a different filter
    templates, total = await service.list(
        tenant_id=current_user.tenant_id,
        document_type=document_type,
        is_active=True,
        search=search,
        offset=offset,
        limit=limit,
    )
    # Filter out private templates that don't belong to the user's tenant
    # but include system templates (which are public by definition)
    filtered_templates = [
        t for t in templates if t.is_public or t.tenant_id == current_user.tenant_id or t.is_system
    ]
    return TemplateListResponse(
        items=[TemplateResponse.from_orm(t) for t in filtered_templates],
        total=total,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    """Get a single template by ID."""
    try:
        template = await service.get(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TemplateResponse.from_orm(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    body: TemplateUpdateRequest,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    """Partially update a template."""
    data = TemplateUpdate(
        name=body.name,
        description=body.description,
        icon=body.icon,
        fields=body.fields,
        statuses=body.statuses,
        parsing_config=body.parsing_config,
        pdf_template=body.pdf_template,
        is_public=body.is_public,
        is_active=body.is_active,
    )
    try:
        template = await service.update(template_id, current_user.tenant_id, data)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SystemTemplateProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateResponse.from_orm(template)


@router.post("/{template_id}/activate", response_model=TemplateResponse)
async def activate_template(
    template_id: UUID,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    """Activate a template."""
    try:
        template = await service.activate(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SystemTemplateProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateResponse.from_orm(template)


@router.post("/{template_id}/deactivate", response_model=TemplateResponse)
async def deactivate_template(
    template_id: UUID,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    """Deactivate a template."""
    try:
        template = await service.deactivate(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SystemTemplateProtectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TemplateResponse.from_orm(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Soft-delete a template."""
    try:
        await service.delete(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SystemTemplateProtectedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{template_id}/status-options", response_model=list[dict])
async def get_status_options(
    template_id: UUID,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> list[dict]:
    """Get status options for a template."""
    try:
        template = await service.get(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return service.get_status_options(template)


@router.post("/{template_id}/validate", response_model=TemplateValidateResponse)
async def validate_template_fields(
    template_id: UUID,
    body: TemplateValidateRequest,
    service: Annotated[TemplateService, Depends(get_template_service)],
    current_user: User = Depends(get_current_active_user),
) -> TemplateValidateResponse:
    """Validate document fields against a template."""
    try:
        template = await service.get(template_id, current_user.tenant_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    errors = service.validate_fields(template, body.fields)
    return TemplateValidateResponse(valid=len(errors) == 0, errors=errors)
