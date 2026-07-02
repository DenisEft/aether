"""Conversation and message Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConversationStatus, MessageRole


class ConversationCreate(BaseModel):
    user_id: uuid.UUID | None = None
    channel_id: uuid.UUID
    external_user_id: str | None = None
    subject: str | None = None
    state: dict = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    subject: str | None = None
    state: dict | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    subject: str | None = None
    external_user_id: str | None = None
    user_id: uuid.UUID | None = None
    channel_id: uuid.UUID
    state: dict = Field(default_factory=dict)
    meta_info: dict = Field(default_factory=dict, alias="metadata")
    message_count: int = 0
    last_message_at: datetime | None = None
    created_at: datetime


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    content_type: str = "text"
    intent: str | None = None
    entities: dict | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    content_type: str
    intent: str | None = None
    entities: dict | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    meta_info: dict = Field(default_factory=dict, alias="metadata")
    created_at: datetime


class PaginatedMessagesResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class QuickReplySuggestionsResponse(BaseModel):
    replies: list[str]
