"""Aether Plugin SDK — business logic as pluggable modules.

Architecture:
    BaseServicePlugin (ABC) → PromptDrivenPlugin | Custom Python Plugin
    PluginRegistry → PluginLoader → Builtin Plugins

Usage:
    from app.plugins import get_registry, PromptDrivenPlugin, PluginManifest

    registry = get_registry()
    await registry.activate("faq")
"""

from app.plugins.base import (
    Action,
    BaseServicePlugin,
    Capability,
    Intent,
    PluginContext,
    PluginHealth,
    PluginManifest,
    PluginPermission,
    PluginResult,
    PluginStatus,
    ToolDefinition,
)
from app.plugins.loader import PluginLoader
from app.plugins.prompt_driver import PromptDrivenPlugin
from app.plugins.registry import (
    PluginNotFoundError,
    PluginRegistry,
    PluginValidationError,
    get_registry,
    reset_registry,
)

__all__ = [
    # Base classes
    "BaseServicePlugin",
    "PromptDrivenPlugin",
    # Data classes
    "Capability",
    "Intent",
    "PluginResult",
    "Action",
    "PluginHealth",
    "PluginManifest",
    "PluginPermission",
    "PluginStatus",
    "PluginContext",
    "ToolDefinition",
    # Registry
    "PluginRegistry",
    "get_registry",
    "reset_registry",
    "PluginNotFoundError",
    "PluginValidationError",
    # Loader
    "PluginLoader",
]
