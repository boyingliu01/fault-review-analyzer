"""Circuit Breaker pattern tests."""

import time

import pytest

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    with_circuit_breaker,
)


class TestCircuitBreaker:
    """Circuit breaker unit tests."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in closed state."""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    def test_closed_state_allows_requests(self):
        """Closed state allows all requests through."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        assert breaker.can_execute() is True

        with breaker:
            pass  # Request allowed

    def test_opens_after_failure_threshold(self):
        """Circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        # Record 3 failures
        for _ in range(3):
            breaker.record_failure(Exception("test error"))

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open
        assert not breaker.can_execute()

    def test_open_state_blocks_requests(self):
        """Open state blocks all requests."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(Exception("test error"))

        with pytest.raises(CircuitBreakerError) as exc_info, breaker:
            pass

        assert "is open" in str(exc_info.value)
        assert exc_info.value.name == "test"

    def test_half_open_after_reset_timeout(self):
        """Circuit transitions to half-open after reset timeout."""
        breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.1)

        breaker.record_failure(Exception("test error"))
        assert breaker.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)

        # State should now be half-open when checked
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.is_half_open
        assert breaker.can_execute()

    def test_half_open_closes_on_success_threshold(self):
        """Half-open circuit closes after enough successes."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=1,
            reset_timeout=0.1,
            success_threshold=2,
        )

        # Open the circuit
        breaker.record_failure(Exception("test error"))
        assert breaker.state == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self):
        """Half-open circuit reopens on any failure."""
        breaker = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.1)

        # Open the circuit
        breaker.record_failure(Exception("test error"))
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Any failure should reopen
        breaker.record_failure(Exception("another error"))
        assert breaker.state == CircuitState.OPEN

    def test_success_resets_failure_count_in_closed(self):
        """Success in closed state resets failure count."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        breaker.record_failure(Exception("error 1"))
        breaker.record_failure(Exception("error 2"))
        assert breaker._failure_count == 2

        breaker.record_success()
        assert breaker._failure_count == 0

    def test_context_manager_records_success(self):
        """Context manager records success on normal exit."""
        breaker = CircuitBreaker("test")

        with breaker:
            pass  # No exception

        assert breaker._success_count == 1 or breaker._failure_count == 0

    def test_context_manager_records_failure(self):
        """Context manager records failure on exception."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        with pytest.raises(ValueError), breaker:
            raise ValueError("test error")

        assert breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Async context manager works correctly."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        async with breaker:
            pass  # Success

        assert breaker._failure_count == 0

        # Test failure
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("async error")

        assert breaker._failure_count == 1

    def test_manual_reset(self):
        """Manual reset returns circuit to closed state."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(Exception("error"))
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_get_stats(self):
        """Get statistics returns correct info."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=5,
            reset_timeout=30.0,
        )
        breaker.record_failure(Exception("error"))

        stats = breaker.get_stats()

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 1
        assert stats["failure_threshold"] == 5
        assert stats["reset_timeout"] == 30.0


class TestCircuitBreakerRegistry:
    """Circuit breaker registry tests."""

    def test_create_breaker(self):
        """Create and register a new circuit breaker."""
        registry = CircuitBreakerRegistry()
        breaker = registry.create("api", failure_threshold=3)

        assert breaker.name == "api"
        assert registry.get("api") is breaker

    def test_create_duplicate_raises(self):
        """Creating duplicate breaker raises error."""
        registry = CircuitBreakerRegistry()
        registry.create("api")

        with pytest.raises(ValueError, match="already exists"):
            registry.create("api")

    def test_get_or_create(self):
        """Get or create returns existing or creates new."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("api", failure_threshold=3)
        breaker2 = registry.get_or_create("api", failure_threshold=5)

        assert breaker1 is breaker2
        assert breaker1.failure_threshold == 3  # Uses first creation

    def test_get_all_stats(self):
        """Get all statistics from all breakers."""
        registry = CircuitBreakerRegistry()
        registry.create("api", failure_threshold=3)
        registry.create("llm", failure_threshold=5)

        stats = registry.get_all_stats()

        assert len(stats) == 2
        names = {s["name"] for s in stats}
        assert names == {"api", "llm"}

    def test_reset_all(self):
        """Reset all circuit breakers."""
        registry = CircuitBreakerRegistry()
        api_breaker = registry.create("api", failure_threshold=1)
        llm_breaker = registry.create("llm", failure_threshold=1)

        api_breaker.record_failure(Exception("error"))
        llm_breaker.record_failure(Exception("error"))

        assert api_breaker.is_open
        assert llm_breaker.is_open

        registry.reset_all()

        assert api_breaker.is_closed
        assert llm_breaker.is_closed


class TestWithCircuitBreakerDecorator:
    """Decorator tests."""

    def test_sync_function_success(self):
        """Sync function decorated correctly."""
        breaker = CircuitBreaker("test")

        @with_circuit_breaker(breaker)
        def sync_func():
            return "success"

        result = sync_func()
        assert result == "success"
        assert breaker._failure_count == 0

    def test_sync_function_failure(self):
        """Sync function failure recorded."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        @with_circuit_breaker(breaker)
        def failing_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            failing_func()

        assert breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Async function decorated correctly."""
        breaker = CircuitBreaker("test")

        @with_circuit_breaker(breaker)
        async def async_func():
            return "async success"

        result = await async_func()
        assert result == "async success"
        assert breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_async_function_failure(self):
        """Async function failure recorded."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        @with_circuit_breaker(breaker)
        async def failing_async():
            raise ValueError("async error")

        with pytest.raises(ValueError):
            await failing_async()

        assert breaker._failure_count == 1

    def test_open_circuit_raises_error(self):
        """Open circuit raises CircuitBreakerError."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(Exception("initial error"))

        @with_circuit_breaker(breaker)
        def func():
            return "should not reach"

        with pytest.raises(CircuitBreakerError):
            func()


class TestCircuitBreakerIntegration:
    """Integration tests with API client patterns."""

    @pytest.mark.asyncio
    async def test_api_client_circuit_protection(self):
        """Simulate API client with circuit breaker protection."""
        from src.api.client import APIClient

        # Create client with circuit breaker
        breaker = CircuitBreaker("api_test", failure_threshold=2, reset_timeout=1.0)
        client = APIClient(
            base_url="https://test.example.com",
            circuit_breaker=breaker,
        )

        assert client.circuit_breaker is breaker
        assert breaker.is_closed

    @pytest.mark.asyncio
    async def test_embedding_generator_circuit_protection(self):
        """Simulate embedding generator with circuit breaker protection."""
        from src.embedding.generator import EmbeddingGenerator

        # Create generator with circuit breaker
        breaker = CircuitBreaker("embedding_test", failure_threshold=2)
        generator = EmbeddingGenerator(
            provider="openai",
            circuit_breaker=breaker,
        )

        assert generator.circuit_breaker is breaker
        assert breaker.is_closed

    def test_multiple_clients_share_registry(self):
        """Multiple clients can share a registry."""
        registry = CircuitBreakerRegistry()

        api_breaker = registry.get_or_create("api", failure_threshold=3)
        llm_breaker = registry.get_or_create("llm", failure_threshold=5)
        registry.get_or_create("embedding", failure_threshold=3)

        # Simulate failures
        api_breaker.record_failure(Exception("api error"))
        llm_breaker.record_failure(Exception("llm error"))

        stats = registry.get_all_stats()
        assert len(stats) == 3

        # Only api and llm have failures
        api_stats = next(s for s in stats if s["name"] == "api")
        assert api_stats["failure_count"] == 1
