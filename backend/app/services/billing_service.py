"""Billing service: token accounting, plan enforcement, usage tracking.

Centralized service for:
- Checking if a tenant has available tokens/credits for an AI operation
- Recording token usage against the tenant's subscription plan
- Enforcing plan limits (tokens, conversations, documents, etc.)
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription, SubscriptionPlan, UsageRecord
from app.models.enums import SubscriptionStatus, UsagePeriod

logger = logging.getLogger("aether.billing")


class QuotaExceededError(Exception):
    """Raised when a tenant exceeds their plan limits."""

    def __init__(self, metric: str, limit: float, current: float):
        self.metric = metric
        self.limit = limit
        self.current = current
        super().__init__(f"Quota exceeded: {metric} ({current}/{limit})")


class BillingService:
    """Token accounting and plan enforcement service."""

    DEFAULT_LIMITS = {
        "max_tokens_per_month": 50_000,
        "max_conversations_per_month": 500,
        "max_documents_per_month": 200,
        "max_users": 3,
        "max_channels": 2,
    }

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Plan resolution ──────────────────────────────────────

    async def get_active_plan(self, tenant_id: UUID) -> SubscriptionPlan | None:
        """Get the active subscription plan for a tenant, or None if no active sub."""
        result = await self._session.execute(
            select(SubscriptionPlan)
            .join(Subscription, Subscription.plan_id == SubscriptionPlan.id)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trial]),
            )
            .limit(1)
        )
        sub = result.scalar_one_or_none()
        return sub

    async def get_plan_limits(self, tenant_id: UUID) -> dict:
        """Get effective limits for a tenant — plan limits or defaults."""
        plan = await self.get_active_plan(tenant_id)
        if plan and plan.limits:
            return {**self.DEFAULT_LIMITS, **plan.limits}
        return self.DEFAULT_LIMITS

    # ── Quota checks ─────────────────────────────────────────

    async def check_quota(self, tenant_id: UUID, metric: str, amount: float = 1.0) -> None:
        """Check if a tenant has quota for a given metric. Raises QuotaExceededError.

        Args:
            tenant_id: The tenant to check.
            metric: e.g. 'tokens', 'conversations', 'documents'.
            amount: How much of the metric is being consumed (for incremental checks).
        """
        limits = await self.get_plan_limits(tenant_id)

        # Map metric to limit key
        limit_key_map = {
            "tokens": "max_tokens_per_month",
            "conversations": "max_conversations_per_month",
            "documents": "max_documents_per_month",
            "users": "max_users",
            "channels": "max_channels",
        }

        limit_key = limit_key_map.get(metric)
        if limit_key is None:
            logger.warning(f"Unknown metric: {metric}, skipping quota check")
            return

        limit = limits.get(limit_key, 0)
        if limit == 0:
            # No limit set — unlimited
            return

        current = await self.get_current_usage(tenant_id, metric)
        if current + amount > limit:
            raise QuotaExceededError(
                metric=metric,
                limit=limit,
                current=current,
            )

    # ── Usage tracking ───────────────────────────────────────

    async def get_current_usage(self, tenant_id: UUID, metric: str) -> float:
        """Get current usage for a metric in the current billing period (month)."""
        period_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self._session.execute(
            select(func.coalesce(func.sum(UsageRecord.value), 0.0)).where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.metric == metric,
                UsageRecord.recorded_at >= period_start,
            )
        )
        return float(result.scalar_one())

    async def record_usage(
        self,
        tenant_id: UUID,
        metric: str,
        value: float = 1.0,
        period: UsagePeriod = UsagePeriod.daily,
        metadata: dict | None = None,
        commit: bool = True,
    ) -> UsageRecord:
        """Record a usage event.

        Args:
            tenant_id: Tenant consuming the resource.
            metric: What was consumed ('tokens', 'conversations', 'documents', etc.)
            value: Quantity consumed.
            period: Aggregation period.
            metadata: Optional extra data (model used, request type, etc.)
            commit: If False, only flush — caller manages transaction. Use False in tests.
        """
        record = UsageRecord(
            tenant_id=tenant_id,
            metric=metric,
            value=value,
            period=period,
        )
        # UsageRecord doesn't have a metadata field — log it instead
        if metadata:
            logger.debug(f"Usage metadata: tenant={tenant_id} metric={metric} meta={metadata}")

        self._session.add(record)
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        await self._session.refresh(record)
        return record

    async def record_tokens(
        self,
        tenant_id: UUID,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "unknown",
        driver_type: str = "unknown",
        commit: bool = True,
    ) -> UsageRecord:
        """Record AI token usage. Convenience method for recording tokens specifically.

        Creates three usage records: tokens (combined), prompt_tokens, completion_tokens.
        """
        total = prompt_tokens + completion_tokens
        metadata = {"model": model, "driver_type": driver_type}

        # All three records share the same transaction
        await self.record_usage(tenant_id, "tokens", float(total), metadata=metadata, commit=False)
        await self.record_usage(
            tenant_id, "prompt_tokens", float(prompt_tokens), metadata=metadata, commit=False
        )
        await self.record_usage(
            tenant_id,
            "completion_tokens",
            float(completion_tokens),
            metadata=metadata,
            commit=False,
        )

        if commit:
            await self._session.commit()

        # Return the main tokens record
        result = await self._session.execute(
            select(UsageRecord)
            .where(UsageRecord.tenant_id == tenant_id, UsageRecord.metric == "tokens")
            .order_by(UsageRecord.recorded_at.desc())
            .limit(1)
        )
        return result.scalar_one()

    # ── Cost estimation ──────────────────────────────────────

    async def estimate_cost(
        self, tenant_id: UUID, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Estimate cost in USD for a token usage based on plan pricing."""
        plan = await self.get_active_plan(tenant_id)
        if plan is None:
            # Free tier: $0.002 per 1K tokens (standard rate)
            return (prompt_tokens + completion_tokens) * 0.002 / 1000

        # Plan-based pricing: use plan limits to determine if overage
        limits = await self.get_plan_limits(tenant_id)
        tokens_used = await self.get_current_usage(tenant_id, "tokens")
        max_tokens = limits.get("max_tokens_per_month", 50_000)
        total = prompt_tokens + completion_tokens

        if tokens_used + total <= max_tokens:
            return 0.0  # Included in plan

        # Overage pricing
        overage = tokens_used + total - max_tokens
        return overage * 0.002 / 1000

    # ── Tenant status ────────────────────────────────────────

    async def get_usage_summary(self, tenant_id: UUID) -> dict:
        """Get a summary of all usage metrics for the current month."""
        limits = await self.get_plan_limits(tenant_id)
        summary = {}
        metric_keys = ["tokens", "conversations", "documents"]

        for metric in metric_keys:
            current = await self.get_current_usage(tenant_id, metric)
            limit_key = {
                "tokens": "max_tokens_per_month",
                "conversations": "max_conversations_per_month",
                "documents": "max_documents_per_month",
            }[metric]
            summary[metric] = {
                "used": current,
                "limit": limits.get(limit_key, 0),
                "remaining": max(0, limits.get(limit_key, 0) - current)
                if limits.get(limit_key, 0) > 0
                else float("inf"),
            }

        return summary
