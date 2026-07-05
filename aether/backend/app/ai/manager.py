"""AI Manager: orchestrates inference pool, intent matching, response generation."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import Intent

from ..services.billing_middleware import get_billing_service
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

    async def _billing_callback(
        self,
        tenant_id: UUID,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        driver_type: str,
    ) -> None:
        """Billing callback that gets the billing service from the database session."""
        # This will be called from SmartRouter with the current session
        # We can't access the session here directly, but this is a placeholder for when we get it from the calling context
        pass

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
        db: AsyncSession | None = None,
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
            # Create billing callback with the database session if provided
            billing_callback = None
            if db is not None and tenant_id is not None:

                async def _billing_callback(
                    tenant_id: UUID,
                    prompt_tokens: int,
                    completion_tokens: int,
                    model: str,
                    driver_type: str,
                ):
                    billing_service = await get_billing_service(db)
                    await billing_service.record_tokens(
                        tenant_id=tenant_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        model=model,
                        driver_type=driver_type,
                        commit=True,
                    )

                billing_callback = _billing_callback

            return await self._smart_router.generate(
                request, strategy=strategy, billing_callback=billing_callback
            )
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
        db: AsyncSession | None = None,
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
            # Create billing callback with the database session if provided
            billing_callback = None
            if db is not None and tenant_id is not None:

                async def _billing_callback(
                    tenant_id: UUID,
                    prompt_tokens: int,
                    completion_tokens: int,
                    model: str,
                    driver_type: str,
                ):
                    billing_service = await get_billing_service(db)
                    await billing_service.record_tokens(
                        tenant_id=tenant_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        model=model,
                        driver_type=driver_type,
                        commit=True,
                    )

                billing_callback = _billing_callback

            # For streaming we need to pass the billing callback
            # For now, we'll pass it through to the stream method
            async for chunk in self._smart_router.generate_stream(
                request, strategy=strategy, billing_callback=billing_callback
            ):
                yield chunk
        else:
            # Fallback to legacy pool
            selected = self._pool._select_driver(strategy)
            if not selected:
                raise RuntimeError("No healthy drivers available")

            key, entry = selected
            async for chunk in entry.driver.infer_stream(request):
                yield chunk

    # === Funnel: Incoming Message Processing ===

    async def process_incoming(
        self,
        text: str,
        tenant_id: str,
        channel_type: str = "telegram",
        conversation_id: str | None = None,
        db: AsyncSession | None = None,
        user_context: dict | None = None,
    ) -> dict:
        """Full funnel: classify intent → extract entities → generate AI response.

        This is THE main entry point for all incoming channel messages.
        Returns a dict with intent, entities, response_text, and metadata.
        """
        result = {
            "intent": None,
            "intent_name": None,
            "entities": {},
            "response_text": None,
            "model_used": None,
            "latency_ms": 0.0,
        }

        import time

        t0 = time.time()

        # Step 1: Classify intent
        if db:
            intent = await self.match_intent(text, tenant_id, db)
            if intent:
                result["intent"] = str(intent.id) if hasattr(intent, "id") else intent
                result["intent_name"] = (
                    intent.display_name if hasattr(intent, "display_name") else str(intent)
                )
                logger.info(f"Intent matched: {result['intent_name']} for tenant={tenant_id}")

        # Step 2: Build messages with context
        messages = []

        # System prompt — tenant-aware
        system_prompt = (
            f"You are an AI assistant for a business using Aether. "
            f"Channel: {channel_type}. "
            f"Be helpful, concise, and professional. "
            f"If this relates to a specific business process, identify the intent and extract key details."
        )
        if result["intent_name"]:
            system_prompt += f" Detected intent: {result['intent_name']}."

        messages.append({"role": "system", "content": system_prompt})

        # Add user context if available
        if user_context:
            ctx_parts = []
            if user_context.get("username"):
                ctx_parts.append(f"User: {user_context['username']}")
            if user_context.get("first_name"):
                ctx_parts.append(f"Name: {user_context['first_name']}")
            if ctx_parts:
                messages.append({"role": "system", "content": " | ".join(ctx_parts)})

        # User message
        messages.append({"role": "user", "content": text})

        # Step 3: Generate AI response
        response = await self.generate_response(
            messages=messages,
            tenant_id=tenant_id,
            db=db,
            max_tokens=1024,
            temperature=0.7,
        )

        result["response_text"] = response.content
        result["model_used"] = response.model
        result["latency_ms"] = (time.time() - t0) * 1000

        logger.info(
            f"Funnel complete: intent={result['intent_name']}, "
            f"model={result['model_used']}, "
            f"latency={result['latency_ms']:.0f}ms, "
            f"tenant={tenant_id}"
        )

        return result

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
    from .router import pool as inference_pool
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
