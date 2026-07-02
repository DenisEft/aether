"""Base driver ABC and data types for AI inference."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional

__all__ = ["BaseDriver", "DriverCapability", "DriverHealth", "DriverMetrics", "InferenceRequest", "InferenceResponse"]

logger = logging.getLogger("aether.ai.drivers")


class DriverCapability(str, Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE = "image"
    AUDIO = "audio"


@dataclass
class DriverHealth:
    status: str  # "healthy", "degraded", "error", "unknown"
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class InferenceRequest:
    messages: list[dict]  # [{"role": "user"/"assistant"/"system", "content": "..."}]
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stop_sequences: list[str] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class InferenceResponse:
    model: str
    driver_type: str
    content: str
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)  # {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DriverMetrics:
    model: str
    total_requests: int = 0
    total_failed: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    cost_usd: float = 0.0
    last_used_at: float | None = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return 1.0 - (self.total_failed / self.total_requests)


class BaseDriver(ABC):
    """Abstract base for all AI inference drivers."""

    def __init__(self, model_id: str, **config):
        self.model_id = model_id
        self.config = config
        self._metrics = DriverMetrics(model=model_id)
        self._last_health = DriverHealth(status="unknown")

    @property
    @abstractmethod
    def driver_type(self) -> str:
        """Unique driver type identifier: 'openai', 'anthropic', 'local', etc."""
        ...

    @abstractmethod
    def capabilities(self) -> list[DriverCapability]:
        """List of capabilities this driver supports."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the driver (setup HTTP client, warmup, etc.)."""
        ...

    @abstractmethod
    async def health_check(self) -> DriverHealth:
        """Check driver health. Returns DriverHealth with status and latency."""
        ...

    @abstractmethod
    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Run a single inference request. Non-streaming."""
        ...

    async def infer_stream(self, request: InferenceRequest) -> AsyncGenerator[str, None]:
        """Run a streaming inference request. Default: calls infer() and yields once."""
        response = await self.infer(request)
        yield response.content

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup resources."""
        ...

    def get_metrics(self) -> DriverMetrics:
        """Return current metrics snapshot."""
        return self._metrics

    def record_failure(self, error: str):
        """Record a failed request."""
        self._metrics.total_requests += 1
        self._metrics.total_failed += 1
        logger.warning(f"Driver {self.driver_type}/{self.model_id} failed: {error}")

    def record_success(self, latency_ms: float, tokens: int = 0):
        """Record a successful request."""
        n = self._metrics.total_requests
        self._metrics.total_requests = n + 1
        self._metrics.total_tokens += tokens
        # Rolling average
        self._metrics.avg_latency_ms = (
            (self._metrics.avg_latency_ms * n + latency_ms) / (n + 1)
        )
        from time import time
        self._metrics.last_used_at = time()

# Export router types when available
try:
    from .router import pool, InferencePool, RoutingStrategy
    __all__.extend(["pool", "InferencePool", "RoutingStrategy"])
except ImportError:
    pass

# Export manager
try:
    from .manager import AIManager, ai_manager
    __all__.extend(["AIManager", "ai_manager"])
except ImportError:
    pass

# Export drivers
try:
    from .drivers import DRIVER_REGISTRY, get_driver, OpenAIDriver, AnthropicDriver, LocalDriver
    __all__.extend(["DRIVER_REGISTRY", "get_driver", "OpenAIDriver", "AnthropicDriver", "LocalDriver"])
except ImportError:
    pass
