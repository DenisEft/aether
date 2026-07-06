"""M2M (machine-to-machine) authentication utilities for Aether."""

from datetime import UTC, datetime, timedelta
import secrets

from fastapi import HTTPException, status
from jose import JWTError, jwt
from redis.asyncio import Redis

from app.config import settings

# M2M token claims
M2M_TOKEN_TYPE = "m2m"
M2M_DEFAULT_EXPIRE_MINUTES = 5
M2M_DEFAULT_SCOPES = ["deploy:write", "deploy:read", "deploy:delete", "processbot:generate"]


async def generate_m2m_token(
    scopes: list[str] | None = None,
    expires_in_minutes: int = M2M_DEFAULT_EXPIRE_MINUTES,
) -> str:
    """Generate an M2M token with specified scopes."""
    if scopes is None:
        scopes = M2M_DEFAULT_SCOPES

    # Generate a unique JTI (JWT ID) for anti-replay
    jti = secrets.token_urlsafe(32)

    # Create token payload
    payload = {
        "sub": "m2m_client",
        "type": M2M_TOKEN_TYPE,
        "scopes": scopes,
        "jti": jti,
        "exp": datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
    }

    # Encode token with M2M secret
    return jwt.encode(payload, settings.M2M_SECRET, algorithm=settings.JWT_ALGORITHM)


async def verify_m2m_token(token: str) -> dict:
    """Verify an M2M token and check for replay attacks."""
    try:
        # Decode the token
        payload = jwt.decode(token, settings.M2M_SECRET, algorithms=[settings.JWT_ALGORITHM])

        # Check if token type is correct
        if payload.get("type") != M2M_TOKEN_TYPE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check scopes
        scopes = payload.get("scopes", [])
        if not scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No scopes provided in token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check for replay attacks using JTI
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        jti = payload.get("jti")
        if await redis_client.exists(f"m2m_jti:{jti}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has already been used",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Store JTI for anti-replay
        await redis_client.setex(f"m2m_jti:{jti}", M2M_DEFAULT_EXPIRE_MINUTES * 60, "used")

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def verify_m2m_token_middleware(token: str) -> dict:
    """FastAPI middleware to verify M2M tokens."""
    return await verify_m2m_token(token)
