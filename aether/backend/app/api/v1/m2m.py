"""M2M (machine-to-machine) authentication endpoints for Aether."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.core.deps import DBDep
from app.core.m2m import generate_m2m_token, verify_m2m_token_middleware

router = APIRouter(tags=["m2m"])


class M2MTokenRequest(BaseModel):
    """Request body for M2M token generation."""

    secret: str
    scopes: list[str] = []


class M2MTokenResponse(BaseModel):
    """Response body for M2M token."""

    token: str


@router.post("/auth/m2m/token", response_model=M2MTokenResponse)
async def generate_m2m_token_endpoint(request: M2MTokenRequest, db: DBDep) -> M2MTokenResponse:
    """Generate an M2M token for machine-to-machine authentication."""
    # Verify secret
    if request.secret != settings.M2M_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid M2M secret")

    # Generate token with provided scopes
    token = await generate_m2m_token(request.scopes)

    return M2MTokenResponse(token=token)


@router.get("/auth/m2m/verify")
async def verify_m2m_token_endpoint(token: str, db: DBDep) -> dict:
    """Verify an M2M token."""
    try:
        payload = await verify_m2m_token_middleware(token)
        return {"valid": True, "payload": payload}
    except HTTPException as e:
        if e.status_code == 401:
            return {"valid": False, "error": "Invalid token"}
        raise
