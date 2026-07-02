"""Test suite for AI Smart Router implementation."""

import asyncio
import unittest

from app.ai import (
    BaseDriver,
    DriverCapability,
    DriverHealth,
    EmbeddingRequest,
    EmbeddingResponse,
    InferenceRequest,
    InferenceResponse,
)
from app.ai.circuit_breaker import CircuitBreaker
from app.ai.inference_pool import InferencePool
from app.ai.manager import AIManager
from app.ai.model_registry import ModelInfo, ModelRegistry
from app.ai.smart_router import RoutingStrategy, SmartRouter


class MockDriver(BaseDriver):
    """Mock driver for testing."""

    def __init__(self, model_id: str, driver_type: str = "test", **config):
        super().__init__(model_id, **config)
        self._driver_type = driver_type
        self._capabilities = [DriverCapability.CHAT]

    @property
    def driver_type(self) -> str:
        return self._driver_type

    def capabilities(self) -> list[DriverCapability]:
        return self._capabilities

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> DriverHealth:
        return DriverHealth(status="healthy", latency_ms=50)

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            model=self.model_id,
            driver_type=self.driver_type,
            content="Mock response",
            latency_ms=50,
        )

    async def generate_stream(self, request: InferenceRequest):
        yield "Mock response"

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3]], model=self.model_id, driver_type=self.driver_type
        )

    async def get_available_models(self) -> list[str]:
        return [self.model_id]

    async def shutdown(self) -> None:
        pass


class TestSmartRouter(unittest.TestCase):
    """Test SmartRouter functionality."""

    def setUp(self):
        self.pool = InferencePool()
        self.registry = ModelRegistry()
        self.router = SmartRouter(self.pool, self.registry)

        # Add mock drivers to pool
        driver1 = MockDriver("model1", "local")
        driver2 = MockDriver("model2", "openai")

        self.pool.register_driver(driver1, priority=1)
        self.pool.register_driver(driver2, priority=1)

        # Add model info to registry
        model1_info = ModelInfo(
            model_id="model1",
            driver_type="local",
            display_name="Local Model",
            context_length=1000,
            cost_per_1k_tokens_input=0.0,
            cost_per_1k_tokens_output=0.0,
            capabilities=["chat"],
            languages=["en"],
            is_local=True,
            is_active=True,
            quality_score=0.9,
        )

        model2_info = ModelInfo(
            model_id="model2",
            driver_type="openai",
            display_name="OpenAI Model",
            context_length=1000,
            cost_per_1k_tokens_input=0.015,
            cost_per_1k_tokens_output=0.06,
            capabilities=["chat"],
            languages=["en"],
            is_local=False,
            is_active=True,
            quality_score=0.8,
        )

        self.registry.register_model(model1_info)
        self.registry.register_model(model2_info)

    def test_router_initialization(self):
        """Test SmartRouter initialization."""
        self.assertIsNotNone(self.router.pool)
        self.assertIsNotNone(self.router.registry)

    def test_routing_strategies(self):
        """Test different routing strategies."""
        request = InferenceRequest(messages=[{"role": "user", "content": "Hello"}], model="model1")

        # Test hybrid strategy (default)
        result = asyncio.run(self.router.route(request, RoutingStrategy.HYBRID))
        self.assertIsNotNone(result.driver)
        self.assertIsInstance(result.score, float)
        self.assertEqual(result.strategy, RoutingStrategy.HYBRID)

        # Test cost optimal strategy
        result = asyncio.run(self.router.route(request, RoutingStrategy.COST_OPTIMAL))
        self.assertIsNotNone(result.driver)

    def test_model_scoring(self):
        """Test model scoring functionality."""
        request = InferenceRequest(messages=[{"role": "user", "content": "Hello"}], model="model1")

        # Test scoring
        score = asyncio.run(
            self.router._score_driver(
                self.pool.get_driver("local", "model1"), request, RoutingStrategy.COST_OPTIMAL
            )
        )
        self.assertIsInstance(score, float)

    def test_fallback_chain(self):
        """Test fallback chain functionality."""
        fallback_chain = asyncio.run(self.router._get_fallback_chain("model1"))
        self.assertIsInstance(fallback_chain, list)


class TestInferencePool(unittest.TestCase):
    """Test InferencePool functionality."""

    def setUp(self):
        self.pool = InferencePool()

    def test_pool_initialization(self):
        """Test pool initialization."""
        self.assertIsNotNone(self.pool._drivers)
        self.assertEqual(self.pool._health_check_interval, 30.0)

    def test_driver_registration(self):
        """Test driver registration."""
        driver = MockDriver("test_model", "test_driver")
        self.pool.register_driver(driver, priority=1, cost_per_1k=0.01)

        self.assertIn("test_driver:test_model", self.pool._drivers)
        entry = self.pool._drivers["test_driver:test_model"]
        self.assertEqual(entry.driver, driver)
        self.assertEqual(entry.priority, 1)
        self.assertEqual(entry.cost_per_1k_tokens, 0.01)


class TestModelRegistry(unittest.TestCase):
    """Test ModelRegistry functionality."""

    def setUp(self):
        self.registry = ModelRegistry()

    def test_model_registration(self):
        """Test model registration."""
        model_info = ModelInfo(
            model_id="test_model",
            driver_type="test_driver",
            display_name="Test Model",
            context_length=1000,
            cost_per_1k_tokens_input=0.015,
            cost_per_1k_tokens_output=0.06,
            capabilities=["chat"],
            languages=["en"],
            is_local=True,
            is_active=True,
            quality_score=0.9,
        )

        self.registry.register_model(model_info)
        retrieved = self.registry.get_model("test_model")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.model_id, "test_model")


class TestAIManager(unittest.TestCase):
    """Test AIManager functionality."""

    def setUp(self):
        self.pool = InferencePool()
        self.registry = ModelRegistry()
        self.router = SmartRouter(self.pool, self.registry)
        self.manager = AIManager(
            smart_router=self.router, inference_pool=self.pool, model_registry=self.registry
        )

    def test_manager_initialization(self):
        """Test manager initialization."""
        self.assertIsNotNone(self.manager.smart_router)
        self.assertIsNotNone(self.manager.inference_pool)
        self.assertIsNotNone(self.manager.model_registry)


class TestCircuitBreaker(unittest.TestCase):
    """Test CircuitBreaker functionality."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        breaker = CircuitBreaker()
        self.assertEqual(breaker.state, "closed")
        self.assertEqual(breaker.failure_threshold, 5)

    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        breaker = CircuitBreaker()

        # Should be allowed initially
        self.assertTrue(breaker.is_call_allowed())

        # After failures, should go to OPEN state
        for _ in range(5):
            breaker.on_failure()

        self.assertEqual(breaker.state, "open")
        self.assertFalse(breaker.is_call_allowed())

        # Reset should bring it back to closed
        breaker.reset()
        self.assertEqual(breaker.state, "closed")
        self.assertTrue(breaker.is_call_allowed())


if __name__ == "__main__":
    unittest.main()
