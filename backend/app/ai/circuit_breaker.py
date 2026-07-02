"""Circuit Breaker — prevents cascading failures in AI driver pool.

States:
    CLOSED → normal operation, requests pass through
    OPEN   → requests immediately fail without real call
    HALF_OPEN → limited test requests to check if service recovered

Based on the standard circuit breaker pattern.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("aether.ai.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5       # Consecutive failures to OPEN
    success_threshold: int = 2       # Successes in HALF_OPEN to CLOSE
    recovery_timeout: float = 30.0   # Seconds to wait before HALF_OPEN
    half_open_max_requests: int = 3  # Max requests allowed in HALF_OPEN


class CircuitBreaker:
    """Circuit breaker for a single AI driver.

    Usage:
        cb = CircuitBreaker("openai_driver")

        if not cb.allow_request():
            raise CircuitBreakerOpenError("Driver unavailable")

        try:
            result = await driver.generate(request)
            cb.on_success()
        except Exception:
            cb.on_failure()
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.monotonic()
        self._total_failures: int = 0
        self._total_successes: int = 0

    def allow_request(self) -> bool:
        """Check if a request should be allowed through.

        Returns True if circuit is CLOSED or HALF_OPEN with capacity.
        Returns False if circuit is OPEN or HALF_OPEN at capacity.
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            elapsed = time.monotonic() - self._last_state_change
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(
                    f"Circuit breaker {self.name}: OPEN → HALF_OPEN "
                    f"(elapsed={elapsed:.1f}s)"
                )
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Limit concurrent requests during recovery
            return True

        return False

    def on_success(self) -> None:
        """Record a successful request."""
        self._total_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    f"Circuit breaker {self.name}: HALF_OPEN → CLOSED "
                    f"({self._success_count} successes)"
                )
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success in CLOSED state
            self._failure_count = 0

    def on_failure(self) -> None:
        """Record a failed request."""
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN → back to OPEN
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                f"Circuit breaker {self.name}: HALF_OPEN → OPEN "
                f"(failure during recovery)"
            )
        elif (
            self.state == CircuitState.CLOSED
            and self._failure_count >= self.config.failure_threshold
        ):
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                f"Circuit breaker {self.name}: CLOSED → OPEN "
                f"({self._failure_count} failures, threshold={self.config.failure_threshold})"
            )

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        self._success_count = 0
        logger.info(f"Circuit breaker {self.name}: manually reset to CLOSED")

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self.state
        self.state = new_state
        self._last_state_change = time.monotonic()

        if new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

    # ── Metrics ──────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def metrics(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "last_failure_time": self._last_failure_time,
            "last_state_change": self._last_state_change,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a request is rejected because the circuit breaker is open."""
    def __init__(self, driver_name: str):
        self.driver_name = driver_name
        super().__init__(f"Circuit breaker open for driver: {driver_name}")
