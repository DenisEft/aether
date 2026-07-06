"""Inference pool for managing AI drivers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import random
import time

from .drivers.base import (
    BaseDriver,
    DriverHealth,
    InferenceRequest,
    InferenceResponse,
)

logger = logging.getLogger("aether.ai.inference_pool")


@dataclass
class DriverEntry:
    """Wrapper around a driver with routing metadata."""

    driver: BaseDriver
    priority: int = 0
    cost_per_1k_tokens: float = 0.0
    max_concurrent: int = 10
    _current_requests: int = 0
    _consecutive_failures: int = 0
    _last_health: DriverHealth | None = None
    _last_health_at: float = 0.0

    @property
    def is_healthy(self) -> bool:
        if self._consecutive_failures >= 3:
            return False
        return not (self._last_health and self._last_health.status == "error")

    @property
    def current_load(self) -> float:
        return self._current_requests / max(self.max_concurrent, 1)

    def mark_request_start(self):
        self._current_requests += 1

    def mark_request_done(self, success: bool):
        self._current_requests = max(0, self._current_requests - 1)
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1


class InferencePool:
    """Pool of AI drivers with smart routing."""

    def __init__(self, health_check_interval: float = 30.0):
        self._drivers: dict[str, DriverEntry] = {}
        self._health_check_interval = health_check_interval
        self._health_task: asyncio.Task | None = None
        self._round_robin_idx = 0
        self._lock = asyncio.Lock()

    def register_driver(
        self,
        driver: BaseDriver,
        priority: int = 0,
        cost_per_1k: float = 0.0,
        max_concurrent: int = 10,
    ):
        """Register a driver in the pool."""
        key = f"{driver.driver_type}:{driver.model_id}"
        self._drivers[key] = DriverEntry(
            driver=driver,
            priority=priority,
            cost_per_1k_tokens=cost_per_1k,
            max_concurrent=max_concurrent,
        )
        logger.info(f"Registered driver: {key} (priority={priority})")

    def unregister_driver(self, driver_type: str, model_id: str):
        """Remove a driver from the pool."""
        key = f"{driver_type}:{model_id}"
        self._drivers.pop(key, None)

    def get_driver(self, driver_type: str, model_id: str) -> BaseDriver | None:
        """Get a specific driver by type and model."""
        key = f"{driver_type}:{model_id}"
        entry = self._drivers.get(key)
        return entry.driver if entry else None

    async def initialize_all(self):
        """Initialize all registered drivers."""
        tasks = []
        for key, entry in self._drivers.items():
            tasks.append(self._init_one(key, entry))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(self._drivers.keys(), results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"Failed to init {key}: {result}")

    async def _init_one(self, key: str, entry: DriverEntry):
        try:
            await entry.driver.initialize()
        except Exception as e:
            logger.error(f"Init failed for {key}: {e}")
            raise

    async def start_health_checks(self):
        """Start periodic health checks."""
        if self._health_task:
            return
        self._health_task = asyncio.create_task(self._health_loop())

    async def _health_loop(self):
        while True:
            await asyncio.sleep(self._health_check_interval)
            await self._check_all()

    async def _check_all(self):
        """Check health of all drivers."""
        tasks = []
        for key, entry in self._drivers.items():
            tasks.append(self._check_one(key, entry))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_one(self, key: str, entry: DriverEntry):
        try:
            health = await entry.driver.health_check()
            entry._last_health = health
            entry._last_health_at = time.time()
            if health.status == "error":
                entry._consecutive_failures += 1
                logger.warning(f"Driver {key} unhealthy: {health.message}")
            else:
                entry._consecutive_failures = 0
        except Exception as e:
            entry._consecutive_failures += 1
            logger.error(f"Health check failed for {key}: {e}")

    def get_all_drivers(self) -> list[BaseDriver]:
        """Get list of all registered drivers."""
        return [entry.driver for entry in self._drivers.values()]

    def get_driver_for_model(self, model_id: str) -> BaseDriver | None:
        """Get the first driver that supports the given model."""
        for _key, entry in self._drivers.items():
            try:
                if model_id in entry.driver.get_available_models():
                    return entry.driver
            except Exception:
                # If we can't check, assume it's available or skip it
                pass
        return None

    async def infer(
        self,
        request: InferenceRequest,
        strategy: str = "least_latency",
        timeout: float = 30.0,
        retries: int = 1,
    ) -> InferenceResponse:
        """Run inference through the best available driver."""
        last_error = None

        # First, check if we have a specific driver for this model
        driver = self.get_driver_for_model(request.model)
        if driver:
            return await self._infer_with_driver(driver, request, timeout, retries)

        # If no driver found, use fallback to select based on strategy
        selected = self._select_driver(strategy)
        if not selected:
            raise RuntimeError("No healthy drivers available")

        key, entry = selected
        entry.mark_request_start()

        try:
            response = await asyncio.wait_for(entry.driver.generate(request), timeout=timeout)
            entry.mark_request_done(success=True)
            return response
        except TimeoutError:
            entry.mark_request_done(success=False)
            last_error = f"Timeout after {timeout}s"
            logger.warning(f"Driver {key} timed out")
        except Exception as e:
            entry.mark_request_done(success=False)
            last_error = str(e)
            logger.error(f"Driver {key} failed: {e}")
            if retries > 0:
                await asyncio.sleep(0.5)
                return await self.infer(request, strategy, timeout, retries - 1)

        raise RuntimeError(f"All inference attempts failed: {last_error}")

    async def _infer_with_driver(
        self, driver: BaseDriver, request: InferenceRequest, timeout: float, retries: int
    ) -> InferenceResponse:
        """Run inference with a specific driver."""
        last_error = None

        for attempt in range(retries + 1):
            try:
                response = await asyncio.wait_for(driver.generate(request), timeout=timeout)
                return response
            except TimeoutError:
                last_error = f"Timeout after {timeout}s"
                logger.warning(f"Driver {driver.driver_type} timed out")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Driver {driver.driver_type} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"All inference attempts failed: {last_error}")

    def _select_driver(
        self,
        strategy: str = "least_latency",
        capability: str | None = None,
        exclude_unhealthy: bool = True,
    ) -> tuple[str, DriverEntry] | None:
        """Select the best driver based on strategy."""

        candidates = []
        for key, entry in self._drivers.items():
            if exclude_unhealthy and not entry.is_healthy:
                continue
            if capability and capability not in [c.value for c in entry.driver.capabilities()]:
                continue
            if entry.current_load >= 1.0:
                continue  # At capacity
            candidates.append((key, entry))

        if not candidates:
            return None

        if strategy == "random":
            return random.choice(candidates)

        if strategy == "priority":
            candidates.sort(key=lambda x: (-x[1].priority, x[1].current_load))
            return candidates[0]

        if strategy == "round_robin":

            async def _rr():
                async with self._lock:
                    self._round_robin_idx = (self._round_robin_idx + 1) % len(candidates)
                    return candidates[self._round_robin_idx]

            # Simple non-async-safe version for now
            self._round_robin_idx = (self._round_robin_idx + 1) % len(candidates)
            return candidates[self._round_robin_idx]

        if strategy == "cost_optimized":
            candidates.sort(key=lambda x: x[1].cost_per_1k_tokens)
            return candidates[0]

        if strategy == "least_loaded":
            candidates.sort(key=lambda x: x[1].current_load)
            return candidates[0]

        if strategy == "least_latency":
            candidates.sort(
                key=lambda x: (x[1]._last_health.latency_ms if x[1]._last_health else 999999)
            )
            return candidates[0]

        return candidates[0]

    async def shutdown_all(self):
        """Shutdown all drivers."""
        if self._health_task:
            self._health_task.cancel()
        for key, entry in self._drivers.items():
            try:
                await entry.driver.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down {key}: {e}")

    async def health_check_all(self) -> dict:
        """Check health of all drivers."""
        result = {}
        tasks = []
        for key, entry in self._drivers.items():
            tasks.append(self._check_one(key, entry))
        await asyncio.gather(*tasks, return_exceptions=True)
        for key, entry in self._drivers.items():
            result[key] = entry._last_health
        return result

    def get_health_summary(self) -> dict:
        """Get health summary for all drivers."""
        summary = {}
        for key, entry in self._drivers.items():
            health = entry._last_health
            summary[key] = {
                "healthy": entry.is_healthy,
                "status": health.status if health else "unknown",
                "latency_ms": health.latency_ms if health else None,
                "load": f"{entry.current_load:.1%}",
                "requests": entry.driver.get_metrics().total_requests,
                "success_rate": f"{entry.driver.get_metrics().success_rate:.1%}",
            }
        return summary


# Global pool instance — created lazily
pool: InferencePool | None = None


def get_pool() -> InferencePool:
    """Get or create the global inference pool."""
    global pool
    if pool is None:
        pool = InferencePool()
    return pool
