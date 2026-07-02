"""OAuth endpoints: social login via Google, Yandex ID, VK ID."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.core.deps import DBDep
from app.core.security import create_access_token, create_refresh_token
from app.models.auth import OAuthState
from app.models.tenants import Tenant
from app.models.users import User
from app.services.oauth_service import get_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])

SUPPORTED_PROVIDERS = {"google", "yandex", "vk"}


@router.get("/auth/oauth/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    db: DBDep,
) -> RedirectResponse:
    """Redirect user to the OAuth provider's authorization page."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
        )

    oauth = get_oauth_service()
    redirect_uri = f"{settings.FRONTEND_URL}/auth/oauth/{provider}/callback"
    auth_url = await oauth.get_authorization_url(provider, redirect_uri)

    # Extract state from the generated URL for CSRF validation
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(auth_url)
    query_params = parse_qs(parsed.query)
    state = query_params.get("state", [""])[0]

    # Store OAuth state for CSRF protection (15 min TTL)
    oauth_state = OAuthState(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # No tenant yet
        user_id=None,
        state=state,
        provider=provider,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(oauth_state)
    await db.commit()
    logger.info(f"OAuth login initiated: provider={provider}, state={state[:8]}...")

    return RedirectResponse(url=auth_url)


@router.get("/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    db: DBDep,
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Handle OAuth callback: exchange code, find/create user, issue tokens."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}",
        )

    # Validate CSRF state
    result = await db.execute(
        select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.provider == provider,
            OAuthState.expires_at > datetime.now(UTC),
        )
    )
    oauth_state = result.scalar_one_or_none()
    if oauth_state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please try again.",
        )

    # Mark state as used
    oauth_state.expires_at = datetime.now(UTC)
    await db.commit()

    # Exchange code for tokens
    oauth = get_oauth_service()
    redirect_uri = f"{settings.FRONTEND_URL}/auth/oauth/{provider}/callback"

    try:
        user_info = await oauth.exchange_code(provider, code, redirect_uri)
    except Exception as e:
        logger.error(f"OAuth token exchange failed for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {e}",
        )

    email = user_info.get("email")
    name = user_info.get("name") or email or ""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve email from OAuth provider. Please ensure email scope is granted.",
        )

    # Find existing user or create new one
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user is None:
        # Create new user with a default tenant
        tenant_slug = email.split("@")[0].lower().replace(".", "-")
        tenant = Tenant(slug=tenant_slug, name=name or tenant_slug)
        db.add(tenant)
        await db.flush()

        new_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            display_name=name or email,
            hashed_password="",  # OAuth users have no password
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"Created new OAuth user: {email} via {provider}")
        user: User = new_user
    else:
        user = existing_user
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )

    # Generate JWT tokens
    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token
    from app.api.v1.auth import _store_refresh_token
    from app.schemas.auth import TokenResponse

    tr = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    await _store_refresh_token(db, user, tr)
    await db.commit()

    # Redirect to frontend with tokens
    frontend_callback = (
        f"{settings.FRONTEND_URL}/auth/callback"
        f"?access_token={access_token}"
        f"&refresh_token={refresh_token}"
    )
    logger.info(f"OAuth login successful: {email} via {provider}")
    return RedirectResponse(url=frontend_callback)
