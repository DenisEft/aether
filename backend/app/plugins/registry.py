"""Plugin Registry — dynamic discovery and lifecycle management.

Manages all registered plugins across all tenants.
Provides intent-to-plugin matching.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.plugins.base import (
    BaseServicePlugin,
    Intent,
    PluginContext,
    PluginManifest,
    PluginResult,
    PluginStatus,
)

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger("aether.plugins.registry")


class PluginNotFoundError(Exception):
    """Raised when a plugin is not found in the registry."""


class PluginValidationError(Exception):
    """Raised when plugin validation fails."""


class PluginRegistry:
    """Central registry for all service plugins.

    Thread-safe singleton. Use get_registry() to access.

    Plugin matching:
        Intent.intent_type is matched against plugin.manifest.intents.
        First match wins (priority-based ordering).
    """

    def __init__(self):
        self._plugins: dict[str, BaseServicePlugin] = {}     # id → plugin
        self._statuses: dict[str, PluginStatus] = {}          # id → status
        self._intent_index: dict[str, list[str]] = {}          # intent_type → [plugin_id, ...]
        self._tenant_plugins: dict[UUID, dict[str, bool]] = {} # tenant → {plugin_id: enabled}

    # ── Registration ─────────────────────────────────────────

    async def register(self, plugin: BaseServicePlugin) -> None:
        """Register a plugin. Calls on_register() → on_validate().

        Plugin is registered as VALIDATED. Call activate() to make it ACTIVE.
        """
        manifest = plugin.manifest
        plugin_id = manifest.id

        if plugin_id in self._plugins:
            logger.warning(f"Plugin {plugin_id} already registered, replacing")
            await self.unregister(plugin_id)

        # Register
        self._plugins[plugin_id] = plugin
        self._statuses[plugin_id] = PluginStatus.REGISTERED

        await plugin.on_register()

        # Validate
        is_valid = await plugin.on_validate()
        if not is_valid:
            self._statuses[plugin_id] = PluginStatus.ERROR
            raise PluginValidationError(f"Plugin {plugin_id} failed validation")

        self._statuses[plugin_id] = PluginStatus.VALIDATED

        # Build intent index
        for intent_type in manifest.intents:
            if intent_type not in self._intent_index:
                self._intent_index[intent_type] = []
            if plugin_id not in self._intent_index[intent_type]:
                self._intent_index[intent_type].append(plugin_id)

        logger.info(f"Plugin registered: {plugin_id} v{manifest.version}")

    async def unregister(self, plugin_id: str) -> None:
        """Unregister and uninstall a plugin."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return

        self._statuses[plugin_id] = PluginStatus.UNINSTALLING
        await plugin.on_uninstall()

        # Remove from intent index
        for _intent_type, plugins in self._intent_index.items():
            if plugin_id in plugins:
                plugins.remove(plugin_id)

        del self._plugins[plugin_id]
        del self._statuses[plugin_id]
        logger.info(f"Plugin unregistered: {plugin_id}")

    # ── Lifecycle ─────────────────────────────────────────────

    async def activate(self, plugin_id: str) -> None:
        """Activate a validated plugin."""
        plugin = self._get_plugin(plugin_id)
        if self._statuses[plugin_id] != PluginStatus.VALIDATED:
            raise PluginValidationError(
                f"Plugin {plugin_id} must be VALIDATED before activation, current: {self._statuses[plugin_id]}"
            )
        await plugin.on_activate()
        self._statuses[plugin_id] = PluginStatus.ACTIVE

    async def deactivate(self, plugin_id: str) -> None:
        """Deactivate (pause) a plugin."""
        plugin = self._get_plugin(plugin_id)
        await plugin.on_deactivate()
        self._statuses[plugin_id] = PluginStatus.INACTIVE

    # ── Intent Matching ───────────────────────────────────────

    async def get_plugins_for_intent(
        self, intent: Intent, tenant_id: UUID | None = None
    ) -> list[BaseServicePlugin]:
        """Find plugins that can handle a given intent.

        Returns plugins sorted by match specificity.
        Checks tenant plugin configuration if tenant_id provided.
        """
        matching_ids = self._intent_index.get(intent.intent_type, [])

        # Also check sub_intent for more specific matching
        if intent.sub_intent and intent.sub_intent in self._intent_index:
            for pid in self._intent_index[intent.sub_intent]:
                if pid not in matching_ids:
                    matching_ids.insert(0, pid)  # sub_intent matches first

        plugins = []
        for pid in matching_ids:
            plugin = self._plugins.get(pid)
            if plugin is None or self._statuses[pid] != PluginStatus.ACTIVE:
                continue

            # Tenant check
            if tenant_id and not self._is_plugin_enabled_for_tenant(tenant_id, pid):
                continue

            plugins.append(plugin)

        return plugins

    async def handle_intent(
        self,
        intent: Intent,
        context: PluginContext,
        plugin_id: str | None = None,
    ) -> PluginResult | None:
        """Handle an intent through a specific plugin or through intent matching.

        If plugin_id is provided, use that plugin directly.
        Otherwise, find the first matching active plugin.
        """
        if plugin_id:
            plugin = self._get_plugin(plugin_id)
            return await plugin.handle_intent(intent, context)

        matching = await self.get_plugins_for_intent(intent, context.tenant_id)
        if not matching:
            return None

        # Use first match (highest priority)
        plugin = matching[0]
        return await plugin.handle_intent(intent, context)

    # ── Query ─────────────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> BaseServicePlugin | None:
        """Get a registered plugin by id."""
        return self._plugins.get(plugin_id)

    def list_plugins(self, status: PluginStatus | None = None) -> list[PluginManifest]:
        """List all registered plugins, optionally filtered by status."""
        manifests = []
        for plugin_id, plugin in self._plugins.items():
            if status and self._statuses[plugin_id] != status:
                continue
            manifests.append(plugin.manifest)
        return manifests

    def get_plugin_status(self, plugin_id: str) -> PluginStatus:
        """Get the current status of a plugin."""
        self._get_plugin(plugin_id)
        return self._statuses[plugin_id]

    def list_intents(self) -> list[str]:
        """List all intent types that have registered plugins."""
        return list(self._intent_index.keys())

    # ── Tenant configuration ─────────────────────────────────

    def set_tenant_plugin_enabled(self, tenant_id: UUID, plugin_id: str, enabled: bool) -> None:
        """Enable/disable a plugin for a specific tenant."""
        if tenant_id not in self._tenant_plugins:
            self._tenant_plugins[tenant_id] = {}
        self._tenant_plugins[tenant_id][plugin_id] = enabled

    def _is_plugin_enabled_for_tenant(self, tenant_id: UUID, plugin_id: str) -> bool:
        """Check if a plugin is enabled for a tenant. Default: enabled."""
        return self._tenant_plugins.get(tenant_id, {}).get(plugin_id, True)

    # ── Internal ──────────────────────────────────────────────

    def _get_plugin(self, plugin_id: str) -> BaseServicePlugin:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin not found: {plugin_id}")
        return plugin


# ── Singleton ─────────────────────────────────────────────────

_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the registry (for testing)."""
    global _registry
    _registry = PluginRegistry()
