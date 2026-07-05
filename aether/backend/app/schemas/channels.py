"""Channel-related Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChannelTypeEnum


class ChannelCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    channel_type: ChannelTypeEnum
    config: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)


class ChannelUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None
    config: dict | None = None
    priority: int | None = Field(None, ge=0)


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    channel_type: str
    display_name: str
    is_active: bool
    priority: int
    config: dict
    created_at: datetime


class ChannelTestResponse(BaseModel):
    success: bool
    latency_ms: float | None = None
    error: str | None = None
