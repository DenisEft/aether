"""User management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentActiveUser, CurrentSuperuser, DBDep
from app.models.users import User
from app.schemas.common import PaginationParams
from app.schemas.users import UserListResponse, UserProfileUpdate, UserResponse

router = APIRouter(tags=["users"])


# ── GET /users ────────────────────────────────────────────────


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: DBDep,
    current_user: CurrentSuperuser,
    pagination: PaginationParams = PaginationParams(),
) -> UserListResponse:
    """List all users in the current tenant (superuser only)."""
    where = User.tenant_id == current_user.tenant_id

    total = await db.execute(select(func.count()).select_from(User).where(where))
    total_count = total.scalar() or 0

    result = await db.execute(
        select(User)
        .where(where)
        .order_by(User.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total_count,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ── GET /users/{user_id} ──────────────────────────────────────


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> UserResponse:
    """Get a user's profile."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


# ── PATCH /users/{user_id} ────────────────────────────────────


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserProfileUpdate,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> UserResponse:
    """Update a user's profile. Users can only update themselves unless superuser."""
    if current_user.id != user_id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update another user's profile"
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.display_name is not None:
        user.full_name = body.display_name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    if body.settings is not None:
        user.settings = body.settings

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ── DELETE /users/{user_id} ───────────────────────────────────


@router.delete("/users/{user_id}", status_code=200)
async def deactivate_user(
    user_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentSuperuser,
) -> dict:
    """Deactivate a user (soft delete, superuser only)."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.commit()
    return {"message": "User deactivated"}
