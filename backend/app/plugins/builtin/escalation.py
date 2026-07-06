"""EscalationPlugin — transfers conversation to a human operator."""

from app.plugins.base import (
    Action,
    BaseServicePlugin,
    Intent,
    PluginContext,
    PluginHealth,
    PluginManifest,
    PluginResult,
    PluginStatus,
)


class EscalationPlugin(BaseServicePlugin):
    """Handles escalation — transferring to a human operator."""

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="escalation",
            name="Escalation",
            version="1.0.0",
            description="Transfers conversation to a human operator when AI cannot help.",
            intents=["escalation", "complaint", "human_operator", "operator"],
            is_builtin=True,
        )

    async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
        reason = intent.entities.get("reason", "User requested human assistance")
        return PluginResult(
            success=True,
            text="Переключаю на оператора. Пожалуйста, подождите...",
            actions=[
                Action(
                    action_type="transfer_to_human",
                    payload={
                        "reason": reason,
                        "priority": "high" if intent.confidence > 0.8 else "normal",
                        "summary": intent.raw_message[:200],
                        "conversation_id": str(context.conversation_id)
                        if context.conversation_id
                        else None,
                        "user_id": str(context.user_id) if context.user_id else None,
                    },
                )
            ],
            data={"escalated": True, "reason": reason},
            suggested_intents=["faq", "order_status"],
        )

    async def health_check(self) -> PluginHealth:
        return PluginHealth(status=PluginStatus.ACTIVE)
