"""FastAPI dependencies: DB session, current user extraction."""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import async_session_factory
from app.models.users import User

security_scheme = HTTPBearer(auto_error=True)


async def get_db() -> AsyncSession:
    """Yield an async database session."""
    async with async_session_factory() as session:
        yield session


DBDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    db: DBDep,
) -> User | None:
    """Extract and validate JWT bearer token, return the authenticated user.
    Returns None for M2M and service tokens.
    """
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    # M2M tokens (new format with type field)
    if payload.get("type") == "m2m":
        return None

    # Service tokens (Vela etc) — sub starts with "service:"
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject"
        )
    if user_id.startswith("service:"):
        return None

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User | None, Depends(get_current_user)]


async def get_current_active_user(current_user: CurrentUser) -> User | None:
    """Reject inactive or deleted users.
    Returns None for M2M/service tokens.
    """
    if current_user is None:
        return None
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    if getattr(current_user, "is_deleted", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account has been deleted"
        )
    return current_user


CurrentActiveUser = Annotated[User | None, Depends(get_current_active_user)]


async def get_current_superuser(current_user: CurrentActiveUser) -> User:
    """Reject non-superuser users."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
