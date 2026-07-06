"""Service endpoints: definitions, instances, bindings, executions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, CurrentSuperuser, DBDep
from app.models.services import (
    ServiceBinding,
    ServiceDefinition,
    ServiceExecution,
    ServiceInstance,
)
from app.schemas.services import (
    ServiceBindingCreate,
    ServiceBindingResponse,
    ServiceBindingUpdate,
    ServiceDefinitionCreate,
    ServiceDefinitionResponse,
    ServiceDefinitionUpdate,
    ServiceExecutionCreate,
    ServiceExecutionResponse,
    ServiceExecutionUpdate,
    ServiceInstanceCreate,
    ServiceInstanceResponse,
    ServiceInstanceUpdate,
)

router = APIRouter(tags=["services"])


# ─────────────────────────────────────────────────────────────
# SERVICE DEFINITIONS (global — superuser manages, active user reads)
# ─────────────────────────────────────────────────────────────


@router.get("/services/definitions", response_model=list[ServiceDefinitionResponse])
async def list_service_definitions(
    db: DBDep,
    current_user: CurrentActiveUser,
    is_active: bool | None = Query(None),
) -> list[ServiceDefinitionResponse]:
    """List available service definitions."""
    stmt = select(ServiceDefinition)
    if is_active is not None:
        stmt = stmt.where(ServiceDefinition.is_active == is_active)
    stmt = stmt.order_by(ServiceDefinition.display_name)
    result = await db.execute(stmt)
    return [ServiceDefinitionResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/services/definitions", response_model=ServiceDefinitionResponse, status_code=201)
async def create_service_definition(
    body: ServiceDefinitionCreate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> ServiceDefinitionResponse:
    """Register a new service definition (superuser only)."""
    svc = ServiceDefinition(
        plugin_id=body.plugin_id,
        display_name=body.display_name,
        description=body.description,
        version=body.version,
        is_builtin=body.is_builtin,
        is_active=body.is_active,
        capabilities=body.capabilities,
        config_schema=body.config_schema,
    )
    db.add(svc)
    await db.commit()
    await db.refresh(svc)
    return ServiceDefinitionResponse.model_validate(svc)


@router.get("/services/definitions/{definition_id}", response_model=ServiceDefinitionResponse)
async def get_service_definition(
    definition_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceDefinitionResponse:
    """Get service definition details."""
    result = await db.execute(
        select(ServiceDefinition).where(ServiceDefinition.id == definition_id)
    )
    svc = result.scalar_one_or_none()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service definition not found"
        )
    return ServiceDefinitionResponse.model_validate(svc)


@router.patch("/services/definitions/{definition_id}", response_model=ServiceDefinitionResponse)
async def update_service_definition(
    definition_id: uuid.UUID,
    body: ServiceDefinitionUpdate,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> ServiceDefinitionResponse:
    """Update a service definition (superuser only)."""
    result = await db.execute(
        select(ServiceDefinition).where(ServiceDefinition.id == definition_id)
    )
    svc = result.scalar_one_or_none()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service definition not found"
        )

    if body.display_name is not None:
        svc.display_name = body.display_name
    if body.description is not None:
        svc.description = body.description
    if body.version is not None:
        svc.version = body.version
    if body.is_builtin is not None:
        svc.is_builtin = body.is_builtin
    if body.is_active is not None:
        svc.is_active = body.is_active
    if body.capabilities is not None:
        svc.capabilities = body.capabilities
    if body.config_schema is not None:
        svc.config_schema = body.config_schema

    await db.commit()
    await db.refresh(svc)
    return ServiceDefinitionResponse.model_validate(svc)


@router.delete("/services/definitions/{definition_id}", status_code=200)
async def delete_service_definition(
    definition_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Delete a service definition (superuser only)."""
    result = await db.execute(
        select(ServiceDefinition).where(ServiceDefinition.id == definition_id)
    )
    svc = result.scalar_one_or_none()
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service definition not found"
        )

    await db.delete(svc)
    await db.commit()
    return {"message": "Service definition deleted"}


