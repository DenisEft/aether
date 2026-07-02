"""AI Core endpoints: intents, entities, AI models, drivers, knowledge bases."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func

from app.core.deps import DBDep, CurrentActiveUser, CurrentSuperuser
from app.models.ai import (
    AIModel,
    DriverConfig,
    DriverMetric,
    EntityType,
    Intent,
    IntentTemplate,
    KnowledgeBase,
    KnowledgeDocument,
)
from app.schemas.ai import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
    DriverConfigCreate,
    DriverConfigResponse,
    DriverConfigUpdate,
    DriverMetricResponse,
    EntityTypeCreate,
    EntityTypeResponse,
    EntityTypeUpdate,
    IntentCreate,
    IntentResponse,
    IntentUpdate,
    IntentTemplateCreate,
    IntentTemplateResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
)

router = APIRouter(tags=["ai"])


# ─────────────────────────────────────────────────────────────
# INTENTS (tenant-scoped)
# ─────────────────────────────────────────────────────────────

@router.get("/intents", response_model=list[IntentResponse])
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


@router.post("/intents", response_model=IntentResponse, status_code=201)
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


@router.get("/intents/{intent_id}", response_model=IntentResponse)
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


@router.patch("/intents/{intent_id}", response_model=IntentResponse)
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


@router.delete("/intents/{intent_id}", status_code=200)
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

@router.get("/intents/{intent_id}/templates", response_model=list[IntentTemplateResponse])
async def list_intent_templates(
    intent_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[IntentTemplateResponse]:
    """List templates for an intent."""
    result = await db.execute(
        select(IntentTemplate).where(
            IntentTemplate.tenant_id == current_user.tenant_id,
            IntentTemplate.intent_id == intent_id,
        ).order_by(IntentTemplate.language)
    )
    return [IntentTemplateResponse.model_validate(t) for t in result.scalars().all()]


@router.post("/intents/{intent_id}/templates", response_model=IntentTemplateResponse, status_code=201)
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
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return IntentTemplateResponse.model_validate(tmpl)


@router.delete("/intents/{intent_id}/templates/{template_id}", status_code=200)
async def delete_intent_template(
    intent_id: uuid.UUID,
    template_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete an intent template."""
    result = await db.execute(
        select(IntentTemplate).where(
            IntentTemplate.id == template_id,
            IntentTemplate.intent_id == intent_id,
            IntentTemplate.tenant_id == current_user.tenant_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    await db.delete(tmpl)
    await db.commit()
    return {"message": "Template deleted"}


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
    result = await db.execute(
        select(AIModel).where(AIModel.id == model_id)
    )
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
    result = await db.execute(
        select(AIModel).where(AIModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    await db.delete(model)
    await db.commit()
    return {"message": "Model deleted"}


# ─────────────────────────────────────────────────────────────
# DRIVER CONFIGS (global — superuser only)
# ─────────────────────────────────────────────────────────────

@router.get("/drivers", response_model=list[DriverConfigResponse])
async def list_drivers(
    db: DBDep,
    current_user: CurrentSuperuser,
) -> list[DriverConfigResponse]:
    """List all AI driver configs (superuser only)."""
    result = await db.execute(
        select(DriverConfig).order_by(DriverConfig.driver_type)
    )
    return [DriverConfigResponse.model_validate(d) for d in result.scalars().all()]


@router.post("/drivers", response_model=DriverConfigResponse, status_code=201)
async def create_driver(
    body: DriverConfigCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Register a new AI driver (superuser only)."""
    driver = DriverConfig(
        driver_type=body.driver_type,
        endpoint=body.endpoint,
        config=body.config,
    )
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return DriverConfigResponse.model_validate(driver)


@router.get("/drivers/{driver_id}", response_model=DriverConfigResponse)
async def get_driver(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Get driver config details (superuser only)."""
    result = await db.execute(
        select(DriverConfig).where(DriverConfig.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    return DriverConfigResponse.model_validate(driver)


@router.patch("/drivers/{driver_id}", response_model=DriverConfigResponse)
async def update_driver(
    driver_id: uuid.UUID,
    body: DriverConfigUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> DriverConfigResponse:
    """Update a driver config (superuser only)."""
    result = await db.execute(
        select(DriverConfig).where(DriverConfig.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    if body.endpoint is not None:
        driver.endpoint = body.endpoint
    if body.is_healthy is not None:
        driver.is_healthy = body.is_healthy
    if body.error_message is not None:
        driver.error_message = body.error_message
    if body.config is not None:
        driver.config = body.config

    await db.commit()
    await db.refresh(driver)
    return DriverConfigResponse.model_validate(driver)


@router.delete("/drivers/{driver_id}", status_code=200)
async def delete_driver(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a driver config (superuser only)."""
    result = await db.execute(
        select(DriverConfig).where(DriverConfig.id == driver_id)
    )
    driver = result.scalar_one_or_none()
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    await db.delete(driver)
    await db.commit()
    return {"message": "Driver deleted"}


# ── Driver Metrics (read-only) ───────────────────────────────

@router.get("/drivers/{driver_id}/metrics", response_model=list[DriverMetricResponse])
async def get_driver_metrics(
    driver_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
    limit: int = Query(default=100, le=1000),
) -> list[DriverMetricResponse]:
    """Get recent metrics for a driver (superuser only)."""
    result = await db.execute(
        select(DriverMetric)
        .where(DriverMetric.driver_config_id == driver_id)
        .order_by(DriverMetric.recorded_at.desc())
        .limit(limit)
    )
    return [DriverMetricResponse.model_validate(m) for m in result.scalars().all()]


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

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


@router.post("/knowledge-bases/{kb_id}/documents", response_model=KnowledgeDocumentResponse, status_code=201)
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


# === Inference Endpoints ===

from pydantic import BaseModel, Field
from typing import Optional
from app.ai.router import RoutingStrategy
from app.ai.manager import ai_manager


class InferencePayload(BaseModel):
    messages: list[dict]
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=32768)
    stream: bool = False
    strategy: RoutingStrategy = RoutingStrategy.LEAST_LATENCY


@router.post("/infer")
async def run_inference(
    payload: InferencePayload,
    current_user: CurrentActiveUser,
):
    """Run AI inference through the smart router."""
    response = await ai_manager.generate_response(
        messages=payload.messages,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        strategy=payload.strategy,
    )
    return {
        "model": response.model,
        "driver": response.driver_type,
        "content": response.content,
        "finish_reason": response.finish_reason,
        "usage": response.usage,
        "latency_ms": response.latency_ms,
    }


@router.get("/health-summary")
async def ai_health_summary(
    current_user: CurrentActiveUser,
):
    """Get health status of all AI drivers."""
    return await ai_manager.health_summary()
