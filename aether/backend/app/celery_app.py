"""Celery application factory for Aether background tasks.

Architecture:
  - default    queue: email, notifications, simple I/O (4 workers)
  - ai         queue: AI inference, NLP processing (2 workers)
  - long_running queue: maintenance, reporting (1 worker)
"""

from __future__ import annotations

import logging

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)


def create_celery() -> Celery:
    broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL
    result_backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL

    if not broker_url:
        raise RuntimeError(
            "Neither CELERY_BROKER_URL nor REDIS_URL is configured. "
            "Set AETHER_REDIS_URL or AETHER_CELERY_BROKER_URL in .env"
        )

    app = Celery(
        "aether",
        broker=broker_url,
        backend=result_backend,
        include=[
            "app.tasks.notifications",
            "app.tasks.ai",
            "app.tasks.maintenance",
        ],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        task_queues={
            "default": {"routing_key": "default"},
            "ai": {"routing_key": "ai"},
            "long_running": {"routing_key": "long_running"},
        },
        task_routes={
            "app.tasks.notifications.*": {"queue": "default"},
            "app.tasks.ai.*": {"queue": "ai"},
            "app.tasks.maintenance.*": {"queue": "long_running"},
        },  # type: ignore[dict-item]
        task_default_queue="default",
        task_default_routing_key="default",
        worker_send_task_events=True,
        task_send_sent_event=True,
        result_expires=3600,  # 1 hour
    )

    return app


celery = create_celery()
