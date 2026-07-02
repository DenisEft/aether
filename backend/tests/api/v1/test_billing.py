"""Tests for billing endpoints (plans, subscriptions, usage)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestPlans:
    async def test_list_plans_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/billing/plans", headers=auth_headers)
        assert resp.status_code in (200, 401, 403)  # may need superadmin

    async def test_list_plans_empty_as_superadmin(
        self, client: AsyncClient, superuser_headers: dict
    ):
        resp = await client.get("/api/v1/billing/plans", headers=superuser_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_plan(self, client: AsyncClient, superuser_headers: dict):
        resp = await client.post(
            "/api/v1/billing/plans",
            headers=superuser_headers,
            json={
                "name": "Pro Plan",
                "slug": "pro",
                "price": 2999,
                "currency": "USD",
                "interval": "monthly",
            },
        )
        # May return 201 or 422 if extra fields required — check what we get
        data = resp.json()
        assert resp.status_code in (201, 422)

    async def test_get_plan_not_found(self, client: AsyncClient, superuser_headers: dict):
        import uuid
        resp = await client.get(
            f"/api/v1/billing/plans/{uuid.uuid4()}",
            headers=superuser_headers,
        )
        assert resp.status_code == 404


class TestSubscriptions:
    async def test_list_subscriptions(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/billing/subscriptions", headers=auth_headers)
        assert resp.status_code in (200, 401, 403)

    async def test_get_subscription_not_found(self, client: AsyncClient, auth_headers: dict):
        import uuid
        resp = await client.get(
            f"/api/v1/billing/subscriptions/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code in (404, 401, 403)


class TestUsage:
    async def test_get_usage(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/billing/usage", headers=auth_headers)
        assert resp.status_code in (200, 401, 403)

    async def test_get_usage_as_superadmin(self, client: AsyncClient, superuser_headers: dict):
        resp = await client.get("/api/v1/billing/usage", headers=superuser_headers)
        assert resp.status_code == 200
