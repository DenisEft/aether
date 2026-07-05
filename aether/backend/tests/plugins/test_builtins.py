"""Tests for builtin plugins."""

import pytest
from uuid import uuid4

from app.plugins.base import Intent, PluginContext
from app.plugins.builtin.echo import EchoPlugin
from app.plugins.builtin.escalation import EscalationPlugin
from app.plugins.builtin.form import FormPlugin
from app.plugins.builtin.classifier import ClassifierPlugin
from app.plugins.builtin.faq import FaqPlugin
from app.plugins.builtin.scheduler import SchedulerPlugin
from app.plugins.builtin.knowledge_base import KnowledgeBasePlugin


class TestEchoPlugin:
    @pytest.mark.asyncio
    async def test_echo(self):
        plugin = EchoPlugin()
        intent = Intent(intent_type="echo", raw_message="Hello, World!")
        context = PluginContext(tenant_id=uuid4())

        result = await plugin.handle_intent(intent, context)
        assert result.success is True
        assert "Hello, World!" in result.text
        assert result.data["echoed"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_manifest(self):
        plugin = EchoPlugin()
        assert plugin.manifest.id == "echo"
        assert "echo" in plugin.manifest.intents


class TestEscalationPlugin:
    @pytest.mark.asyncio
    async def test_escalation(self):
        plugin = EscalationPlugin()
        intent = Intent(
            intent_type="complaint",
            raw_message="Your service is terrible!",
            entities={"reason": "Bad service"},
        )
        context = PluginContext(tenant_id=uuid4())

        result = await plugin.handle_intent(intent, context)
        assert result.success is True
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "transfer_to_human"
        assert result.data["escalated"] is True


class TestFormPlugin:
    @pytest.mark.asyncio
    async def test_form_fields_collection(self):
        plugin = FormPlugin()
        intent = Intent(
            intent_type="form",
            raw_message="I want to register",
            entities={"form_name": "registration", "fields": ["name", "email"]},
        )
        context = PluginContext(tenant_id=uuid4())

        result = await plugin.handle_intent(intent, context)
        assert result.success is True
        assert "wait_for_input" in [a.action_type for a in result.actions]

    @pytest.mark.asyncio
    async def test_form_partial_fill(self):
        plugin = FormPlugin()
        intent = Intent(
            intent_type="form",
            raw_message="My name is Denis",
            entities={"form_name": "registration", "fields": ["name", "email"], "name": "Denis"},
        )
        context = PluginContext(tenant_id=uuid4())

        result = await plugin.handle_intent(intent, context)
        assert result.success is True
        # Should ask for the remaining field (email)
        assert any("email" in str(a.payload).lower() for a in result.actions)


class TestManifests:
    """Verify all builtin plugins have valid manifests."""

    @pytest.mark.asyncio
    async def test_classifier_manifest(self):
        p = ClassifierPlugin()
        assert p.manifest.id == "classifier"
        assert p.manifest.is_prompt_driven is True

    @pytest.mark.asyncio
    async def test_faq_manifest(self):
        p = FaqPlugin()
        assert p.manifest.id == "faq"

    @pytest.mark.asyncio
    async def test_scheduler_manifest(self):
        p = SchedulerPlugin()
        assert p.manifest.id == "scheduler"

    @pytest.mark.asyncio
    async def test_knowledge_base_manifest(self):
        p = KnowledgeBasePlugin()
        assert p.manifest.id == "knowledge_base"
