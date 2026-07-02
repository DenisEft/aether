"""Auth endpoints: signup, login, magic link, refresh, API keys."""

from __future__ import annotations

import logging
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.config import settings
from app.core.deps import DBDep, CurrentActiveUser, get_db
from app.core.security import (
    API_KEY_PREFIX,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.models.auth import ApiKey, MagicLink, RefreshToken, Session
from app.models.tenants import Tenant
from app.models.users import User
from app.core.rate_limit import limiter
from app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ── Helper ────────────────────────────────────────────────────


def _make_token_response(user: User, db_session_id: uuid.UUID | None = None) -> TokenResponse:
    """Create access+refresh token pair."""
    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _hash_token(token: str) -> str:
    """SHA-256 hash of the full token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _store_refresh_token(db, user: User, token_response: TokenResponse) -> RefreshToken:
    payload = decode_token(token_response.refresh_token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if payload else None

    rt = RefreshToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash_token(token_response.refresh_token),
        expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
        is_revoked=False,
    )
    db.add(rt)
    await db.flush()
    return rt


# ── POST /auth/signup ─────────────────────────────────────────


@router.post("/auth/signup", response_model=dict, status_code=201)
@limiter.limit("3/hour")
async def signup(request: Request, body: SignupRequest, db: DBDep) -> dict:  # noqa: ARG001
    """Register a new user and tenant."""

    # Create tenant
    tenant = Tenant(slug=body.tenant_slug, name=body.tenant_slug)
    db.add(tenant)
    await db.flush()

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=body.email,
        full_name=body.display_name,
        hashed_password=hash_password(body.password),
        is_active=True,
        is_superadmin=True,  # First user is tenant superuser
    )
    db.add(user)
    await db.flush()

    # Token
    token_data = {"sub": str(user.id), "tenant_id": str(tenant.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token
    payload = decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if payload else None
    rt = RefreshToken(
        tenant_id=tenant.id,
        user_id=user.id,
        token_hash=_hash_token(refresh_token),
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(rt)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_verified": user.mfa_enabled,  # using mfa_enabled as proxy
            "created_at": user.created_at.isoformat(),
        },
    }


# ── POST /auth/login ──────────────────────────────────────────


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: DBDep) -> TokenResponse:  # noqa: ARG001
    """Authenticate with email and password."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    tr = _make_token_response(user)
    await _store_refresh_token(db, user, tr)
    await db.commit()
    return tr


# ── POST /auth/login/magic-link ───────────────────────────────


@router.post("/auth/login/magic-link", status_code=200)
@limiter.limit("3/hour")
async def request_magic_link(request: Request, body: MagicLinkRequest, db: DBDep) -> dict:  # noqa: ARG001
    """Request a magic link (emailed to user). Stub: just logs the link."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None:
        # Don't leak whether user exists
        return {"message": "If the email is registered, a magic link has been sent."}

    import secrets
    token = secrets.token_urlsafe(32)
    ml = MagicLink(
        tenant_id=user.tenant_id,
        email=body.email,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        is_used=False,
    )
    db.add(ml)
    await db.commit()

    magic_url = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
    logger.info(f"Magic link for {body.email}: {magic_url}")

    return {"message": "If the email is registered, a magic link has been sent."}


# ── POST /auth/login/magic-link/verify ───────────────────────


@router.post("/auth/login/magic-link/verify", response_model=TokenResponse)
@limiter.limit("5/minute")
async def verify_magic_link(request: Request, body: MagicLinkVerifyRequest, db: DBDep) -> TokenResponse:  # noqa: ARG001
    """Verify a magic link token and return JWT pair."""
    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token_hash == hashlib.sha256(body.token.encode()).hexdigest(),
            MagicLink.is_used == False,
            MagicLink.expires_at > datetime.now(timezone.utc),
        )
    )
    ml = result.scalar_one_or_none()
    if ml is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    ml.is_used = True

    result = await db.execute(select(User).where(User.email == ml.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.is_verified = True
    user.last_login_at = datetime.now(timezone.utc)
    tr = _make_token_response(user)
    await _store_refresh_token(db, user, tr)
    await db.commit()
    return tr


# ── POST /auth/refresh ────────────────────────────────────────


@router.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, body: RefreshRequest, db: DBDep) -> TokenResponse:  # noqa: ARG001
    """Exchange a refresh token for a new token pair."""
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Revoke old refresh token — must exist and not be revoked
    token_hash = _hash_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
        )
    )
    old_rt = result.scalar_one_or_none()
    if old_rt is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or is invalid",
        )
    old_rt.is_revoked = True

    tr = _make_token_response(user)
    await _store_refresh_token(db, user, tr)
    await db.commit()
    return tr


# ── POST /auth/logout ─────────────────────────────────────────


@router.post("/auth/logout", status_code=200)
async def logout(
    body: RefreshRequest | None = None,
    db: DBDep = None,
    current_user: CurrentActiveUser = None,
) -> dict:
    """Revoke the provided refresh token."""
    if body and body.refresh_token:
        token_hash = _hash_token(body.refresh_token)
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == current_user.id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
            )
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.is_revoked = True
            await db.commit()

    return {"message": "Logged out"}


# ── GET /users/me ─────────────────────────────────────────────


@router.get("/users/me", response_model=UserResponse)
async def get_me(current_user: CurrentActiveUser) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── POST /users/me/api-keys ────────────────────────────────────


@router.post("/users/me/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreateRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> ApiKeyCreateResponse:
    """Create a new API key. The secret is returned only once."""
    prefix, full_key = generate_api_key()
    key_hash = hash_api_key(full_key)

    ak = ApiKey(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        expires_at=body.expires_at,
    )
    db.add(ak)
    await db.commit()
    await db.refresh(ak)

    resp = ApiKeyResponse(
        id=ak.id,
        name=ak.name,
        prefix=ak.key_prefix,
        created_at=ak.created_at,
        last_used_at=ak.last_used_at,
        expires_at=ak.expires_at,
    )
    return ApiKeyCreateResponse(api_key=resp, secret=full_key)


# ── GET /users/me/api-keys ────────────────────────────────────


@router.get("/users/me/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(db: DBDep, current_user: CurrentActiveUser) -> list[ApiKeyResponse]:
    """List all API keys for the current user."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            ApiKey.is_revoked == False,
        ).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            prefix=k.key_prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


