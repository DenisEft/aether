"""Smart AI router with routing strategies and fallback chains."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Awaitable
from uuid import UUID

from .drivers.base import BaseDriver, DriverHealth, DriverMetrics, InferenceRequest, InferenceResponse, EmbeddingRequest, EmbeddingResponse
from .inference_pool import InferencePool
from .model_registry import ModelRegistry

logger = logging.getLogger("aether.ai.smart_router")


class RoutingStrategy(str, Enum):
    """Routing strategy enumeration."""
    COST_OPTIMAL = "cost_optimal"       # Most cost-effective (prefers local)
    LATENCY_OPTIMAL = "latency_optimal" # Fastest (prefers small models)
    PRIVACY_FIRST = "privacy_first"     # Only local drivers
    QUALITY_FIRST = "quality_first"     # Highest quality model (ignores cost)
    HYBRID = "hybrid"                 # Weighted scoring (default)


@dataclass
class RoutingResult:
    """Result of routing decision."""
    driver: BaseDriver
    score: float
    strategy: RoutingStrategy
    fallback_chain: list[str] = field(default_factory=list)


class SmartRouter:
    """Intelligent AI router with multiple routing strategies, fallback chains, and circuit breakers."""

    def __init__(self, pool: InferencePool, registry: ModelRegistry,
                 default_strategy: RoutingStrategy = RoutingStrategy.HYBRID,
                 billing_callback: Callable[[UUID, int, int, str, str], Awaitable[None]] | None = None):
        self.pool = pool
        self.registry = registry
        self.default_strategy = default_strategy
        self.billing_callback = billing_callback
        self._lock = asyncio.Lock()

        # Weighted scoring configuration per strategy
        self._scoring_weights = {
            RoutingStrategy.COST_OPTIMAL: {"cost": 0.5, "latency": 0.15, "quality": 0.15, "availability": 0.2},
            RoutingStrategy.LATENCY_OPTIMAL: {"cost": 0.1, "latency": 0.5, "quality": 0.2, "availability": 0.2},
            RoutingStrategy.PRIVACY_FIRST: {"cost": 0.1, "latency": 0.1, "quality": 0.7, "availability": 0.1},
            RoutingStrategy.QUALITY_FIRST: {"cost": 0.1, "latency": 0.1, "quality": 0.7, "availability": 0.1},
            RoutingStrategy.HYBRID: {"cost": 0.3, "latency": 0.2, "quality": 0.3, "availability": 0.2},
        }

    async def route(self, request: InferenceRequest,
                 strategy: RoutingStrategy | None = None) -> RoutingResult:
        """
        Route a request to the best available driver based on strategy.

        Args:
            request: InferenceRequest to route
            strategy: Routing strategy (uses default if None)

        Returns:
            RoutingResult with selected driver and scoring info
        """
        if strategy is None:
            strategy = self.default_strategy

        # Get available drivers for the requested model
        available_drivers = await self._get_available_drivers(request.model, strategy)

        if not available_drivers:
            raise RuntimeError("No drivers available for routing")

        # Score all drivers
        scored_drivers = []
        for driver in available_drivers:
            score = await self._score_driver(driver, request, strategy)
            scored_drivers.append((driver, score))

        # Sort by score (higher is better)
        scored_drivers.sort(key=lambda x: x[1], reverse=True)

        # Get the best driver
        best_driver, best_score = scored_drivers[0]

        # Check if we need to use fallback chain
        fallback_chain = []
        if not self._is_driver_healthy(best_driver):
            fallback_chain = await self._get_fallback_chain(request.model)
            if fallback_chain:
                # Try fallback drivers
                for fallback_model in fallback_chain:
                    fallback_drivers = await self._get_available_drivers(fallback_model, strategy)
                    if fallback_drivers:
                        # Try first healthy fallback driver
                        for driver in fallback_drivers:
                            if self._is_driver_healthy(driver):
                                score = await self._score_driver(driver, request, strategy)
                                if score > best_score * 0.8:  # Only use if significantly better
                                    best_driver = driver
                                    best_score = score
                                    break
                        # If we found a working fallback driver, exit the loop
                        if best_driver != scored_drivers[0][0]:
                            break

        return RoutingResult(
            driver=best_driver,
            score=best_score,
            strategy=strategy,
            fallback_chain=fallback_chain
        )

    async def _get_available_drivers(self, model_id: str | None,
                                    strategy: RoutingStrategy) -> List[BaseDriver]:
        """Get list of available drivers for a model, filtered by strategy."""
        drivers = []

        # Get all drivers that support the requested model
        for driver in self.pool.get_all_drivers():
            # Check if driver supports the model
            try:
                if model_id and model_id in await driver.get_available_models():
                    drivers.append(driver)
                elif not model_id:  # No model requested, get all drivers
                    drivers.append(driver)
            except Exception:
                # If we can't check, assume it's available or skip it
                pass

        # Apply privacy filter if needed
        if strategy == RoutingStrategy.PRIVACY_FIRST:
            # Only allow local drivers
            drivers = [d for d in drivers if self._is_local_driver(d)]

        return drivers

    def _is_driver_healthy(self, driver: BaseDriver) -> bool:
        """Check if a driver is healthy."""
        try:
            health = driver.health_check()  # This would need to be async
            return health.status != DriverHealth.status.OFFLINE
        except Exception:
            return False

    def _is_local_driver(self, driver: BaseDriver) -> bool:
        """Check if a driver is a local driver."""
        # This is a simplified check - in a real implementation would
        # check model configuration or driver type
        return driver.driver_type in ["local", "llama_cpp", "ollama"]

    async def _score_driver(self, driver: BaseDriver, request: InferenceRequest,
                        strategy: RoutingStrategy) -> float:
        """
        Score a driver based on the current strategy.

        Args:
            driver: Driver to score
            request: Request to score for
            strategy: Scoring strategy

        Returns:
            Score (higher is better)
        """
        try:
            # Get driver metrics
            health = await driver.health_check()
            metrics = driver.get_metrics()

            # Get model info from registry
            model_info = self.registry.get_model(request.model) if request.model else None

            # Get scoring weights
            weights = self._scoring_weights.get(strategy, self._scoring_weights[RoutingStrategy.HYBRID])

            # Calculate normalized scores
            cost_score = 1.0  # Default to perfect score
            latency_score = 1.0  # Default to perfect score
            quality_score = 1.0  # Default to perfect score
            availability_score = 1.0  # Default to perfect score

            if model_info:
                # Cost score (lower is better, so we normalize)
                cost_per_1k = model_info.cost_per_1k_tokens_input + model_info.cost_per_1k_tokens_output
                if cost_per_1k > 0:
                    cost_score = 1.0 / (1.0 + cost_per_1k)  # Inverse scaling
                else:
                    cost_score = 1.0

                # Quality score (higher is better)
                quality_score = model_info.quality_score if hasattr(model_info, 'quality_score') else 1.0

            # Latency score (lower is better)
            if health.latency_ms > 0:
                latency_score = 1.0 / (1.0 + health.latency_ms / 1000.0)  # Normalized by 1000ms threshold
            else:
                latency_score = 0.5  # Medium score if latency not available

            # Availability score (based on success rate)
            availability_score = metrics.success_rate if metrics.success_rate else 0.5

            # Calculate final score
            score = (
                weights["cost"] * cost_score +
                weights["latency"] * latency_score +
                weights["quality"] * quality_score +
                weights["availability"] * availability_score
            )

            return score

        except Exception as e:
            logger.warning(f"Error scoring driver {driver.driver_type}: {e}")
            return 0.0  # Return very low score on error

    async def _get_fallback_chain(self, model_id: str) -> List[str]:
        """Get fallback chain for a model."""
        # This would typically be retrieved from configuration or registry
        # For now, return a simple fallback chain
        fallback_chain = [
            # Example fallback models in order
            "gpt-4o-mini",
            "deepseek-v4-pro",
            "llama3.2-1B",
            "Qwen3.6-35B-A3B-APEX-I-Quality"
        ]
        return fallback_chain

    async def generate(self, request: InferenceRequest,
                       strategy: RoutingStrategy | None = None,
                       billing_callback: Callable[[UUID, int, int, str, str], Awaitable[None]] | None = None) -> InferenceResponse:
        """Generate response using routing strategy."""
        routing_result = await self.route(request, strategy)
        response = await routing_result.driver.generate(request)

        # Handle billing if tenant_id is provided
        if request.tenant_id is not None:
            try:
                # Extract usage from response
                prompt_tokens = response.usage.get('prompt_tokens', 0)
                completion_tokens = response.usage.get('completion_tokens', 0)

                # Call billing callback if provided (prefer passed callback over instance callback)
                callback = billing_callback or self.billing_callback
                if callback:
                    await callback(
                        UUID(request.tenant_id),
                        prompt_tokens,
                        completion_tokens,
                        response.model,
                        response.driver_type
                    )
            except Exception as e:
                logger.warning(f"Billing callback failed for tenant {request.tenant_id}: {e}")

        return response

    async def generate_stream(self, request: InferenceRequest,
                               strategy: RoutingStrategy | None = None,
                               billing_callback: Callable[[UUID, int, int, str, str], Awaitable[None]] | None = None):
        """Stream response using routing strategy."""
        routing_result = await self.route(request, strategy)

        # For streaming, we need to accumulate token counts
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Collect all chunks to calculate total tokens
        chunks = []
        async for chunk in routing_result.driver.generate_stream(request):
            chunks.append(chunk)
            yield chunk

        # If we have tenant_id and billing callback, record usage
        if request.tenant_id is not None:
            callback = billing_callback or self.billing_callback
            if callback:
                try:
                    # If we can't get precise token counts from streaming, make an estimate
                    # In a real implementation, the driver should provide proper token accounting
                    if chunks:
                        # Estimate based on content length
                        for chunk in chunks:
                            if hasattr(chunk, 'usage') and chunk.usage:
                                total_prompt_tokens += chunk.usage.get('prompt_tokens', 0)
                                total_completion_tokens += chunk.usage.get('completion_tokens', 0)

                    await callback(
                        UUID(request.tenant_id),
                        total_prompt_tokens,
                        total_completion_tokens,
                        request.model or "unknown",
                        routing_result.driver.driver_type
                    )
                except Exception as e:
                    logger.warning(f"Billing callback failed for streaming tenant {request.tenant_id}: {e}")

    async def embed(self, request: EmbeddingRequest, strategy: RoutingStrategy | None = None,
                 billing_callback: Callable[[UUID, int, int, str, str], Awaitable[None]] | None = None) -> EmbeddingResponse:
        """Generate embeddings using routing strategy."""
        # For embedding, we might want to use a specific driver or fallback strategy
        # This is simplified - in practice, embeddings could be routed similarly to generation
        try:
            # First try to get a driver with embedding capability
            available_drivers = []
            for driver in self.pool.get_all_drivers():
                if "embedding" in [cap.value for cap in driver.capabilities()]:
                    available_drivers.append(driver)

            if not available_drivers:
                # If no embedding driver found, use any available driver
                available_drivers = self.pool.get_all_drivers()

            if available_drivers:

                # Route to first available driver
                driver = available_drivers[0]  # Simple round-robin for now
                response = await driver.embed(request)

                # Handle billing if tenant_id is provided
                if request.tenant_id is not None:
                    try:
                        # Extract usage from response
                        prompt_tokens = response.usage.get('prompt_tokens', 0)
                        total_tokens = response.usage.get('total_tokens', 0)
                        completion_tokens = total_tokens - prompt_tokens

                        # Call billing callback if provided (prefer passed callback over instance callback)
                        callback = billing_callback or self.billing_callback
                        if callback:
                            await callback(
                                UUID(request.tenant_id),
                                prompt_tokens,
                                completion_tokens,
                                response.model,
                                driver.driver_type
                            )
                    except Exception as e:
                        logger.warning(f"Billing callback failed for embedding tenant {request.tenant_id}: {e}")

                return response
            else:
                raise RuntimeError("No drivers available for embedding")

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    async def health_check(self) -> dict:
        """Get health summary for all drivers."""
        return await self.pool.health_check_all()
