"""Tests for health endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealth:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "healthy" or data.get("status") == "ok"

    async def test_health_includes_version(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert "version" in resp.json()
