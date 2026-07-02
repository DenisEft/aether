"""Tests for tenant CRUD endpoints (superadmin only)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestTenantCRUD:
    async def test_list_tenants(self, client: AsyncClient, superuser_headers: dict, tenant: dict):
        resp = await client.get("/api/v1/tenants", headers=superuser_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_create_tenant(self, client: AsyncClient, superuser_headers: dict):
        resp = await client.post(
            "/api/v1/tenants",
            headers=superuser_headers,
            json={"slug": "new-tenant", "name": "New Tenant"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "new-tenant"
        assert "id" in data

    async def test_get_tenant(self, client: AsyncClient, superuser_headers: dict, tenant: dict):
        resp = await client.get(
            f"/api/v1/tenants/{tenant['id']}",
            headers=superuser_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["slug"] == tenant["slug"]

    async def test_update_tenant(self, client: AsyncClient, superuser_headers: dict, tenant: dict):
        resp = await client.patch(
            f"/api/v1/tenants/{tenant['id']}",
            headers=superuser_headers,
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_delete_tenant(self, client: AsyncClient, superuser_headers: dict):
        # Create then delete
        create = await client.post(
            "/api/v1/tenants",
            headers=superuser_headers,
            json={"slug": "to-delete", "name": "Delete Me"},
        )
        tid = create.json()["id"]
        resp = await client.delete(
            f"/api/v1/tenants/{tid}",
            headers=superuser_headers,
        )
        assert resp.status_code == 200

    async def test_regular_user_cannot_list_tenants(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/tenants", headers=auth_headers)
        assert resp.status_code in (401, 403)

    async def test_unauthenticated_cannot_list_tenants(self, client: AsyncClient):
        resp = await client.get("/api/v1/tenants")
        assert resp.status_code in (401, 403)
