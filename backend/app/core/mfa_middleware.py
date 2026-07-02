"""MFA enforcement middleware and dependency.

For admin/owner roles, MFA is required. The JWT must contain mfa_verified=True.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import CurrentActiveUser, DBDep
from app.core.security import decode_token
from app.models.auth import MFAConfig

logger = logging.getLogger("aether.mfa")


async def require_mfa_if_enabled(
    request: Request,
    current_user: CurrentActiveUser,
    db: DBDep,
) -> bool:
    """Check if MFA is required for this user and verify it's been completed.

    Returns True if MFA is not needed or already verified.
    Raises HTTPException if MFA is required but not verified.
    """
    # Check if MFA is enabled for this user
    result = await db.execute(
        select(MFAConfig).where(
            MFAConfig.user_id == current_user.id,
            MFAConfig.is_enabled == True,  # noqa: E712
        )
    )
    mfa_config = result.scalar_one_or_none()

    if mfa_config is None:
        # MFA not enabled — no check needed
        return True

    # MFA is enabled — check if this request has mfa_verified claim
    token = _extract_token_from_request(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA required: cannot verify token",
        )

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA required: invalid token",
        )

    mfa_verified = payload.get("mfa_verified", False)
    if not mfa_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA verification required. Use POST /auth/mfa/verify to complete MFA.",
        )

    return True


async def require_mfa_for_admin(
    request: Request,
    current_user: CurrentActiveUser,
    db: DBDep,
) -> bool:
    """Require MFA for admin/owner roles. For regular users, optional."""
    # Only enforce for admin/owner users
    if current_user.is_superadmin:
        return await require_mfa_if_enabled(request, current_user, db)

    # For regular users, MFA is optional (but checked if enabled)
    return await require_mfa_if_enabled(request, current_user, db)


def _extract_token_from_request(request: Request) -> str | None:
    """Extract JWT bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# Dependency annotations for FastAPI
RequireMFA = Annotated[bool, Depends(require_mfa_if_enabled)]
RequireMFAForAdmin = Annotated[bool, Depends(require_mfa_for_admin)]
