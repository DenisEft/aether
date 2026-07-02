"""Security utilities: JWT, password hashing, API keys, MFA."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings

# ── Password hashing (Argon2) ────────────────────────────────
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ────────────────────────────────────────────────
def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data, expires_delta)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token."""
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    data["type"] = "refresh"
    return _create_token(data, expires_delta)


def decode_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns payload or None on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ── API Key utilities ─────────────────────────────────────────
API_KEY_PREFIX = "aeth"


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns ``(display_prefix, full_key)``. Store only the hash; the full key
    is shown once to the user.
    """
    token = secrets.token_hex(24)  # 48 hex chars
    full_key = f"{API_KEY_PREFIX}_{token}"
    return f"{API_KEY_PREFIX}••••••{token[-4:]}", full_key


def hash_api_key(key: str) -> str:
    """SHA-256 hash of an API key for secure storage."""
    return hashlib.sha256(key.encode()).hexdigest()


# ── MFA utilities ─────────────────────────────────────────
def generate_mfa_secret() -> str:
    """Generate a base32 encoded secret for TOTP."""
    return secrets.token_urlsafe(32)


def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret."""
    import pyotp
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate backup codes for MFA."""
    return [secrets.token_urlsafe(16) for _ in range(count)]


def validate_password_strength(password: str) -> bool:
    """Validate password strength."""
    # Check for minimum 12 characters
    if len(password) < 12:
        return False
    
    # Check for uppercase, lowercase, digit, and special character
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    return all([has_upper, has_lower, has_digit, has_special])