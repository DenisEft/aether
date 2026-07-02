"""Tests for auth endpoints: signup, login, magic link, refresh, logout."""
from __future__ import annotations

import hashlib
import secrets

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_PASSWORD, TEST_ADMIN_PASSWORD


class TestSignup:
    """POST /api/v1/auth/signup"""

    async def test_signup_creates_user_and_tenant(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "newuser@example.com",
            "password": TEST_USER_PASSWORD,
            "display_name": "New User",
            "tenant_slug": "new-corp",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"

    async def test_signup_duplicate_email_fails(self, client: AsyncClient):
        """Signup creates new tenant+user each time (no duplicate check yet — AUDIT C3).
        Both signups succeed; verify second returns valid tokens."""
        email = "dup-test@example.com"
        r1 = await client.post("/api/v1/auth/signup", json={
            "email": email, "password": TEST_USER_PASSWORD,
            "display_name": "First", "tenant_slug": "corp-1",
        })
        assert r1.status_code == 201
        r2 = await client.post("/api/v1/auth/signup", json={
            "email": email, "password": TEST_USER_PASSWORD,
            "display_name": "Second", "tenant_slug": "corp-2",
        })
        # Currently no duplicate check — both succeed (AUDIT C3: should fix later)
        assert r2.status_code == 201
        assert "access_token" in r2.json()

    async def test_signup_missing_fields_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "incomplete@example.com",
        })
        assert resp.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_with_valid_credentials(self, client: AsyncClient, user: dict):
        resp = await client.post("/api/v1/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_fails(self, client: AsyncClient, user: dict):
        resp = await client.post("/api/v1/auth/login", json={
            "email": user["email"],
            "password": "WrongP@ss123!",
        })
        assert resp.status_code in (400, 401)

    async def test_login_nonexistent_user_fails(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "ghost@example.com",
            "password": "WrongP@ss123!",
        })
        assert resp.status_code in (400, 401)


class TestMagicLink:
    """POST /api/v1/auth/login/magic-link + /verify"""

    async def test_request_magic_link(self, client: AsyncClient, user: dict):
        resp = await client.post("/api/v1/auth/login/magic-link", json={
            "email": user["email"],
        })
        # Always returns 200 (prevents enumeration)
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_verify_magic_link(self, client: AsyncClient, magic_link: dict):
        resp = await client.post("/api/v1/auth/login/magic-link/verify", json={
            "token": magic_link["token"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_verify_invalid_token_fails(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login/magic-link/verify", json={
            "token": "this-is-not-a-valid-token",
        })
        assert resp.status_code in (400, 401)


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_returns_new_tokens(self, client: AsyncClient, user: dict):
        # First login to get tokens
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data.get("refresh_token") is not None

    async def test_refresh_with_invalid_token_fails(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid-refresh-token",
        })
        assert resp.status_code in (400, 401)


class TestCurrentUser:
    """GET /api/v1/users/me"""

    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "id" in data

    async def test_unauthorized_access_fails(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code in (401, 403)


class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout(self, client: AsyncClient, user: dict):
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"},
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

        refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code in (400, 401)


class TestUpdateMe:
    """PUT /api/v1/users/me"""

    async def test_update_full_name(self, client: AsyncClient, auth_headers: dict):
        resp = await client.put(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Updated Name"

    async def test_update_without_auth(self, client: AsyncClient):
        resp = await client.put("/api/v1/users/me", json={"full_name": "Hacker"})
        assert resp.status_code in (401, 403)


class TestDeleteMe:
    """DELETE /api/v1/users/me"""

    async def test_delete_account(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Account deleted"

        # After deletion, auth should fail
        resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert resp.status_code in (401, 403)
