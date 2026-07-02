"""AI Manager: orchestrates inference pool, intent matching, response generation."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import Intent

from . import InferenceRequest, InferenceResponse
from .context_manager import ContextManager
from .inference_pool import InferencePool
from .model_registry import ModelRegistry
from .smart_router import SmartRouter

logger = logging.getLogger("aether.ai.manager")


class AIManager:
    """Central AI orchestration manager."""

    def __init__(
        self,
        smart_router: SmartRouter | None = None,
        inference_pool: InferencePool | None = None,
        model_registry: ModelRegistry | None = None,
    ):
        self._smart_router = smart_router
        self._pool = inference_pool or InferencePool()
        self._registry = model_registry or ModelRegistry()
        self._context_manager = (
            ContextManager(self._smart_router, self._registry) if self._smart_router else None
        )

    @property
    def smart_router(self) -> SmartRouter:
        return self._smart_router

    @property
    def inference_pool(self) -> InferencePool:
        return self._pool

    @property
    def model_registry(self) -> ModelRegistry:
        return self._registry

    @property
    def context_manager(self) -> ContextManager:
        return self._context_manager

    # === Intent Management ===

    async def match_intent(self, text: str, tenant_id: str, db: AsyncSession) -> Intent | None:
        """Match user text to an intent using simple keyword matching (v1).
        Stage 9: Replace with embedding-based semantic matching."""
        result = await db.execute(select(Intent).where(Intent.tenant_id == tenant_id))
        intents = result.scalars().all()

        text_lower = text.lower()
        best_score = 0.0
        best_intent: Intent | None = None

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
        strategy: str = "hybrid",
        tenant_id: str | None = None,
        conversation_id: str | None = None,
    ) -> InferenceResponse:
        """Generate a response using the best available AI driver."""

        # Create request with context handling
        request = InferenceRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            tenant_id=tenant_id,
        )

        # If we have smart router, use it for routing
        if self._smart_router:
            return await self._smart_router.generate(request, strategy=strategy)
        else:
            # Fallback to legacy pool
            return await self._pool.infer(request, strategy=strategy)

    async def generate_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        strategy: str = "hybrid",
        tenant_id: str | None = None,
    ):
        """Generate a streaming response."""
        from . import InferenceRequest

        request = InferenceRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            tenant_id=tenant_id,
        )

        # Get driver and stream
        if self._smart_router:
            async for chunk in self._smart_router.generate_stream(request, strategy=strategy):
                yield chunk
        else:
            # Fallback to legacy pool
            selected = self._pool._select_driver(strategy)
            if not selected:
                raise RuntimeError("No healthy drivers available")

            key, entry = selected
            async for chunk in entry.driver.infer_stream(request):
                yield chunk

    # === Health ===

    async def health_summary(self) -> dict:
        """Get health summary of all drivers."""
        if self._smart_router:
            return await self._smart_router.health_check()
        else:
            return self._pool.get_health_summary()


# Global AI manager singleton
ai_manager = AIManager()

# Initialize with smart router if available
try:
    from .inference_pool import pool as inference_pool
    from .model_registry import registry as model_registry
    from .smart_router import SmartRouter

    ai_manager = AIManager(
        smart_router=SmartRouter(inference_pool, model_registry),
        inference_pool=inference_pool,
        model_registry=model_registry,
    )
except Exception as e:
    logger.warning(f"Failed to initialize smart router components: {e}")
    # Fall back to basic manager
    ai_manager = AIManager()
