"""User-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=128)
    avatar_url: str | None = None
    settings: dict | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str = ""
    avatar_url: str | None = None
    is_verified: bool = False
    is_superadmin: bool = False
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
