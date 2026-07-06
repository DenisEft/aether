"""EchoPlugin — returns the user's message as-is. Simplest plugin for testing."""

from app.plugins.base import (
    BaseServicePlugin,
    Intent,
    PluginContext,
    PluginHealth,
    PluginManifest,
    PluginResult,
    PluginStatus,
)


class EchoPlugin(BaseServicePlugin):
    """Echo back the user's message. Useful for testing the plugin system."""

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="echo",
            name="Echo",
            version="1.0.0",
            description="Returns the user's message as-is for testing.",
            intents=["echo", "test"],
            is_builtin=True,
        )

    async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
        return PluginResult(
            success=True,
            text=f"Echo: {intent.raw_message}",
            data={"echoed": intent.raw_message},
        )

    async def health_check(self) -> PluginHealth:
        return PluginHealth(status=PluginStatus.ACTIVE)
