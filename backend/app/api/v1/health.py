from __future__ import annotations

import time

import sqlalchemy
from fastapi import APIRouter

from app.config import settings
from app.database import engine

router = APIRouter(tags=["health"])

_start_time: float = time.time()


@router.get("/health", summary="Health check")
async def health_check() -> dict:
    """Return service health status including DB and Redis connectivity."""
    # ── PostgreSQL ────────────────────────────────────────────
    db_status = "disconnected"
    db_latency_ms: float | None = None

    try:
        async with engine.connect() as conn:
            before = time.perf_counter()
            await conn.execute(sqlalchemy.text("SELECT 1"))
            after = time.perf_counter()
            db_latency_ms = round((after - before) * 1000, 2)
            db_status = "connected"
    except Exception as exc:
        db_status = f"error: {exc}"

    # ── Redis ─────────────────────────────────────────────────
    redis_status = "not configured"
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_status = "connected"
        await r.close()
    except Exception as exc:
        redis_status = f"error: {exc}"

    uptime_seconds = round(time.time() - _start_time, 1)

    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime": uptime_seconds,
        "db": {
            "status": db_status,
            "latency_ms": db_latency_ms,
        },
        "redis": {
            "status": redis_status,
        },
    }
