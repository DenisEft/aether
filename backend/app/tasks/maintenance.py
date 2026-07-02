"""Maintenance tasks (queue: long_running)."""

from __future__ import annotations

import logging

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, queue="long_running", max_retries=1, acks_late=True)
def cleanup_expired_tokens(self) -> dict:
    """Remove expired refresh tokens, magic links, and sessions."""
    logger.info("cleanup_expired_tokens: starting")
    # Stage 4: implement token cleanup
    return {"deleted": 0}


@celery.task(bind=True, queue="long_running", max_retries=1, acks_late=True)
def generate_usage_report(self, tenant_id: str | None = None) -> dict:
    """Generate a periodic usage report for billing."""
    logger.info("generate_usage_report: tenant=%s", tenant_id or "all")
    # Stage 4: aggregate usage records
    return {"tenants": 0, "total_cost_usd": 0.0}


@celery.task(bind=True, queue="long_running", max_retries=1, acks_late=True)
def check_driver_health(self) -> dict:
    """Periodically check health of all AI drivers."""
    logger.info("check_driver_health: starting")
    # Stage 4: ping all registered drivers
    return {"total": 0, "healthy": 0, "unhealthy": 0}
