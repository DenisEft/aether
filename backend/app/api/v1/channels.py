"""Channel management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DBDep, CurrentActiveUser
from app.models.channels import Channel
from app.schemas.channels import (
    ChannelCreate,
    ChannelResponse,
    ChannelTestResponse,
    ChannelUpdate,
)

router = APIRouter(tags=["channels"])


# ── GET /channels ────────────────────────────────────────────


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(db: DBDep, current_user: CurrentActiveUser) -> list[ChannelResponse]:
    """List all channels in the current tenant."""
    result = await db.execute(
        select(Channel)
        .where(Channel.tenant_id == current_user.tenant_id)
        .order_by(Channel.priority.desc(), Channel.created_at.desc())
    )
    channels = result.scalars().all()
    return [ChannelResponse.model_validate(c) for c in channels]


# ── POST /channels ────────────────────────────────────────────


@router.post("/channels", response_model=ChannelResponse, status_code=201)
async def create_channel(
    body: ChannelCreate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ChannelResponse:
    """Create a new channel."""
    channel = Channel(
        tenant_id=current_user.tenant_id,
        display_name=body.display_name,
        channel_type=body.channel_type.value if hasattr(body.channel_type, "value") else body.channel_type,
        config=body.config,
        priority=body.priority,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return ChannelResponse.model_validate(channel)


# ── GET /channels/{channel_id} ───────────────────────────────


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ChannelResponse:
    """Get channel details."""
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.tenant_id == current_user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ChannelResponse.model_validate(channel)


# ── PATCH /channels/{channel_id} ─────────────────────────────


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    body: ChannelUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ChannelResponse:
    """Update a channel."""
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.tenant_id == current_user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    if body.display_name is not None:
        channel.display_name = body.display_name
    if body.is_active is not None:
        channel.is_active = body.is_active
    if body.config is not None:
        channel.config = body.config
    if body.priority is not None:
        channel.priority = body.priority

    await db.commit()
    await db.refresh(channel)
    return ChannelResponse.model_validate(channel)


# ── DELETE /channels/{channel_id} ────────────────────────────


@router.delete("/channels/{channel_id}", status_code=200)
async def delete_channel(
    channel_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Delete a channel."""
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.tenant_id == current_user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    await db.delete(channel)
    await db.commit()
    return {"message": "Channel deleted"}


# ── POST /channels/{channel_id}/test ──────────────────────────


@router.post("/channels/{channel_id}/test", response_model=ChannelTestResponse)
async def test_channel(
    channel_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ChannelTestResponse:
    """Test channel connectivity. Stub: always returns success."""
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.tenant_id == current_user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    return ChannelTestResponse(success=True, latency_ms=1.0)


# === Channel Lifecycle (WebSocket/Polling) ===

from pydantic import BaseModel
from app.channels.router import channel_router
from app.channels.base import ChannelConfig


class ChannelStartRequest(BaseModel):
    channel_type: str
    channel_id: str
    display_name: str = ""
    config: dict = {}


@router.post("/{channel_id}/start")
async def start_channel(
    channel_id: str,
    payload: ChannelStartRequest,
    current_user: CurrentActiveUser,
    db: DBDep,
):
    """Start a channel (connect, begin polling/webhook)."""
    # Verify channel belongs to user's tenant
    result = await db.execute(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.tenant_id == current_user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    config = ChannelConfig(
        id=str(channel.id),
        channel_type=channel.channel_type.value,
        tenant_id=str(channel.tenant_id),
        display_name=channel.display_name,
        config=payload.config,
    )

    ch = await channel_router.start_channel(config)
    return {
        "id": channel_id,
        "status": ch.status.value,
        "channel_type": ch.config.channel_type,
    }


@router.post("/{channel_id}/stop")
async def stop_channel(
    channel_id: str,
    current_user: CurrentActiveUser,
):
    """Stop a channel."""
    key = f"{current_user.tenant_id}:{channel_id}"
    await channel_router.stop_channel(key)
    return {"status": "stopped"}


@router.get("/status")
async def channels_status(current_user: CurrentActiveUser):
    """Get runtime status of all active channels."""
    return channel_router.get_status()
