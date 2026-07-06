"""Pydantic schemas for organisations, memberships, and invites."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

# ── Organisation ──────────────────────────────────────────────


class OrganisationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = None


class OrganisationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    logo_url: str | None = None


class OrganisationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    member_count: int = 0
    created_at: datetime


# ── Membership ────────────────────────────────────────────────


class OrganisationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str | None
    email: str
    role: str
    role_id: uuid.UUID | None
    invited_at: datetime | None
    accepted_at: datetime | None


# ── Invites ───────────────────────────────────────────────────


class InviteCreateRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    role: str | None = None


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str | None
    status: str = "pending"
    created_at: datetime


# ── Role change ──────────────────────────────────────────────


class ChangeRoleRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)
