"""Authentication schemas: signup, login, tokens, API keys, passkeys, MFA."""

from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field

# ── Request schemas ───────────────────────────────────────────


class SignupRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=8)
    tenant_slug: str = Field(..., description="Tenant slug (e.g. 'acme')")
    display_name: str = Field(..., min_length=1, max_length=128, examples=["Alice"])


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(...)
    mfa_code: str | None = Field(None)
    remember_me: bool | None = Field(False)


class MagicLinkRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])


class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(...)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(...)


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, examples=["CI/CD pipeline"])
    expires_at: datetime | None = Field(None, description="Optional expiry (ISO-8601)")


class PasskeyRegistrationBeginRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])


class PasskeyRegistrationCompleteRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    response: dict = Field(...)


class PasskeyAuthenticationBeginRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])


class PasskeyAuthenticationCompleteRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    response: dict = Field(...)


class MFADisableRequest(BaseModel):
    mfa_code: str = Field(...)


class OAuthLoginRequest(BaseModel):
    provider: str = Field(..., examples=["google", "yandex", "vk"])


# ── Response schemas ──────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str = Field(...)
    refresh_token: str = Field(...)
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Access token TTL in seconds")


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(...)
    email: str = Field(...)
    display_name: str = Field(default="")
    avatar_url: str | None = Field(default=None)
    is_verified: bool = Field(default=False)
    created_at: datetime = Field(...)

    @classmethod
    def from_orm_model(cls, user: User) -> UserResponse:  # noqa: F821
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.full_name or "",
            avatar_url=user.avatar_url,
            is_verified=False,
            created_at=user.created_at,
        )


class ApiKeyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(...)
    name: str = Field(...)
    prefix: str = Field(..., description="Display-safe prefix (e.g. 'aeth••••••abcd')")
    created_at: datetime = Field(...)
    last_used_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)

    @classmethod
    def from_orm_model(cls, key: ApiKey, full_key: str | None = None) -> ApiKeyResponse:  # noqa: F821
        return cls(
            id=key.id,
            name=key.name,
            prefix=key.key_prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
        )


class ApiKeyCreateResponse(BaseModel):
    """Returned only at creation time — includes the full secret key."""

    api_key: ApiKeyResponse = Field(...)
    secret: str = Field(..., description="Full API key — shown only once")


class PasskeyRegistrationBeginResponse(BaseModel):
    challenge: str = Field(...)
    public_key: dict = Field(...)


class PasskeyAuthenticationBeginResponse(BaseModel):
    challenge: str = Field(...)
    public_key: dict = Field(...)


class MFACodeResponse(BaseModel):
    mfa_required: bool = Field(...)
    mfa_enabled: bool = Field(...)


class OAuthRedirectResponse(BaseModel):
    redirect_url: str = Field(...)


class OAuthCallbackResponse(BaseModel):
    access_token: str = Field(...)
    refresh_token: str = Field(...)


class MFATokenResponse(BaseModel):
    access_token: str = Field(...)
    refresh_token: str = Field(...)
    token_type: str = Field(default="bearer")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(...)
    new_password: str = Field(..., min_length=12)


class SessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(...)
    ip_address: str | None = Field(None)
    user_agent: str | None = Field(None)
    created_at: datetime = Field(...)
    expires_at: datetime = Field(...)


class InviteRequest(BaseModel):
    token: str = Field(...)