# ─────────────────────────────────────────────────────────────
# SERVICE INSTANCES (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("/services/instances", response_model=list[ServiceInstanceResponse])
async def list_service_instances(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[ServiceInstanceResponse]:
    """List service instances for the current tenant."""
    result = await db.execute(
        select(ServiceInstance)
        .where(ServiceInstance.tenant_id == current_user.tenant_id)
        .order_by(ServiceInstance.installed_at.desc())
    )
    return [ServiceInstanceResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/services/instances", response_model=ServiceInstanceResponse, status_code=201)
async def create_service_instance(
    body: ServiceInstanceCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceInstanceResponse:
    """Install a service instance for the current tenant."""
    instance = ServiceInstance(
        tenant_id=current_user.tenant_id,
        service_definition_id=body.service_definition_id,
        config=body.config,
        is_active=body.is_active,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return ServiceInstanceResponse.model_validate(instance)


@router.get("/services/instances/{instance_id}", response_model=ServiceInstanceResponse)
async def get_service_instance(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceInstanceResponse:
    """Get service instance details."""
    result = await db.execute(
        select(ServiceInstance).where(
            ServiceInstance.id == instance_id,
            ServiceInstance.tenant_id == current_user.tenant_id,
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service instance not found"
        )
    return ServiceInstanceResponse.model_validate(instance)


@router.patch("/services/instances/{instance_id}", response_model=ServiceInstanceResponse)
async def update_service_instance(
    instance_id: uuid.UUID,
    body: ServiceInstanceUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceInstanceResponse:
    """Update a service instance."""
    result = await db.execute(
        select(ServiceInstance).where(
            ServiceInstance.id == instance_id,
            ServiceInstance.tenant_id == current_user.tenant_id,
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service instance not found"
        )

    if body.config is not None:
        instance.config = body.config
    if body.is_active is not None:
        instance.is_active = body.is_active

    await db.commit()
    await db.refresh(instance)
    return ServiceInstanceResponse.model_validate(instance)


@router.delete("/services/instances/{instance_id}", status_code=200)
async def delete_service_instance(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Uninstall a service instance."""
    result = await db.execute(
        select(ServiceInstance).where(
            ServiceInstance.id == instance_id,
            ServiceInstance.tenant_id == current_user.tenant_id,
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service instance not found"
        )

    await db.delete(instance)
    await db.commit()
    return {"message": "Service instance uninstalled"}


# ─────────────────────────────────────────────────────────────
# SERVICE BINDINGS (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("/services/bindings", response_model=list[ServiceBindingResponse])
async def list_service_bindings(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[ServiceBindingResponse]:
    """List service bindings for the current tenant."""
    result = await db.execute(
        select(ServiceBinding)
        .where(ServiceBinding.tenant_id == current_user.tenant_id)
        .order_by(ServiceBinding.priority.desc())
    )
    return [ServiceBindingResponse.model_validate(b) for b in result.scalars().all()]


@router.post("/services/bindings", response_model=ServiceBindingResponse, status_code=201)
async def create_service_binding(
    body: ServiceBindingCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceBindingResponse:
    """Create a binding between a service instance and a channel."""
    binding = ServiceBinding(
        tenant_id=current_user.tenant_id,
        service_instance_id=body.service_instance_id,
        channel_id=body.channel_id,
        priority=body.priority,
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return ServiceBindingResponse.model_validate(binding)


@router.get("/services/bindings/{binding_id}", response_model=ServiceBindingResponse)
async def get_service_binding(
    binding_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceBindingResponse:
    """Get service binding details."""
    result = await db.execute(
        select(ServiceBinding).where(
            ServiceBinding.id == binding_id,
            ServiceBinding.tenant_id == current_user.tenant_id,
        )
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service binding not found"
        )
    return ServiceBindingResponse.model_validate(binding)


@router.patch("/services/bindings/{binding_id}", response_model=ServiceBindingResponse)
async def update_service_binding(
    binding_id: uuid.UUID,
    body: ServiceBindingUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceBindingResponse:
    """Update a service binding."""
    result = await db.execute(
        select(ServiceBinding).where(
            ServiceBinding.id == binding_id,
            ServiceBinding.tenant_id == current_user.tenant_id,
        )
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service binding not found"
        )

    if body.channel_id is not None:
        binding.channel_id = body.channel_id
    if body.priority is not None:
        binding.priority = body.priority

    await db.commit()
    await db.refresh(binding)
    return ServiceBindingResponse.model_validate(binding)


@router.delete("/services/bindings/{binding_id}", status_code=200)
async def delete_service_binding(
    binding_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete a service binding."""
    result = await db.execute(
        select(ServiceBinding).where(
            ServiceBinding.id == binding_id,
            ServiceBinding.tenant_id == current_user.tenant_id,
        )
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service binding not found"
        )

    await db.delete(binding)
    await db.commit()
    return {"message": "Service binding deleted"}


# ─────────────────────────────────────────────────────────────
# SERVICE EXECUTIONS (tenant-scoped)
# ─────────────────────────────────────────────────────────────


@router.get("/services/executions", response_model=list[ServiceExecutionResponse])
async def list_service_executions(
    db: DBDep,
    current_user: CurrentActiveUser,
    conversation_id: uuid.UUID | None = Query(None),
    instance_id: uuid.UUID | None = Query(None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ServiceExecutionResponse]:
    """List service executions for the current tenant."""
    stmt = select(ServiceExecution).where(
        ServiceExecution.tenant_id == current_user.tenant_id,
    )
    if conversation_id is not None:
        stmt = stmt.where(ServiceExecution.conversation_id == conversation_id)
    if instance_id is not None:
        stmt = stmt.where(ServiceExecution.service_instance_id == instance_id)
    stmt = stmt.order_by(ServiceExecution.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [ServiceExecutionResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/services/executions", response_model=ServiceExecutionResponse, status_code=201)
async def create_service_execution(
    body: ServiceExecutionCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceExecutionResponse:
    """Record a service execution."""
    execution = ServiceExecution(
        tenant_id=current_user.tenant_id,
        service_instance_id=body.service_instance_id,
        conversation_id=body.conversation_id,
        intent=body.intent,
        entities=body.entities,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return ServiceExecutionResponse.model_validate(execution)


@router.get("/services/executions/{execution_id}", response_model=ServiceExecutionResponse)
async def get_service_execution(
    execution_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceExecutionResponse:
    """Get service execution details."""
    result = await db.execute(
        select(ServiceExecution).where(
            ServiceExecution.id == execution_id,
            ServiceExecution.tenant_id == current_user.tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service execution not found"
        )
    return ServiceExecutionResponse.model_validate(execution)


@router.patch("/services/executions/{execution_id}", response_model=ServiceExecutionResponse)
async def update_service_execution(
    execution_id: uuid.UUID,
    body: ServiceExecutionUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ServiceExecutionResponse:
    """Update a service execution (e.g. mark result, add metrics)."""
    result = await db.execute(
        select(ServiceExecution).where(
            ServiceExecution.id == execution_id,
            ServiceExecution.tenant_id == current_user.tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service execution not found"
        )

    if body.result is not None:
        execution.result = body.result
    if body.response_text is not None:
        execution.response_text = body.response_text
    if body.duration_ms is not None:
        execution.duration_ms = body.duration_ms
    if body.tokens_used is not None:
        execution.tokens_used = body.tokens_used
    if body.cost_usd is not None:
        execution.cost_usd = body.cost_usd
    if body.error_message is not None:
        execution.error_message = body.error_message

    await db.commit()
    await db.refresh(execution)
    return ServiceExecutionResponse.model_validate(execution)
