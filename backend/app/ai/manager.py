"""AI Manager: orchestrates inference pool, intent matching, response generation."""

from __future__ import annotations

import logging
from typing import Optional

from app.models.ai import Intent, IntentTemplate, AIModel, DriverConfig
from app.schemas.ai import IntentCreate, IntentUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from . import InferenceRequest, InferenceResponse
from .router import pool, InferencePool, RoutingStrategy

logger = logging.getLogger("aether.ai.manager")


class AIManager:
    """Central AI orchestration manager."""

    def __init__(self, inference_pool: InferencePool | None = None):
        self._pool = inference_pool or pool

    @property
    def inference_pool(self) -> InferencePool:
        return self._pool

    # === Intent Management ===

    async def match_intent(
        self, text: str, tenant_id: str, db: AsyncSession
    ) -> Optional[Intent]:
        """Match user text to an intent using simple keyword matching (v1).
        Stage 9: Replace with embedding-based semantic matching."""
        result = await db.execute(
            select(Intent)
            .where(Intent.tenant_id == tenant_id)
        )
        intents = result.scalars().all()

        text_lower = text.lower()
        best_score = 0.0
        best_intent: Optional[Intent] = None

        for intent in intents:
            # Simple keyword match (v1)
            keywords = [intent.name.lower(), intent.display_name.lower()]
            for kw in keywords:
                if kw in text_lower:
                    score = len(kw) / len(text_lower)
                    if score > best_score:
                        best_score = score
                        best_intent = intent

        return best_intent if best_score > 0.1 else None

    # === Inference ===

    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        strategy: RoutingStrategy = RoutingStrategy.LEAST_LATENCY,
    ) -> InferenceResponse:
        """Generate a response using the best available AI driver."""

        request = InferenceRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return await self._pool.infer(request, strategy=strategy)

    async def generate_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """Generate a streaming response."""
        from . import InferenceRequest

        request = InferenceRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Get driver and stream
        selected = self._pool._select_driver(RoutingStrategy.LEAST_LATENCY)
        if not selected:
            raise RuntimeError("No healthy drivers available")

        key, entry = selected
        async for chunk in entry.driver.infer_stream(request):
            yield chunk

    # === Health ===

    async def health_summary(self) -> dict:
        """Get health summary of all drivers."""
        return self._pool.get_health_summary()


# Global AI manager singleton
ai_manager = AIManager()
