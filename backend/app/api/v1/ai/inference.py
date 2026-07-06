"""Inference and health endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.ai.manager import ai_manager
from app.ai.router import RoutingStrategy
from app.core.deps import CurrentActiveUser, DBDep

logger = logging.getLogger("aether.api.ai.inference")
router = APIRouter(tags=["inference"])


class InferencePayload(BaseModel):
    messages: list[dict]
    system_prompt: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=32768)
    stream: bool = False
    strategy: RoutingStrategy = RoutingStrategy.LEAST_LATENCY


@router.post("/infer")
async def run_inference(
    payload: InferencePayload,
    db: DBDep,
    current_user: CurrentActiveUser,
):
    """Run AI inference through the smart router."""
    response = await ai_manager.generate_response(
        messages=payload.messages,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        strategy=payload.strategy,
    )

    # Record token usage for billing (non-blocking — don't fail the response)
    if response.usage and response.usage.get("total_tokens", 0) > 0:
        try:
            from app.services.billing_middleware import BillingAIMiddleware

            middleware = BillingAIMiddleware(db)
            await middleware.check_and_record(
                tenant_id=current_user.tenant_id,
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
                model=response.model,
                driver_type=response.driver_type,
            )
        except Exception:
            # Billing failure must never block AI responses
            logger.exception("Billing middleware failed")
            pass

    return {
        "model": response.model,
        "driver": response.driver_type,
        "content": response.content,
        "finish_reason": response.finish_reason,
        "usage": response.usage,
        "latency_ms": response.latency_ms,
    }


@router.get("/health-summary")
async def ai_health_summary(
    current_user: CurrentActiveUser,
):
    """Get health status of all AI drivers."""
    return await ai_manager.health_summary()
