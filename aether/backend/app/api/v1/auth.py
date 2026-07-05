"""Auth endpoints: signup, login, magic link, refresh, API keys, passkeys, MFA."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url

# M2M imports
from app.config import settings
from app.core.deps import CurrentActiveUser, DBDep
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    generate_backup_codes,
    generate_mfa_secret,
    hash_api_key,
    hash_password,
    validate_password_strength,
    verify_mfa_code,
    verify_password,
)
from app.models.auth import (
    ApiKey,
    Invite,
    MagicLink,
    MFAConfig,
    Passkey,
    RefreshToken,
    Session,
)
from app.models.tenants import Tenant
from app.models.users import User
from app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ChangePasswordRequest,
    InviteRequest,
    LoginRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    MFADisableRequest,
    MFATokenResponse,
    PasskeyAuthenticationBeginRequest,
    PasskeyAuthenticationBeginResponse,
    PasskeyAuthenticationCompleteRequest,
    PasskeyRegistrationBeginRequest,
    PasskeyRegistrationBeginResponse,
    PasskeyRegistrationCompleteRequest,
    RefreshRequest,
    SessionResponse,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.tenant_provisioning import TenantProvisioningService

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


def _make_mfa_token_response(user: User) -> MFATokenResponse:
    """Create access+refresh token pair with MFA verified."""
    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id), "mfa_verified": True}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    return MFATokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


def _hash_token(token: str) -> str:
    """SHA-256 hash of the full token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _store_refresh_token(db, user: User, token_response: TokenResponse) -> RefreshToken:
    payload = decode_token(token_response.refresh_token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC) if payload else None

    rt = RefreshToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash_token(token_response.refresh_token),
        expires_at=expires_at
        or (datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
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

    # Provision the tenant
    provisioning_service = TenantProvisioningService(db)
    try:
        provision_result = await provisioning_service.provision_tenant(tenant.id)
    except Exception as e:
        logger.error(f"Failed to provision tenant {tenant.id}: {e}")
        # We could rollback here if needed, but tenant already exists
        # For now, we'll proceed with the signup
        pass

    # Token
    token_data = {"sub": str(user.id), "tenant_id": str(tenant.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store refresh token
    payload = decode_token(refresh_token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC) if payload else None
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Check if MFA is enabled
    mfa_result = await db.execute(select(MFAConfig).where(MFAConfig.user_id == user.id))
    mfa_config = mfa_result.scalar_one_or_none()

    if mfa_config and mfa_config.is_enabled:
        # MFA is enabled, check code if provided
        if body.mfa_code:
            if not verify_mfa_code(mfa_config.secret_encrypted, body.mfa_code):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
                )
        else:
            # MFA required but not provided
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA code required"
            )

    user.last_login_at = datetime.now(UTC)
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
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
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
async def verify_magic_link(
    request: Request, body: MagicLinkVerifyRequest, db: DBDep
) -> TokenResponse:  # noqa: ARG001
    """Verify a magic link token and return JWT pair."""
    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token_hash == hashlib.sha256(body.token.encode()).hexdigest(),
            MagicLink.is_used == False,
            MagicLink.expires_at > datetime.now(UTC),
        )
    )
    ml = result.scalar_one_or_none()
    if ml is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    ml.is_used = True

    result = await db.execute(select(User).where(User.email == ml.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    user.is_verified = True
    user.last_login_at = datetime.now(UTC)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

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


# ── POST /auth/passkey/register/begin ───────────────────────────────


@router.post("/auth/passkey/register/begin", response_model=PasskeyRegistrationBeginResponse)
@limiter.limit("5/minute")
async def passkey_register_begin(
    request: Request, body: PasskeyRegistrationBeginRequest, db: DBDep
) -> PasskeyRegistrationBeginResponse:  # noqa: ARG001
    """Begin passkey registration process."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Create registration options
    registration_options = generate_registration_options(
        rp_id="aether.local",  # Should be configurable via settings
        rp_name="Aether",
        user_id=str(user.id),
        user_name=user.email,
        user_display_name=user.full_name or user.email,
        attestation="none",
        authenticator_attachment=None,
        require_resident_key=True,
        user_verification="preferred",
    )

    # Convert to dict for response
    options_dict = {
        "challenge": bytes_to_base64url(registration_options.challenge),
        "public_key": {
            "rp": registration_options.rp,
            "user": registration_options.user,
            "challenge": bytes_to_base64url(registration_options.challenge),
            "pubKeyCredParams": registration_options.pub_key_cred_params,
            "timeout": registration_options.timeout,
            "excludeCredentials": registration_options.exclude_credentials,
            "authenticatorSelection": registration_options.authenticator_selection,
            "attestation": registration_options.attestation,
        },
    }

    return PasskeyRegistrationBeginResponse(
        challenge=options_dict["challenge"], public_key=options_dict["public_key"]
    )


# ── POST /auth/passkey/register/complete ───────────────────────────────


@router.post("/auth/passkey/register/complete", status_code=200)
@limiter.limit("5/minute")
async def passkey_register_complete(
    request: Request, body: PasskeyRegistrationCompleteRequest, db: DBDep
) -> dict:  # noqa: ARG001
    """Complete passkey registration process."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify registration response
    try:
        registration_result = verify_registration_response(
            response=body.response,
            expected_challenge=bytes_to_base64url(body.response.get("challenge", "")),
            expected_rp_id="aether.local",  # Should be configurable via settings
            expected_origin=settings.FRONTEND_URL,
            require_user_verification=True,
        )
    except Exception as e:
        logger.error(f"Passkey registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey registration failed"
        )

    # Store the passkey credential
    passkey = Passkey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        credential_id=registration_result.credential_id.decode("utf-8"),
        public_key=registration_result.public_key,
        sign_count=registration_result.sign_count,
        name=body.response.get("name", "Passkey"),
        device_type=body.response.get("device_type", "unknown"),
    )
    db.add(passkey)
    await db.commit()

    return {"message": "Passkey registered successfully"}


# ── POST /auth/passkey/login/begin ───────────────────────────────


@router.post("/auth/passkey/login/begin", response_model=PasskeyAuthenticationBeginResponse)
@limiter.limit("5/minute")
async def passkey_login_begin(
    request: Request, body: PasskeyAuthenticationBeginRequest, db: DBDep
) -> PasskeyAuthenticationBeginResponse:  # noqa: ARG001
    """Begin passkey authentication process."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get stored passkeys for the user
    result = await db.execute(select(Passkey).where(Passkey.user_id == user.id))
    passkeys = result.scalars().all()

    if not passkeys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No passkeys found for user"
        )

    # Create authentication options
    allow_credentials = [{"type": "public-key", "id": pk.credential_id} for pk in passkeys]

    authentication_options = generate_authentication_options(
        rp_id="aether.local",  # Should be configurable via settings
        allow_credentials=allow_credentials,
        user_verification="preferred",
        timeout=30000,
    )

    # Convert to dict for response
    options_dict = {
        "challenge": bytes_to_base64url(authentication_options.challenge),
        "public_key": {
            "challenge": bytes_to_base64url(authentication_options.challenge),
            "timeout": authentication_options.timeout,
            "allowCredentials": authentication_options.allow_credentials,
            "userVerification": authentication_options.user_verification,
        },
    }

    return PasskeyAuthenticationBeginResponse(
        challenge=options_dict["challenge"], public_key=options_dict["public_key"]
    )


# ── POST /auth/passkey/login/complete ───────────────────────────────


@router.post("/auth/passkey/login/complete", response_model=TokenResponse)
@limiter.limit("5/minute")
async def passkey_login_complete(
    request: Request, body: PasskeyAuthenticationCompleteRequest, db: DBDep
) -> TokenResponse:  # noqa: ARG001
    """Complete passkey authentication process."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get stored passkey for the user
    result = await db.execute(select(Passkey).where(Passkey.user_id == user.id))
    passkeys = result.scalars().all()

    if not passkeys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No passkeys found for user"
        )

    # Find the passkey by credential ID from response
    credential_id = body.response.get("id")
    passkey = next((pk for pk in passkeys if pk.credential_id == credential_id), None)
    if not passkey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey not found")

    # Verify authentication response
    try:
        authentication_result = verify_authentication_response(
            response=body.response,
            expected_challenge=bytes_to_base64url(body.response.get("challenge", "")),
            expected_rp_id="aether.local",  # Should be configurable via settings
            expected_origin=settings.FRONTEND_URL,
            public_key=passkey.public_key,
            sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        logger.error(f"Passkey authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey authentication failed"
        )

    # Update sign count
    passkey.sign_count = authentication_result.sign_count
    await db.commit()

    # Generate tokens
    tr = _make_token_response(user)
    await _store_refresh_token(db, user, tr)
    await db.commit()
    return tr


# ── OAuth endpoints moved to app/api/v1/oauth.py ─────────────────


# ── POST /auth/mfa/setup ───────────────────────────────


@router.post("/auth/mfa/setup", response_model=dict)
@limiter.limit("3/minute")
async def mfa_setup(
    request: Request,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Setup MFA for the current user."""
    # Generate a new secret
    secret = generate_mfa_secret()

    # Create backup codes
    backup_codes = generate_backup_codes()

    # Store MFA configuration
    mfa_config = MFAConfig(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        secret_encrypted=secret,
        is_enabled=False,
        backup_codes=backup_codes,
    )
    db.add(mfa_config)
    await db.commit()

    # Return the secret and backup codes
    return {"secret": secret, "backup_codes": backup_codes}


# ── POST /auth/mfa/verify ───────────────────────────────


@router.post("/auth/mfa/verify", response_model=MFATokenResponse)
@limiter.limit("3/minute")
async def mfa_verify(
    request: Request,
    body: MFADisableRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> MFATokenResponse:
    """Verify MFA code and enable MFA for the user."""
    # Get MFA config
    result = await db.execute(select(MFAConfig).where(MFAConfig.user_id == current_user.id))
    mfa_config = result.scalar_one_or_none()

    if not mfa_config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not setup")

    # Verify the code
    if not verify_mfa_code(mfa_config.secret_encrypted, body.mfa_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    # Enable MFA
    mfa_config.is_enabled = True
    await db.commit()

    # Generate tokens with MFA verified
    return _make_mfa_token_response(current_user)


# ── POST /auth/mfa/disable ───────────────────────────────


@router.post("/auth/mfa/disable", response_model=dict)
@limiter.limit("3/minute")
async def mfa_disable(
    request: Request,
    body: MFADisableRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Disable MFA for the user."""
    # Get MFA config
    result = await db.execute(select(MFAConfig).where(MFAConfig.user_id == current_user.id))
    mfa_config = result.scalar_one_or_none()

    if not mfa_config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not setup")

    # Verify the code
    if not verify_mfa_code(mfa_config.secret_encrypted, body.mfa_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    # Disable MFA
    mfa_config.is_enabled = False
    await db.commit()

    return {"message": "MFA disabled successfully"}


# ── GET /auth/sessions ──────────────────────────────────────


@router.get("/auth/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> list[SessionResponse]:
    """List active sessions for the current user."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(Session)
        .where(
            Session.user_id == current_user.id,
            Session.expires_at > now,
        )
        .order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()
    return [SessionResponse.model_validate(s) for s in sessions]


# ── POST /auth/logout/all ──────────────────────────────────


@router.post("/auth/logout/all", status_code=200)
async def logout_all(
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Log out from all devices — revoke all refresh tokens."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
        )  # noqa: E712
    )
    tokens = result.scalars().all()
    count = 0
    for rt in tokens:
        rt.is_revoked = True
        count += 1
    await db.commit()
    return {"message": "Logged out from all devices", "sessions_revoked": count}


# ── POST /users/me/change-password ──────────────────────────


@router.post("/users/me/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    db: DBDep,
    current_user: CurrentActiveUser,
) -> dict:
    """Change password for the current user."""
    # Verify old password
    if not verify_password(body.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Validate new password strength
    if not validate_password_strength(body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 12+ characters with uppercase, lowercase, digit, and special character",
        )

    # Hash and save new password
    current_user.hashed_password = hash_password(body.new_password)

    # Revoke all existing refresh tokens (security best practice)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
        )  # noqa: E712
    )
    for rt in result.scalars().all():
        rt.is_revoked = True

    await db.commit()
    return {"message": "Password changed"}


# ── POST /auth/invite/accept ────────────────────────────────


@router.post("/auth/invite/accept", status_code=200)
async def accept_invite(
    body: InviteRequest,
    db: DBDep,
) -> dict:
    """Accept an invitation and create or link user account."""
    token_hash = _hash_token(body.token)

    # Find valid invite
    result = await db.execute(
        select(Invite).where(
            Invite.token_hash == token_hash,
            Invite.is_used == False,  # noqa: E712
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation",
        )

    # Find or create user by email
    result = await db.execute(select(User).where(User.email == invite.email))
    user = result.scalar_one_or_none()

    if user is None:
        # Create user without password (they'll set it later or use magic link)
        import uuid as _uuid

        user = User(
            id=_uuid.uuid4(),
            tenant_id=invite.tenant_id,
            email=invite.email,
            display_name=invite.email.split("@")[0],
            hashed_password="",
            is_active=True,
        )
        db.add(user)
        logger.info(f"Created user from invite: {invite.email}")

    # Mark invite as used
    invite.is_used = True

    # Generate tokens
    tr = _make_token_response(user)
    await _store_refresh_token(db, user, tr)
    await db.commit()

    return {
        "access_token": tr.access_token,
        "refresh_token": tr.refresh_token,
        "token_type": tr.token_type,
        "message": "Invitation accepted",
    }


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
        select(ApiKey)
        .where(
            ApiKey.user_id == current_user.id,
            ApiKey.is_revoked == False,
        )
        .order_by(ApiKey.created_at.desc())
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
    password: str | None = Field(
        None,
        min_length=12,
        description="New password (12+ chars, uppercase, lowercase, digit, special)",
    )


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
    if body.password is not None:
        if not validate_password_strength(body.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be 12+ characters with uppercase, lowercase, digit, and special character",
            )
        current_user.hashed_password = hash_password(body.password)
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
    current_user.deleted_at = datetime.now(UTC)
    await db.commit()

    return {"message": "Account deleted"}
