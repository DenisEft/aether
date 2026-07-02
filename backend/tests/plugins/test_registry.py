"""Tests for plugin registry and lifecycle."""

import pytest
from uuid import uuid4

from app.plugins.base import (
    Intent,
    PluginContext,
    PluginManifest,
    PluginResult,
    PluginStatus,
)
from app.plugins.registry import PluginRegistry, PluginNotFoundError, PluginValidationError
from app.plugins.builtin.echo import EchoPlugin
from app.plugins.builtin.escalation import EscalationPlugin


@pytest.fixture
def registry():
    """Fresh registry for each test."""
    from app.plugins.registry import reset_registry, get_registry
    reset_registry()
    return get_registry()


class TestPluginLifecycle:
    """Test complete plugin lifecycle: register → validate → activate → deactivate → unregister."""

    @pytest.mark.asyncio
    async def test_register_and_activate(self, registry):
        plugin = EchoPlugin()
        await registry.register(plugin)

        assert plugin.manifest.id == "echo"
        assert registry.get_plugin_status("echo") == PluginStatus.VALIDATED

        await registry.activate("echo")
        assert registry.get_plugin_status("echo") == PluginStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_deactivate_and_unregister(self, registry):
        plugin = EchoPlugin()
        await registry.register(plugin)
        await registry.activate("echo")

        await registry.deactivate("echo")
        assert registry.get_plugin_status("echo") == PluginStatus.INACTIVE

        await registry.unregister("echo")
        assert registry.get_plugin("echo") is None

    @pytest.mark.asyncio
    async def test_cannot_activate_before_register(self, registry):
        with pytest.raises(PluginNotFoundError):
            await registry.activate("nonexistent")

    @pytest.mark.asyncio
    async def test_list_plugins(self, registry):
        await registry.register(EchoPlugin())
        await registry.activate("echo")
        await registry.register(EscalationPlugin())
        await registry.activate("escalation")

        all_plugins = registry.list_plugins()
        assert len(all_plugins) == 2

        active_plugins = registry.list_plugins(PluginStatus.ACTIVE)
        assert len(active_plugins) == 2


class TestIntentMatching:
    """Test intent → plugin matching."""

    @pytest.mark.asyncio
    async def test_match_intent_to_plugin(self, registry):
        await registry.register(EchoPlugin())
        await registry.activate("echo")
        await registry.register(EscalationPlugin())
        await registry.activate("escalation")

        # Echo intent should match EchoPlugin
        intent = Intent(intent_type="echo", raw_message="test")
        matching = await registry.get_plugins_for_intent(intent)
        assert len(matching) == 1
        assert matching[0].manifest.id == "echo"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, registry):
        await registry.register(EchoPlugin())
        await registry.activate("echo")

        intent = Intent(intent_type="unknown_intent", raw_message="test")
        matching = await registry.get_plugins_for_intent(intent)
        assert len(matching) == 0

    @pytest.mark.asyncio
    async def test_handle_intent_through_registry(self, registry):
        await registry.register(EchoPlugin())
        await registry.activate("echo")

        intent = Intent(intent_type="echo", raw_message="Hello!")
        context = PluginContext(tenant_id=uuid4())

        result = await registry.handle_intent(intent, context)
        assert result is not None
        assert result.success is True
        assert "Echo" in result.text

    @pytest.mark.asyncio
    async def test_handle_intent_direct_plugin(self, registry):
        await registry.register(EscalationPlugin())
        await registry.activate("escalation")

        intent = Intent(intent_type="complaint", raw_message="Bad service!")
        context = PluginContext(tenant_id=uuid4())

        result = await registry.handle_intent(intent, context, plugin_id="escalation")
        assert result is not None
        assert result.success is True
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "transfer_to_human"


class TestListIntents:
    """Test listing all registered intents."""

    @pytest.mark.asyncio
    async def test_list_intents(self, registry):
        await registry.register(EchoPlugin())
        await registry.activate("echo")
        await registry.register(EscalationPlugin())
        await registry.activate("escalation")

        intents = registry.list_intents()
        assert "echo" in intents
        assert "complaint" in intents
