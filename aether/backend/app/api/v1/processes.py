"""Process Runtime API — execute Vela-generated business processes.

Endpoints:
  POST   /processes/{instance_id}/start      — Start a process instance
  POST   /processes/{instance_id}/transition — Move to next block
  POST   /processes/{instance_id}/field      — Set field values
  GET    /processes/{instance_id}            — Get current state
  GET    /processes/                         — List instances for tenant
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc

from app.core.deps import DBDep, CurrentActiveUser
from app.models.process_runtime import ProcessInstance, ProcessTransition
from app.models.services import ServiceInstance

router = APIRouter(prefix="/api/v1/processes", tags=["process-runtime"])


# ── Schemas ──────────────────────────────────────────────────────────

class StartProcessRequest(BaseModel):
    service_instance_id: uuid.UUID | None = None
    process_definition: dict = Field(..., description="Full process JSON from Vela")
    started_by: str | None = None


class TransitionRequest(BaseModel):
    to_block: str = Field(..., description="Target block key")
    label: str | None = None
    triggered_by: str = "user"


class SetFieldRequest(BaseModel):
    block_key: str
    field_key: str
    value: str | int | float | bool | None


class ProcessInstanceResponse(BaseModel):
    id: uuid.UUID
    state: str
    current_block_key: str | None
    field_values: dict
    execution_log: list
    started_at: datetime
    completed_at: datetime | None


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/start", response_model=ProcessInstanceResponse, status_code=201)
async def start_process(
    body: StartProcessRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Start a new process instance for the current tenant."""
    tenant_id = current_user.tenant_id

    # Find the first block (start)
    blocks = body.process_definition.get("blocks", [])
    start_block = next((b for b in blocks if b.get("block_type") == "start"), blocks[0] if blocks else None)
    if not start_block:
        raise HTTPException(status_code=422, detail="Process definition has no blocks")

    instance = ProcessInstance(
        tenant_id=tenant_id,
        service_instance_id=body.service_instance_id,
        process_definition=body.process_definition,
        current_block_key=start_block["key"],
        state="active",
        started_by=body.started_by or current_user.email,
        execution_log=[{
            "block_key": start_block["key"],
            "action": "enter",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": body.started_by or current_user.email,
        }],
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    return ProcessInstanceResponse(
        id=instance.id,
        state=instance.state,
        current_block_key=instance.current_block_key,
        field_values=instance.field_values,
        execution_log=instance.execution_log,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
    )


@router.post("/{instance_id}/transition", response_model=ProcessInstanceResponse)
async def transition_process(
    instance_id: uuid.UUID,
    body: TransitionRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Move the process to the next block."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "active":
        raise HTTPException(status_code=409, detail=f"Process is {instance.state}")

    # Validate target block exists in definition
    blocks = instance.process_definition.get("blocks", [])
    target_block = next((b for b in blocks if b["key"] == body.to_block), None)
    if not target_block:
        raise HTTPException(status_code=422, detail=f"Block '{body.to_block}' not found in process")

    # Validate connection exists
    connections = instance.process_definition.get("connections", [])
    valid = any(
        c.get("source") == instance.current_block_key and c.get("target") == body.to_block
        for c in connections
    )
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"No connection from '{instance.current_block_key}' to '{body.to_block}'",
        )

    # Record transition
    transition = ProcessTransition(
        instance_id=instance.id,
        from_block=instance.current_block_key,
        to_block=body.to_block,
        transition_label=body.label,
        triggered_by=body.triggered_by,
    )
    db.add(transition)

    # Update instance
    old_block = instance.current_block_key
    instance.current_block_key = body.to_block

    # Check if target is end block
    if target_block.get("block_type") == "end":
        instance.state = "completed"
        instance.completed_at = datetime.now(timezone.utc)

    # Log
    log_entry = {
        "block_key": body.to_block,
        "action": "enter",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": body.triggered_by,
    }
    instance.execution_log = (instance.execution_log or []) + [log_entry]

    await db.commit()
    await db.refresh(instance)

    return ProcessInstanceResponse(
        id=instance.id,
        state=instance.state,
        current_block_key=instance.current_block_key,
        field_values=instance.field_values,
        execution_log=instance.execution_log,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
    )


@router.post("/{instance_id}/field", response_model=ProcessInstanceResponse)
async def set_process_field(
    instance_id: uuid.UUID,
    body: SetFieldRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Set a field value for the current block."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "active":
        raise HTTPException(status_code=409, detail=f"Process is {instance.state}")

    field_values = dict(instance.field_values or {})
    block_values = dict(field_values.get(body.block_key, {}))

    # Track delta for audit
    old_value = block_values.get(body.field_key)
    block_values[body.field_key] = body.value
    field_values[body.block_key] = block_values
    instance.field_values = field_values

    # Log the change
    log_entry = {
        "block_key": body.block_key,
        "action": "set_field",
        "field": body.field_key,
        "value": body.value,
        "previous": old_value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": current_user.email,
    }
    instance.execution_log = (instance.execution_log or []) + [log_entry]

    await db.commit()
    await db.refresh(instance)

    return ProcessInstanceResponse(
        id=instance.id,
        state=instance.state,
        current_block_key=instance.current_block_key,
        field_values=instance.field_values,
        execution_log=instance.execution_log,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
    )


@router.get("/{instance_id}", response_model=ProcessInstanceResponse)
async def get_process_instance(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Get current state of a process instance."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")

    return ProcessInstanceResponse(
        id=instance.id,
        state=instance.state,
        current_block_key=instance.current_block_key,
        field_values=instance.field_values,
        execution_log=instance.execution_log,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
    )


@router.get("/", response_model=list[ProcessInstanceResponse])
async def list_process_instances(
    db: DBDep,
    current_user: CurrentActiveUser,
    state_filter: str | None = Query(None, alias="state"),
    limit: int = Query(20, le=100),
) -> list[ProcessInstanceResponse]:
    """List process instances for current tenant."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.tenant_id == current_user.tenant_id
    )
    if state_filter:
        stmt = stmt.where(ProcessInstance.state == state_filter)
    stmt = stmt.order_by(desc(ProcessInstance.started_at)).limit(limit)

    result = await db.execute(stmt)
    instances = result.scalars().all()

    return [
        ProcessInstanceResponse(
            id=i.id,
            state=i.state,
            current_block_key=i.current_block_key,
            field_values=i.field_values,
            execution_log=i.execution_log,
            started_at=i.started_at,
            completed_at=i.completed_at,
        )
        for i in instances
    ]


@router.post("/{instance_id}/generate-document")
async def generate_document(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
    block_key: str | None = Query(None),
) -> dict:
    """Generate a document for a process block. Fills placeholders with field values.

    For blocks of type 'document' with config.start_actions containing generate_docx,
    this endpoint renders the template with field_values from the process instance.
    """
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")

    # Find document blocks
    blocks = instance.process_definition.get("blocks", [])
    if block_key:
        blocks = [b for b in blocks if b["key"] == block_key]

    doc_blocks = [b for b in blocks if b.get("block_type") == "document"]
    if not doc_blocks:
        raise HTTPException(status_code=422, detail="No document blocks found in process")

    generated = []
    for block in doc_blocks:
        config = block.get("config", {})
        actions = config.get("start_actions", []) + config.get("end_actions", [])
        doc_actions = [a for a in actions if a.get("type") == "generate_docx"]

        for action in doc_actions:
            template_name = action.get("template", f"{block.get('label', 'document')}.docx")
            placeholders = action.get("placeholders", [])

            # Fill placeholders from field_values
            filled = {}
            block_values = instance.field_values.get(block["key"], {})
            for ph in placeholders:
                filled[ph] = block_values.get(ph, f"{{{ph}}}")

            # Also fill from all field_values
            for bk, fields in instance.field_values.items():
                for fk, fv in fields.items():
                    if fk not in filled:
                        filled[fk] = fv

            generated.append({
                "block_key": block["key"],
                "template": template_name,
                "placeholders": filled,
                "status": "pending",  # Real rendering would happen async
            })

    # Log
    log_entry = {
        "action": "generate_doc",
        "blocks": list(set(g["block_key"] for g in generated)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": current_user.email,
    }
    instance.execution_log = (instance.execution_log or []) + [log_entry]
    await db.commit()

    return {
        "instance_id": str(instance.id),
        "documents": generated,
        "status": "generated",
    }
