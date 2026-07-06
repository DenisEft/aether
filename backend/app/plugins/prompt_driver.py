"""PromptDrivenPlugin — AI-powered plugin via prompt + examples + tools.

Instead of writing Python code, users configure a plugin through:
- A system prompt (defines behavior)
- Conversation examples (few-shot)
- Tool definitions (declared external API calls)

The AI engine handles intent → response using these configurations.
This is Stage 1/MVP for non-technical users.
"""

from __future__ import annotations

import json
import logging

from app.plugins.base import (
    BaseServicePlugin,
    Intent,
    PluginContext,
    PluginHealth,
    PluginManifest,
    PluginResult,
    PluginStatus,
    ToolDefinition,
)

logger = logging.getLogger("aether.plugins.prompt_driver")


class PromptDrivenPlugin(BaseServicePlugin):
    """Plugin driven by AI prompt configuration — no Python code needed.

    Manifest example:
        PromptDrivenPlugin(
            manifest=PluginManifest(
                id="faq",
                name="FAQ Plugin",
                version="1.0.0",
                description="Answers frequently asked questions",
                intents=["faq", "question"],
                is_prompt_driven=True,
            ),
            system_prompt="You are a helpful FAQ bot...",
            examples=[...],
            tools=[...],
        )
    """

    def __init__(
        self,
        manifest: PluginManifest,
        system_prompt: str,
        examples: list[dict[str, str]] | None = None,
        tools: list[ToolDefinition] | None = None,
        response_config: dict | None = None,
    ):
        self._manifest = manifest
        self._system_prompt = system_prompt
        self._examples: list[dict[str, str]] = examples or []
        self._tools: list[ToolDefinition] = tools or []
        self._response_config: dict = response_config or {}
        self._request_count = 0
        self._error_count = 0

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    # ── Intent Handling ───────────────────────────────────────

    async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
        """Process intent by assembling prompt + calling AI engine.

        The actual AI call is delegated to ai_manager via the plugin context.
        Plugin doesn't call AI directly — it returns a prompt assembly for the system.
        """
        self._request_count += 1

        try:
            # Build messages for the AI engine
            messages = self._build_messages(intent, context)

            # Build tool definitions for function calling
            tool_defs = self._build_tool_defs()

            # Return result — actual AI call happens in service layer
            # The service layer calls ai_manager.generate_stream(messages, tools=tool_defs)
            return PluginResult(
                success=True,
                text="",  # Filled by service layer after AI call
                data={
                    "messages": messages,
                    "tools": tool_defs,
                    "response_config": self._response_config,
                    "plugin_id": self._manifest.id,
                },
                suggested_intents=self._manifest.intents,
            )
        except Exception as e:
            self._error_count += 1
            logger.exception(f"PromptDrivenPlugin {self._manifest.id} error")
            return PluginResult(success=False, error=str(e))

    # ── Prompt Assembly ───────────────────────────────────────

    def _build_messages(self, intent: Intent, context: PluginContext) -> list[dict[str, str]]:
        """Assemble AI messages: system prompt + examples + context + user message."""
        messages = [{"role": "system", "content": self._render_prompt(intent, context)}]

        # Add few-shot examples
        for example in self._examples:
            messages.append({"role": example.get("role", "user"), "content": example["content"]})

        # Add conversation history
        for hist_msg in context.conversation_history[-10:]:
            messages.append({"role": hist_msg.get("role", "user"), "content": hist_msg["content"]})

        # Add current intent
        messages.append(
            {
                "role": "user",
                "content": self._format_intent_message(intent, context),
            }
        )

        return messages

    def _render_prompt(self, intent: Intent, context: PluginContext) -> str:
        """Render system prompt with template variables."""
        prompt = self._system_prompt

        # Simple variable substitution
        variables = {
            "tenant_id": str(context.tenant_id),
            "user_id": str(context.user_id) if context.user_id else "anonymous",
            "channel": context.channel_type,
            "intent": intent.intent_type,
            "language": intent.language,
        }
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt

    def _format_intent_message(self, intent: Intent, context: PluginContext) -> str:
        """Format the user's intent as a message for the AI."""
        parts = [f"User said: {intent.raw_message}"]

        if intent.entities:
            entities_str = json.dumps(intent.entities, ensure_ascii=False, indent=2)
            parts.append(f"Extracted entities: {entities_str}")

        if context.collected_entities:
            collected_str = json.dumps(context.collected_entities, ensure_ascii=False)
            parts.append(f"Previously collected: {collected_str}")

        if context.session_state:
            state_str = json.dumps(context.session_state, ensure_ascii=False)
            parts.append(f"Session state: {state_str}")

        return "\n".join(parts)

    # ── Tool Definitions ──────────────────────────────────────

    def _build_tool_defs(self) -> list[dict]:
        """Convert ToolDefinition to OpenAI-compatible function calling format."""
        tool_defs = []
        for tool in self.get_tools():
            tool_defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return tool_defs

    def get_tools(self) -> list[ToolDefinition]:
        return self._tools

    # ── Health ────────────────────────────────────────────────

    async def health_check(self) -> PluginHealth:
        return PluginHealth(
            status=PluginStatus.ACTIVE,
            total_requests=self._request_count,
            total_errors=self._error_count,
        )
