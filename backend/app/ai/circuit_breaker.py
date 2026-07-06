"""Circuit breaker implementation for AI drivers."""

from __future__ import annotations

import asyncio
from enum import Enum
import time


class CircuitBreakerState(str, Enum):  # noqa: UP042
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # All requests fail immediately
    HALF_OPEN = "half_open"  # Test requests allowed


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: int = 30, half_open_max: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._request_count = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        return self._state

    def is_call_allowed(self) -> bool:
        """
        Check if a call is allowed based on current state.

        Returns:
            True if call is allowed, False if should be rejected.
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            # Check if timeout has passed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to half-open
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._request_count = 0
                    return True
            return False

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Allow limited requests
            return self._request_count < self.half_open_max

        return False

    def on_success(self):
        """Record a successful request."""
        # Since this is not async, we can't use the lock properly in sync context
        # But for now, just do the basic logic
        if self._state == CircuitBreakerState.HALF_OPEN:
            # If we're in half-open state and this was a success,
            # transition back to closed state
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._request_count = 0
        elif self._state == CircuitBreakerState.OPEN:
            # If we're in open state, transition back to closed on success
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._request_count = 0

    def on_failure(self):
        """Record a failed request."""
        # Since this is not async, we can't use the lock properly in sync context
        # But for now, just do the basic logic
        if self._state == CircuitBreakerState.HALF_OPEN:
            # In half-open state, we've had a failure, so go back to open
            self._state = CircuitBreakerState.OPEN
            self._last_failure_time = time.time()
            self._request_count = 0
        else:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                self._last_failure_time = time.time()
            else:
                self._state = CircuitBreakerState.CLOSED

    def reset(self):
        """Reset the circuit breaker to initial state."""
        # Since this is not async, we can't use the lock properly in sync context
        # But for now, just do the basic logic
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._request_count = 0

    def __str__(self):
        return f"CircuitBreaker(state={self._state.value}, failures={self._failure_count})"
