"""Tests for PromptDrivenPlugin."""

import pytest
from uuid import uuid4

from app.plugins.base import (
    Intent,
    PluginContext,
    PluginManifest,
)
from app.plugins.prompt_driver import PromptDrivenPlugin


@pytest.fixture
def prompt_plugin():
    return PromptDrivenPlugin(
        manifest=PluginManifest(
            id="test_faq",
            name="Test FAQ",
            version="1.0.0",
            description="Test FAQ plugin",
            intents=["faq", "question"],
            is_prompt_driven=True,
        ),
        system_prompt="You are a test FAQ bot for {tenant_id}.",
        examples=[
            {"role": "user", "content": "What is Aether?"},
            {"role": "assistant", "content": "Aether is a SaaS platform."},
        ],
    )


class TestPromptDrivenPlugin:
    """Test PromptDrivenPlugin behavior."""

    @pytest.mark.asyncio
    async def test_manifest(self, prompt_plugin):
        manifest = prompt_plugin.manifest
        assert manifest.id == "test_faq"
        assert manifest.is_prompt_driven is True
        assert "faq" in manifest.intents

    @pytest.mark.asyncio
    async def test_build_messages(self, prompt_plugin):
        intent = Intent(
            intent_type="faq",
            raw_message="What is Aether?",
            language="en",
        )
        context = PluginContext(
            tenant_id=uuid4(),
            channel_type="web_widget",
        )

        result = await prompt_plugin.handle_intent(intent, context)
        assert result.success is True

        # Check that messages were assembled
        messages = result.data.get("messages", [])
        assert len(messages) >= 2  # system + example + user
        assert messages[0]["role"] == "system"
        assert "test FAQ bot" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_template_rendering(self, prompt_plugin):
        """Test that {tenant_id} and other variables are rendered."""
        tenant_id = uuid4()
        intent = Intent(intent_type="faq", raw_message="help")
        context = PluginContext(tenant_id=tenant_id)

        result = await prompt_plugin.handle_intent(intent, context)
        messages = result.data.get("messages", [])

        system_content = messages[0]["content"]
        assert str(tenant_id) in system_content

    @pytest.mark.asyncio
    async def test_entity_formatting(self, prompt_plugin):
        """Test that entities are included in the prompt."""
        intent = Intent(
            intent_type="faq",
            raw_message="Order #12345 status?",
            entities={"order_id": "12345", "status": "pending"},
        )
        context = PluginContext(tenant_id=uuid4())

        result = await prompt_plugin.handle_intent(intent, context)
        messages = result.data.get("messages", [])

        # Last message should contain entities
        user_message = messages[-1]["content"]
        assert "12345" in user_message

    @pytest.mark.asyncio
    async def test_get_tools(self):
        """Test tool definitions."""
        from app.plugins.base import ToolDefinition

        plugin = PromptDrivenPlugin(
            manifest=PluginManifest(
                id="tool_plugin",
                name="Tool Plugin",
                version="1.0.0",
                description="",
                intents=["test"],
                is_prompt_driven=True,
            ),
            system_prompt="test",
            tools=[
                ToolDefinition(
                    name="search_orders",
                    description="Search orders by ID",
                    parameters={"type": "object", "properties": {"order_id": {"type": "string"}}},
                )
            ],
        )

        tools = plugin.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "search_orders"
