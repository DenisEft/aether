"""M2M (machine-to-machine) authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.core.security import create_access_token

router = APIRouter(tags=["auth"])


class M2MTokenRequest(BaseModel):
    """Request model for M2M token generation."""
    secret: str
    scopes: List[str]


class M2MTokenResponse(BaseModel):
    """Response model for M2M token generation."""
    access_token: str
    token_type: str
    expires_in: int


@router.post("/m2m/token", response_model=M2MTokenResponse)
async def generate_m2m_token(request: M2MTokenRequest):
    """Generate a JWT token for machine-to-machine authentication."""
    # Validate the secret
    if request.secret != settings.AETHER_M2M_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create token payload
    token_data = {
        "sub": "service:vela",
        "scopes": request.scopes,
        "type": "m2m",
    }

    # Set expiration time
    expire_minutes = settings.AETHER_M2M_TOKEN_EXPIRE_MINUTES
    expires_delta = timedelta(minutes=expire_minutes)

    # Generate access token
    access_token = create_access_token(token_data, expires_delta)

    return M2MTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )
