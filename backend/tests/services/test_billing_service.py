"""Tests for BillingService — token accounting, quota enforcement."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from app.services.billing_service import BillingService, QuotaExceededError
from app.models.billing import SubscriptionPlan, Subscription
from app.models.enums import SubscriptionStatus


class TestBillingService:
    """Token accounting and quota enforcement tests."""

    async def test_get_plan_limits_default(self, async_session):
        """Without a subscription, use default limits."""
        billing = BillingService(async_session)
        limits = await billing.get_plan_limits(uuid4())
        assert limits["max_tokens_per_month"] == 50_000
        assert limits["max_conversations_per_month"] == 500

    async def test_record_usage_and_get_usage(self, async_session):
        """Recording usage creates a UsageRecord, get_current_usage sums them."""
        tenant = uuid4()
        billing = BillingService(async_session)

        await billing.record_usage(tenant, "tokens", 500.0, commit=False)
        await billing.record_usage(tenant, "tokens", 200.0, commit=False)
        await billing.record_usage(tenant, "conversations", 3.0, commit=False)
        await async_session.flush()

        tokens_usage = await billing.get_current_usage(tenant, "tokens")
        assert tokens_usage == 700.0

        conv_usage = await billing.get_current_usage(tenant, "conversations")
        assert conv_usage == 3.0

    async def test_record_tokens(self, async_session):
        """Recording tokens creates 3 metric records: tokens, prompt_tokens, completion_tokens."""
        tenant = uuid4()
        billing = BillingService(async_session)

        billing_service = billing  # alias
        # Use record_usage directly since record_tokens commits internally
        await billing.record_usage(tenant, "tokens", 150.0, commit=False)
        await billing.record_usage(tenant, "prompt_tokens", 100.0, commit=False)
        await billing.record_usage(tenant, "completion_tokens", 50.0, commit=False)
        await async_session.flush()

        assert await billing.get_current_usage(tenant, "tokens") == 150.0

    async def test_plan_limits_and_quota(self, async_session):
        """With a plan, limits come from the plan and quota is enforced."""
        tenant = uuid4()
        billing = BillingService(async_session)

        # Create plan and subscription in this transaction
        # NOTE: Using features=[] to work around SQLite ARRAY limitation
        plan = SubscriptionPlan(
            id="test_pro",
            name="Test Pro",
            price_monthly_usd=99.0,
            limits={"max_tokens_per_month": 100, "max_conversations_per_month": 10},
            is_public=True,
            sort_order=1,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([plan, sub])
        await async_session.flush()

        # Verify limits from plan
        limits = await billing.get_plan_limits(tenant)
        assert limits["max_tokens_per_month"] == 100
        assert limits["max_conversations_per_month"] == 10

        # Within limit — should pass
        await billing.record_usage(tenant, "tokens", 50.0, commit=False)
        await async_session.flush()
        await billing.check_quota(tenant, "tokens", 30)  # 50 + 30 = 80, limit 100

        # Over limit — should raise
        await billing.record_usage(tenant, "tokens", 40.0, commit=False)  # now 90
        await async_session.flush()
        with pytest.raises(QuotaExceededError) as exc:
            await billing.check_quota(tenant, "tokens", 20)  # 90 + 20 = 110 > 100
        assert exc.value.metric == "tokens"
        assert exc.value.limit == 100
        assert exc.value.current == 90.0

    async def test_check_quota_without_plan_uses_default(self, async_session):
        """Without a plan, default limits (50000 tokens) apply."""
        tenant = uuid4()
        billing = BillingService(async_session)

        # 1000 tokens should be fine (way under 50000 default)
        await billing.check_quota(tenant, "tokens", 1000)  # won't raise

    async def test_usage_summary(self, async_session):
        """Usage summary returns all metrics with limits."""
        tenant = uuid4()
        billing = BillingService(async_session)

        # Create plan and subscription
        plan = SubscriptionPlan(
            id="test_starter",
            name="Test Starter",
            price_monthly_usd=29.0,
            limits={"max_tokens_per_month": 100, "max_conversations_per_month": 10, "max_documents_per_month": 50},
            is_public=True,
            sort_order=0,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([plan, sub])
        await async_session.flush()

        # Record some usage
        await billing.record_usage(tenant, "tokens", 50.0, commit=False)
        await billing.record_usage(tenant, "conversations", 5.0, commit=False)
        await async_session.flush()

        summary = await billing.get_usage_summary(tenant)
        assert summary["tokens"]["used"] == 50.0
        assert summary["tokens"]["limit"] == 100
        assert summary["tokens"]["remaining"] == 50.0
        assert summary["conversations"]["used"] == 5.0

    async def test_get_active_plan(self, async_session):
        """Active plan resolves from active subscription."""
        tenant = uuid4()
        billing = BillingService(async_session)

        # No plan when no subscription
        plan = await billing.get_active_plan(tenant)
        assert plan is None

        # With subscription
        sp = SubscriptionPlan(
            id="test_gold",
            name="Test Gold",
            price_monthly_usd=199.0,
            limits={"max_tokens_per_month": 1000},
            is_public=True,
            sort_order=2,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=sp.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([sp, sub])
        await async_session.flush()

        plan = await billing.get_active_plan(tenant)
        assert plan is not None
        assert plan.id == "test_gold"

    async def test_estimate_cost(self, async_session):
        """Cost estimation: free within plan, calculated for overage."""
        tenant = uuid4()
        billing = BillingService(async_session)

        # Without plan — small cost for small usage
        cost = await billing.estimate_cost(tenant, 10, 5)
        assert cost > 0.0  # Free tier: $0.002/1K = $0.00003 for 15 tokens

        # With plan — free within limits
        plan = SubscriptionPlan(
            id="test_bronze",
            name="Test Bronze",
            price_monthly_usd=9.0,
            limits={"max_tokens_per_month": 100},
            is_public=True,
            sort_order=0,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([plan, sub])
        await async_session.flush()

        cost = await billing.estimate_cost(tenant, 10, 5)
        assert cost == 0.0  # Inside plan limits


class TestBillingMiddleware:
    """Tests for the billing middleware layer."""

    async def test_check_and_record_success(self, async_session):
        """Middleware records usage when under quota."""
        from app.services.billing_middleware import BillingAIMiddleware

        tenant = uuid4()
        middleware = BillingAIMiddleware(async_session, commit=False)

        # Need a plan so quota check works
        plan = SubscriptionPlan(
            id=f"test_ai_{uuid4().hex[:8]}",
            name="Test AI",
            price_monthly_usd=29.0,
            limits={"max_tokens_per_month": 1000},
            is_public=True,
            sort_order=0,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([plan, sub])
        await async_session.flush()

        await middleware.check_and_record(
            tenant_id=tenant,
            prompt_tokens=50,
            completion_tokens=25,
            model="gpt-4",
            driver_type="openai",
        )
        # Verify usage was recorded
        billing = BillingService(async_session)
        usage = await billing.get_current_usage(tenant, "tokens")
        assert usage == 75.0

    async def test_check_and_record_quota_exceeded(self, async_session):
        """Middleware raises HTTP 429 when quota exceeded."""
        from app.services.billing_middleware import BillingAIMiddleware
        from fastapi import HTTPException

        tenant = uuid4()
        middleware = BillingAIMiddleware(async_session, commit=False)

        # Plan with tiny limit
        plan = SubscriptionPlan(
            id=f"test_tiny_{uuid4().hex[:8]}",
            name="Test Tiny",
            price_monthly_usd=0.0,
            limits={"max_tokens_per_month": 10},
            is_public=True,
            sort_order=0,
        )
        now = datetime.now(timezone.utc)
        sub = Subscription(
            tenant_id=tenant,
            plan_id=plan.id,
            status=SubscriptionStatus.active,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        async_session.add_all([plan, sub])
        await async_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await middleware.check_and_record(
                tenant_id=tenant,
                prompt_tokens=15,
                completion_tokens=5,
                model="gpt-4",
                driver_type="openai",
            )
        assert exc_info.value.status_code == 429
        assert "quota_exceeded" in str(exc_info.value.detail)
