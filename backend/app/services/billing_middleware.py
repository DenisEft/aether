"""Billing middleware — intercept AI inference to track token usage.

Wraps BaseDriver.infer() and infer_stream() to:
1. Check quota before request
2. Record token usage after successful request
3. Deny if over quota (raise HTTP 429)

Integration point: monkey-patches InferencePool to inject billing checks.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from uuid import UUID

from fastapi import HTTPException, status

from app.services.billing_service import BillingService, QuotaExceededError

logger = logging.getLogger("aether.billing.middleware")

# ContextVar for passing tenant_id through async call chain
# Set by the API layer before AI calls, read by billing middleware
_current_tenant_id: ContextVar[UUID | None] = ContextVar("billing_tenant_id", default=None)


def set_billing_tenant(tenant_id: UUID) -> None:
    """Set the current tenant ID for billing context."""
    _current_tenant_id.set(tenant_id)


def get_billing_tenant() -> UUID | None:
    """Get the current tenant ID for billing context."""
    return _current_tenant_id.get()


class BillingAIMiddleware:
    """Middleware that wraps AI driver inference with billing checks.

    Usage:
        middleware = BillingAIMiddleware(session)
        response = await middleware.checked_infer(driver, request)
    """

    def __init__(self, session, commit: bool = True):
        self.billing = BillingService(session)
        self._commit = commit

    async def check_and_record(
        self,
        tenant_id: UUID,
        prompt_tokens: int,
        completion_tokens: int,
        model: str = "unknown",
        driver_type: str = "unknown",
    ) -> None:
        """Check quota and record token usage.

        Called after a successful AI inference to track consumption.
        """
        try:
            # Check if we're within quota
            await self.billing.check_quota(tenant_id, "tokens", float(prompt_tokens + completion_tokens))
        except QuotaExceededError as e:
            logger.warning(
                f"AI quota exceeded: tenant={tenant_id} "
                f"metric={e.metric} current={e.current} limit={e.limit}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "metric": e.metric,
                    "used": e.current,
                    "limit": e.limit,
                    "message": (
                        f"Monthly {e.metric} quota exceeded: "
                        f"{e.current:.0f}/{e.limit:.0f}. "
                        f"Upgrade your plan for more."
                    ),
                },
            )

        # Record usage
        try:
            await self.billing.record_tokens(
                tenant_id=tenant_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
                driver_type=driver_type,
                commit=self._commit,
            )
        except Exception:
            # Don't block the response if usage recording fails
            logger.exception(f"Failed to record token usage for tenant={tenant_id}")


# Singleton billing service factory
async def get_billing_service(session) -> BillingService:
    """Get a BillingService instance for the current session."""
    return BillingService(session)