# ── DELETE /users/me/api-keys/{key_id} ────────────────────────


@router.delete("/users/me/api-keys/{key_id}", status_code=200)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Revoke an API key."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    ak = result.scalar_one_or_none()
    if ak is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    ak.is_revoked = True
    await db.commit()
    return {"message": "API key revoked"}


# ── PUT /users/me ─────────────────────────────────────────────


class UpdateMeBody(BaseModel):
    """Editable profile fields."""
    full_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None


@router.put("/users/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeBody,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> UserResponse:
    """Update current user's profile."""
    if body.full_name is not None:
        current_user.display_name = body.full_name
    if body.email is not None:
        current_user.email = body.email
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ── POST /users/me/avatar ─────────────────────────────────────


@router.post("/users/me/avatar")
async def upload_avatar(
    file: UploadFile,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Upload avatar image. Returns the public URL."""
    import os
    from pathlib import Path

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, WebP allowed")

    # Save file
    avatars_dir = Path("static/avatars")
    avatars_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "avatar.jpg")[1] or ".jpg"
    filename = f"{current_user.id}{ext}"
    filepath = avatars_dir / filename

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="Avatar must be under 5MB")

    filepath.write_bytes(content)

    url = f"/static/avatars/{filename}"
    current_user.avatar_url = url
    await db.commit()

    return {"avatar_url": url}


# ── DELETE /users/me ──────────────────────────────────────────


@router.delete("/users/me")
async def delete_me(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Soft-delete current user's account."""
    # Revoke all refresh tokens
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
        )
    )
    for rt in result.scalars().all():
        rt.is_revoked = True

    # Revoke all API keys
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            ApiKey.is_revoked == False,
        )
    )
    for ak in result.scalars().all():
        ak.is_revoked = True

    # Soft-delete user
    current_user.is_deleted = True
    current_user.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Account deleted"}
