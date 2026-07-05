"""Process Runtime API — execute Vela-generated business processes.

Endpoints:
  POST   /processes/start                  — Start a process instance
  POST   /processes/{instance_id}/transition — Move to next block
  POST   /processes/{instance_id}/field      — Set field values (batch)
  GET    /processes/{instance_id}            — Get current state + available transitions
  GET    /processes/                         — List instances for tenant
  POST   /processes/{instance_id}/pause      — Pause execution
  POST   /processes/{instance_id}/resume     — Resume execution
  POST   /processes/{instance_id}/cancel     — Cancel execution
  POST   /processes/{instance_id}/generate-document — Generate document from template
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
    initial_field_values: dict = Field(default_factory=dict, description="Pre-filled field values per block key")
    context: dict = Field(default_factory=dict, description="External context: purchase_id, source, etc.")
    webhook_url: str | None = Field(None, description="Aether will POST state changes to this URL")


class TransitionRequest(BaseModel):
    to_block: str = Field(..., description="Target block key")
    label: str | None = None
    triggered_by: str = "user"
    comment: str | None = Field(None, description="Human comment for this transition")
    field_values: dict | None = Field(None, description="Field values to set during transition")


class SetFieldsRequest(BaseModel):
    block_key: str
    values: dict = Field(..., description="Batch field: {field_key: value, ...}")


class AvailableTransition(BaseModel):
    to_block: str
    label: str | None
    condition: str | None  # future: expression evaluation
    source_port: str = "output"
    target_port: str = "input"


class ProcessInstanceResponse(BaseModel):
    id: uuid.UUID
    state: str
    process_name: str | None = None
    current_block_key: str | None
    current_block_label: str | None
    field_values: dict
    execution_log: list
    available_transitions: list[AvailableTransition] | None = None
    process_definition: dict | None = None
    service_instance_id: uuid.UUID | None = None
    started_by: str | None = None
    started_at: datetime
    completed_at: datetime | None
    context: dict | None = None


# ── Helpers ──────────────────────────────────────────────────────────

def _get_block_by_key(definition: dict, key: str) -> dict | None:
    blocks = definition.get("blocks", [])
    for b in blocks:
        if b["key"] == key:
            return b
    return None


def _get_available_transitions(definition: dict, current_block_key: str) -> list[dict]:
    """Compute available transitions from the current block."""
    connections = definition.get("connections", [])
    transitions: list[dict] = []
    for c in connections:
        source = c.get("source") or c.get("source_block_key", "")
        if source == current_block_key:
            target_key = c.get("target") or c.get("target_block_key", "")
            target_block = _get_block_by_key(definition, target_key)
            transitions.append({
                "to_block": target_key,
                "label": c.get("label", "") or target_block.get("label", "") if target_block else "",
                "condition": c.get("condition", None),
                "source_port": c.get("source_port", "output"),
                "target_port": c.get("target_port", "input"),
            })
    return transitions


def _instance_to_response(instance: ProcessInstance, include_full: bool = False) -> ProcessInstanceResponse:
    """Convert ProcessInstance to API response."""
    definition = instance.process_definition or {}
    current_block = _get_block_by_key(definition, instance.current_block_key) if instance.current_block_key else None
    process_name = definition.get("name") or definition.get("slug", "Process")

    return ProcessInstanceResponse(
        id=instance.id,
        state=instance.state,
        process_name=process_name,
        current_block_key=instance.current_block_key,
        current_block_label=current_block.get("label") if current_block else None,
        field_values=instance.field_values if isinstance(instance.field_values, dict) else {},
        execution_log=instance.execution_log if isinstance(instance.execution_log, list) else [],
        available_transitions=_get_available_transitions(definition, instance.current_block_key)
            if instance.state == "active" else None,
        process_definition=definition if include_full else None,
        service_instance_id=instance.service_instance_id,
        started_by=instance.started_by,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
        context=instance.context if isinstance(instance.context, dict) else None,
    )


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/start", response_model=ProcessInstanceResponse, status_code=201)
async def start_process(
    body: StartProcessRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Start a new process instance for the current tenant.

    Takes a full process_definition JSON from Vela and creates a ProcessInstance.
    Optionally accepts initial_field_values and context (purchase_id, source, etc.).
    """
    tenant_id = current_user.tenant_id

    # Validate definition has blocks
    blocks = body.process_definition.get("blocks", [])
    if not blocks:
        raise HTTPException(status_code=422, detail="Process definition has no blocks")

    # Find entry block: prefer 'start' type, fallback to first block
    start_block = next((b for b in blocks if b.get("block_type") == "start"), None)
    if not start_block:
        start_block = blocks[0]

    # Build context
    ctx = dict(body.context or {})
    ctx["source"] = ctx.get("source", "api")
    if body.webhook_url:
        ctx["webhook_url"] = body.webhook_url

    # Merge initial field values
    field_values = dict(body.initial_field_values or {})

    instance = ProcessInstance(
        tenant_id=tenant_id,
        service_instance_id=body.service_instance_id,
        process_definition=body.process_definition,
        current_block_key=start_block["key"],
        state="active",
        started_by=body.started_by or current_user.email,
        field_values=field_values,
        context=ctx,
        source_system="vela",
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

    # TODO: emit WS event process.started
    return _instance_to_response(instance, include_full=True)


@router.post("/{instance_id}/transition", response_model=ProcessInstanceResponse)
async def transition_process(
    instance_id: uuid.UUID,
    body: TransitionRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Move the process to the next block with optional field values and comment."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "active":
        raise HTTPException(status_code=409, detail=f"Process is {instance.state}")

    # Validate target block exists in definition
    target_block = _get_block_by_key(instance.process_definition, body.to_block)
    if not target_block:
        raise HTTPException(status_code=422, detail=f"Block '{body.to_block}' not found in process")

    # Validate connection exists
    valid = any(
        t["to_block"] == body.to_block
        for t in _get_available_transitions(instance.process_definition, instance.current_block_key)
    )
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"No connection from '{instance.current_block_key}' to '{body.to_block}'",
        )

    # Apply field_values passed with transition
    if body.field_values:
        all_values = dict(instance.field_values or {})
        for bk, fields in body.field_values.items():
            if bk not in all_values:
                all_values[bk] = {}
            all_values[bk].update(fields)
        instance.field_values = all_values

    # Record transition
    transition = ProcessTransition(
        instance_id=instance.id,
        from_block=instance.current_block_key,
        to_block=body.to_block,
        transition_label=body.label,
        triggered_by=body.triggered_by,
        comment=body.comment,
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
        "action": "transition",
        "from": old_block,
        "label": body.label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": body.triggered_by,
    }
    instance.execution_log = (instance.execution_log or []) + [log_entry]

    await db.commit()
    await db.refresh(instance)

    # TODO: emit WS event process.transitioned
    return _instance_to_response(instance, include_full=True)


@router.post("/{instance_id}/field", response_model=ProcessInstanceResponse)
async def set_process_fields(
    instance_id: uuid.UUID,
    body: SetFieldsRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Set field values for a block (batch update)."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "active":
        raise HTTPException(status_code=409, detail=f"Process is {instance.state}")

    field_values = dict(instance.field_values or {})
    block_values = dict(field_values.get(body.block_key, {}))

    # Track deltas for audit
    deltas = {}
    for fk, fv in body.values.items():
        old = block_values.get(fk)
        deltas[fk] = {"old": old, "new": fv}
        block_values[fk] = fv

    field_values[body.block_key] = block_values
    instance.field_values = field_values

    # Log the changes
    for fk, fv in body.values.items():
        log_entry = {
            "block_key": body.block_key,
            "action": "set_field",
            "field": fk,
            "value": fv,
            "previous": deltas[fk]["old"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": current_user.email,
        }
        instance.execution_log = (instance.execution_log or []) + [log_entry]

    await db.commit()
    await db.refresh(instance)

    # TODO: emit WS event process.field_updated
    return _instance_to_response(instance, include_full=True)


@router.get("/{instance_id}", response_model=ProcessInstanceResponse)
async def get_process_instance(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
    include_definition: bool = Query(False),
) -> ProcessInstanceResponse:
    """Get current state of a process instance, including available transitions."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")

    return _instance_to_response(instance, include_full=include_definition)


@router.get("/", response_model=list[ProcessInstanceResponse])
async def list_process_instances(
    db: DBDep,
    current_user: CurrentActiveUser,
    state_filter: str | None = Query(None, alias="state"),
    service_instance_id: uuid.UUID | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
) -> list[ProcessInstanceResponse]:
    """List process instances for current tenant."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.tenant_id == current_user.tenant_id
    )
    if state_filter:
        stmt = stmt.where(ProcessInstance.state == state_filter)
    if service_instance_id:
        stmt = stmt.where(ProcessInstance.service_instance_id == service_instance_id)
    stmt = stmt.order_by(desc(ProcessInstance.started_at)).offset(offset).limit(limit)

    result = await db.execute(stmt)
    instances = result.scalars().all()

    return [_instance_to_response(i) for i in instances]


@router.post("/{instance_id}/pause", response_model=ProcessInstanceResponse)
async def pause_process(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Pause a running process."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "active":
        raise HTTPException(status_code=409, detail=f"Cannot pause: process is {instance.state}")

    instance.state = "paused"
    instance.execution_log = (instance.execution_log or []) + [{
        "action": "pause",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": current_user.email,
    }]
    await db.commit()
    await db.refresh(instance)

    # TODO: emit WS event process.paused
    return _instance_to_response(instance)


@router.post("/{instance_id}/resume", response_model=ProcessInstanceResponse)
async def resume_process(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Resume a paused process."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state != "paused":
        raise HTTPException(status_code=409, detail=f"Cannot resume: process is {instance.state}")

    instance.state = "active"
    instance.execution_log = (instance.execution_log or []) + [{
        "action": "resume",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": current_user.email,
    }]
    await db.commit()
    await db.refresh(instance)

    # TODO: emit WS event process.resumed
    return _instance_to_response(instance)


@router.post("/{instance_id}/cancel", response_model=ProcessInstanceResponse)
async def cancel_process(
    instance_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ProcessInstanceResponse:
    """Cancel a running or paused process."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance or instance.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.state not in ("active", "paused"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel: process is {instance.state}")

    instance.state = "cancelled"
    instance.completed_at = datetime.now(timezone.utc)
    instance.execution_log = (instance.execution_log or []) + [{
        "action": "cancel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": current_user.email,
    }]
    await db.commit()
    await db.refresh(instance)

    # TODO: emit WS event process.cancelled
    return _instance_to_response(instance)


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
                "status": "pending",
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
