"""Main AI module initializer for Aether."""

from .context_manager import ContextManager
from .embedding_service import EmbeddingService
from .inference_pool import InferencePool
from .manager import AIManager
from .model_registry import ModelRegistry
from .smart_router import SmartRouter

# Initialize global instances
pool = InferencePool()
registry = ModelRegistry()
smart_router = SmartRouter(pool, registry)
embedding_service = EmbeddingService(pool)
context_manager = ContextManager(smart_router, registry)

# Global AI manager instance
ai_manager = AIManager(smart_router=smart_router, inference_pool=pool, model_registry=registry)

__all__ = [
    "pool",
    "registry",
    "smart_router",
    "embedding_service",
    "context_manager",
    "ai_manager",
]
