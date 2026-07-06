"""Aether API — FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_v1_router
from app.api.v1.ws import router as ws_router
from app.config import settings
from app.database import close_engine, engine
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.tenant import TenantContextMiddleware

logging.basicConfig(
    level=logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)

app = FastAPI(
    title="Aether API",
    version="0.1.0",
    description="Multi-tenant SaaS backend for Aether",
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(TenantContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api")
app.include_router(ws_router)


# ── Lifespan ──────────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    """Verify DB connectivity and initialize AI pool."""
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:
        logging.warning("DB connection unavailable on startup: %s", exc)

    # Initialize AI drivers from DB config
    if settings.AI_LOCAL_DRIVER_ENABLED:
        try:
            from app.ai import LocalDriver
            from app.ai.router import pool

            local_driver = LocalDriver(
                model_id=settings.AI_LOCAL_DRIVER_MODEL_ID,
                base_url=settings.AI_LOCAL_DRIVER_URL,
            )
            pool.register(local_driver, priority=10, cost_per_1k=0, max_concurrent=5)
            await local_driver.initialize()
            logging.info(
                "Local AI driver registered on port %s (model: %s)",
                settings.AI_LOCAL_DRIVER_URL,
                settings.AI_LOCAL_DRIVER_MODEL_ID,
            )
        except Exception as exc:
            logging.warning("Could not register local AI driver: %s", exc)

    # Start background health checks
    try:
        await pool.start_health_checks()
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown() -> None:
    """Dispose DB connection pool and shutdown AI drivers."""
    try:
        from app.ai.router import pool

        await pool.shutdown_all()
    except Exception:
        pass
    await close_engine()
