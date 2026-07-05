"""FastAPI dependencies: DB session, current user extraction."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.core.security import decode_token
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
    Returns None for M2M service tokens.
    """
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("type") == "m2m":
        return None  # M2M token — no user object

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(current_user: CurrentUser) -> User | None:
    """Reject inactive or deleted users.
    Returns None for M2M tokens — services handle this case.
    """
    if current_user is None:
        return None  # M2M service token — no user object
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    if getattr(current_user, "is_deleted", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account has been deleted")
    return current_user


CurrentActiveUser = Annotated[User | None, Depends(get_current_active_user)]


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_superuser(current_user: CurrentActiveUser) -> User:
    """Reject non-superuser users."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]


async def get_current_service(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
) -> dict:
    """Extract M2M service token. Returns payload with scopes, or raises 401."""
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    sub: str | None = payload.get("sub")
    if sub is None or not sub.startswith("service:"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Service token required")

    return {
        "service": sub.replace("service:", ""),
        "scopes": payload.get("scopes", []),
        "token_type": payload.get("type", "m2m"),
        "tenant_id": payload.get("tenant_id"),
    }


CurrentService = Annotated[dict, Depends(get_current_service)]
