"""Tests for security primitives: password hashing, JWT encode/decode, token generation."""
from __future__ import annotations

import os

import pytest

os.environ["AETHER_JWT_SECRET_KEY"] = "test-secret-for-security-tests-only"
os.environ["AETHER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


class TestPasswordHashing:
    """Password hashing and verification using argon2."""

    def test_hash_and_verify(self):
        from app.core.security import hash_password, verify_password

        plain = "MySecureP@ss1"
        hashed = hash_password(plain)

        assert hashed != plain
        assert hashed.startswith("$argon2")
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        from app.core.security import hash_password, verify_password

        hashed = hash_password("CorrectPass1!")
        assert verify_password("WrongPass1!", hashed) is False

    def test_hash_is_deterministic_per_input(self):
        """Same input produces different salts — different output."""
        from app.core.security import hash_password

        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2  # different salts


class TestJWT:
    """JWT encode, decode, and validation."""

    def test_encode_and_decode(self):
        from app.core.security import create_access_token, decode_token

        payload = {"sub": "user-123", "type": "access"}
        token = create_access_token(payload)
        decoded = decode_token(token)

        assert decoded is not None
        assert decoded["sub"] == "user-123"

    def test_decode_invalid_token_is_none(self):
        from app.core.security import decode_token

        assert decode_token("not.a.valid.jwt") is None
        assert decode_token("") is None
        assert decode_token("abc") is None

    def test_access_and_refresh_differ(self):
        from app.core.security import create_access_token, create_refresh_token

        payload = {"sub": "user-123"}
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)

        assert access != refresh
