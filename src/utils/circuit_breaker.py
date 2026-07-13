"""Circuit Breaker pattern implementation for external API resilience.

Provides protection against cascading failures by temporarily blocking
requests to failing services.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit is open and requests are blocked."""

    def __init__(self, name: str, reset_timeout: float):
        self.name = name
        self.reset_timeout = reset_timeout
        super().__init__(f"Circuit breaker '{name}' is open. Will retry after {reset_timeout:.1f}s")


class CircuitBreaker:
    """Circuit breaker for protecting external API calls.

    States:
        - CLOSED: Normal operation, all requests pass through
        - OPEN: Failure threshold exceeded, requests blocked
        - HALF_OPEN: Testing if service recovered

    Args:
        name: Identifier for logging purposes
        failure_threshold: Number of failures before opening circuit
        reset_timeout: Seconds to wait before attempting recovery
        success_threshold: Successful calls needed to close from half-open

    Example:
        >>> breaker = CircuitBreaker("api", failure_threshold=3, reset_timeout=30)
        >>> async with breaker:
        ...     response = await api_client.request()
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._last_state_change: float = time.monotonic()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, updating if reset timeout expired."""
        if self._state == CircuitState.OPEN and self._should_attempt_reset():
            self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.reset_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0

        logger.info(f"Circuit breaker '{self.name}': {old_state.value} -> {new_state.value}")

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    f"Circuit breaker '{self.name}' recovered after "
                    f"{self._success_count} successful calls"
                )
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self, error: Exception | None = None) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        error_msg = str(error) if error else "unknown"
        logger.warning(
            f"Circuit breaker '{self.name}' recorded failure "
            f"({self._failure_count}/{self.failure_threshold}): {error_msg}"
        )

        if self._state == CircuitState.HALF_OPEN or (
            self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold
        ):
            self._transition_to(CircuitState.OPEN)

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        return self.state != CircuitState.OPEN

    def __enter__(self) -> CircuitBreaker:
        """Context manager entry - raises if circuit is open."""
        if not self.can_execute():
            raise CircuitBreakerError(self.name, self.reset_timeout)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - records success or failure."""
        if exc_type is None:
            self.record_success()
        else:
            # Convert BaseException to Exception if needed
            error = exc_val if isinstance(exc_val, Exception) else None
            self.record_failure(error)

    async def __aenter__(self) -> CircuitBreaker:
        """Async context manager entry."""
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._transition_to(CircuitState.CLOSED)
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Example:
        >>> registry = CircuitBreakerRegistry()
        >>> registry.create("api", failure_threshold=3)
        >>> breaker = registry.get("api")
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def create(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> CircuitBreaker:
        """Create and register a new circuit breaker."""
        if name in self._breakers:
            raise ValueError(f"Circuit breaker '{name}' already exists")

        breaker = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            success_threshold=success_threshold,
        )
        self._breakers[name] = breaker
        return breaker

    def get(self, name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name in self._breakers:
            return self._breakers[name]
        return self.create(
            name=name,
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            success_threshold=success_threshold,
        )

    def get_all_stats(self) -> list[dict]:
        """Get statistics for all circuit breakers."""
        return [breaker.get_stats() for breaker in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


def with_circuit_breaker(
    breaker: CircuitBreaker,
) -> Callable:
    """Decorator to wrap a function with circuit breaker protection.

    Example:
        >>> breaker = CircuitBreaker("api")
        >>> @with_circuit_breaker(breaker)
        ... async def fetch_data():
        ...     return await api.request()
    """

    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not breaker.can_execute():
                raise CircuitBreakerError(breaker.name, breaker.reset_timeout)
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not breaker.can_execute():
                raise CircuitBreakerError(breaker.name, breaker.reset_timeout)
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(e)
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
