"""Notification/email tasks (queue: default)."""

from __future__ import annotations

import logging

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, queue="default", max_retries=3, default_retry_delay=60, acks_late=True)
def send_magic_link(self, email: str, magic_link_token: str) -> dict:
    """Send a magic link login email."""
    logger.info("send_magic_link: email=%s", email)
    # Stage 4: connect to email provider
    return {"sent": False, "provider": "smtp"}


@celery.task(bind=True, queue="default", max_retries=3, default_retry_delay=60, acks_late=True)
def send_invitation(self, email: str, invite_token: str, org_name: str) -> dict:
    """Send an organisation invitation email."""
    logger.info("send_invitation: email=%s, org=%s", email, org_name)
    # Stage 4: connect to email provider
    return {"sent": False, "provider": "smtp"}


@celery.task(bind=True, queue="default", max_retries=1, acks_late=True)
def send_passwordless_code(self, email: str, code: str) -> dict:
    """Send a one-time passwordless login code."""
    logger.info("send_passwordless_code: email=%s", email)
    return {"sent": False, "provider": "smtp"}
