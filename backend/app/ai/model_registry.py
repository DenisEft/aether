"""Model registry for AI models and their configurations."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .drivers.base import BaseDriver

logger = logging.getLogger("aether.ai.model_registry")


@dataclass
class ModelInfo:
    """Information about an AI model."""
    model_id: str
    driver_type: str
    display_name: str
    context_length: int
    cost_per_1k_tokens_input: float = 0.0
    cost_per_1k_tokens_output: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    is_local: bool = False
    is_active: bool = True
    min_vram_mb: int = 0
    recommended_for: list[str] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0 to 1.0 scale


class ModelRegistry:
    """Registry for AI models with their configurations."""

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._driver_models: Dict[str, List[str]] = {}  # driver_type -> [model_id]
        self._tenant_overrides: Dict[str, Dict[str, str]] = {}  # tenant_id -> {task: model_id}

    def register_model(self, model_info: ModelInfo):
        """Register a new AI model."""
        self._models[model_info.model_id] = model_info
        if model_info.driver_type not in self._driver_models:
            self._driver_models[model_info.driver_type] = []
        self._driver_models[model_info.driver_type].append(model_info.model_id)
        logger.info(f"Registered model: {model_info.model_id} for driver {model_info.driver_type}")

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model information by ID."""
        return self._models.get(model_id)

    def get_available_models(self, driver_type: Optional[str] = None) -> List[ModelInfo]:
        """Get all available models, optionally filtered by driver type."""
        if driver_type:
            model_ids = self._driver_models.get(driver_type, [])
            return [self._models[mid] for mid in model_ids if mid in self._models]
        return list(self._models.values())

    def get_model_for_task(self, task_type: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """Get preferred model for a specific task type."""
        # First check tenant overrides
        if tenant_id and tenant_id in self._tenant_overrides:
            override = self._tenant_overrides[tenant_id]
            if task_type in override:
                return override[task_type]
        
        # Return default model for task type
        # This would be more sophisticated in a real system
        return None

    def set_tenant_override(self, tenant_id: str, task_type: str, model_id: str):
        """Set a tenant-specific override for a task type."""
        if tenant_id not in self._tenant_overrides:
            self._tenant_overrides[tenant_id] = {}
        self._tenant_overrides[tenant_id][task_type] = model_id
        logger.info(f"Set tenant override: {tenant_id} -> {task_type} = {model_id}")

    def get_tenant_overrides(self, tenant_id: str) -> Dict[str, str]:
        """Get all tenant overrides."""
        return self._tenant_overrides.get(tenant_id, {})