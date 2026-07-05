"""Vela Process Publishing endpoint — M2M protected.

Accepts ProcessDefinitions from Vela and stores them as ServiceInstances
with full process graph in config JSONB.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.core.security import decode_token
from app.dependencies import DbSession
from app.database import get_db as _get_db
from app.models.services import ServiceDefinition, ServiceInstance
from sqlalchemy import select
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

router = APIRouter(prefix="/services", tags=["publish"])

security = HTTPBearer(auto_error=False)


class PublishRequest(BaseModel):
    """Payload from Vela: process definition to publish as Aether service."""
    name: str
    slug: str
    description: str = ""
    blocks: list[dict]
    connections: list[dict]
    pages: list[dict] = []
    source: str = "vela"
    vela_process_id: str = ""


class PublishResponse(BaseModel):
    service_id: str
    status: str
    message: str = ""


async def verify_m2m_scope(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    required_scope: str = "processbot:deploy",
) -> dict:
    """Verify M2M token has the required scope."""
    if credentials is None:
        raise HTTPException(401, "Authorization required")

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Invalid token")

    if payload.get("type") != "m2m":
        raise HTTPException(403, "M2M token required")

    scopes: list[str] = payload.get("scopes", [])
    if required_scope not in scopes:
        raise HTTPException(403, f"Missing required scope: {required_scope}")

    return payload


@router.post("/publish", response_model=PublishResponse)
async def publish_process(
    req: PublishRequest,
    payload: dict = Depends(verify_m2m_scope),
    db=Depends(_get_db),
):
    """Publish a Vela process definition as an Aether service."""

    # ── Find or create a VELA_PROXY ServiceDefinition ──
    result = await db.execute(
        select(ServiceDefinition).where(
            ServiceDefinition.plugin_id == "vela_process"
        )
    )
    sd = result.scalar_one_or_none()

    if sd is None:
        sd = ServiceDefinition(
            id=uuid.uuid4(),
            plugin_id="vela_process",
            display_name="Vela Process",
            description="Business process published from Vela",
            version="1.0.0",
            is_builtin=False,
            capabilities=["process_execution", "webhook"],
            config_schema={
                "type": "object",
                "properties": {
                    "vela_process_id": {"type": "string"},
                    "blocks": {"type": "array"},
                    "connections": {"type": "array"},
                    "pages": {"type": "array"},
                },
            },
        )
        db.add(sd)
        await db.flush()

    # ── Check if already published for this vela_process_id ──
    if req.vela_process_id:
        # Search existing instances by checking config JSONB
        result = await db.execute(
            select(ServiceInstance).where(
                ServiceInstance.service_definition_id == sd.id,
                ServiceInstance.config["vela_process_id"].astext == req.vela_process_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.config = {
                "vela_process_id": req.vela_process_id,
                "name": req.name,
                "slug": req.slug,
                "blocks": req.blocks,
                "connections": req.connections,
                "pages": req.pages,
                "updated_at": None,  # filled by onupdate
            }
            await db.commit()
            return PublishResponse(
                service_id=str(existing.id),
                status="updated",
                message=f"Updated existing service {existing.id}",
            )

    # ── Create new ServiceInstance ──
    # For now use a default tenant (in production, tenant comes from Vela org mapping)
    from app.models.tenants import Tenant
    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(400, "No tenants configured in Aether")

    instance = ServiceInstance(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        service_definition_id=sd.id,
        config={
            "vela_process_id": req.vela_process_id,
            "name": req.name,
            "slug": req.slug,
            "blocks": req.blocks,
            "connections": req.connections,
            "pages": req.pages,
        },
        is_active=True,
    )
    db.add(instance)
    await db.commit()

    return PublishResponse(
        service_id=str(instance.id),
        status="published",
        message=f"Service published as {instance.id}",
    )
