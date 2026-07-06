"""Plugin SDK — Base classes, contracts, and data structures.

Plugin Architecture:
    Business logic lives in plugins, NOT in the core.
    All plugins implement BaseServicePlugin (ABC).

Lifecycle:
    register → validate → activate → deactivate → uninstall
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid

# ── Permissions ──────────────────────────────────────────────


class PluginPermission(str, Enum):
    """Permissions a plugin can request in its manifest."""

    READ_DB = "read_db"
    WRITE_DB = "write_db"
    CALL_AI = "call_ai"
    SEND_MESSAGE = "send_message"
    CALL_EXTERNAL_API = "call_external_api"
    SCHEDULE_TASK = "schedule_task"
    READ_USER_DATA = "read_user_data"
    MANAGE_CHANNELS = "manage_channels"


# ── Plugin Status ────────────────────────────────────────────


class PluginStatus(str, Enum):
    REGISTERED = "registered"  # discovered, not yet validated
    VALIDATED = "validated"  # schema check passed
    ACTIVE = "active"  # running, handling intents
    INACTIVE = "inactive"  # installed but paused
    ERROR = "error"  # runtime error
    UNINSTALLING = "uninstalling"


# ── Data Classes ─────────────────────────────────────────────


@dataclass
class Capability:
    """What a plugin can do — declared in manifest."""

    name: str  # "document_generation", "price_calculation"
    display_name: str  # Human-readable
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    output_schema: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Intent:
    """What the user wants — classified by AI pipeline."""

    intent_type: str  # "order_status", "faq", "document_request"
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_message: str = ""
    language: str = "ru"
    sub_intent: str | None = None


@dataclass
class PluginResult:
    """Result returned by a plugin after handling an intent."""

    success: bool
    text: str = ""  # Main response text
    actions: list[Action] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)  # Structured data for templates
    error: str | None = None
    suggested_intents: list[str] = field(default_factory=list)  # Follow-up intents


@dataclass
class Action:
    """An action the plugin wants the system to execute."""

    action_type: str  # "send_message", "call_api", "wait_for_input",
    # "schedule_task", "transfer_to_human", "execute_code"
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    delay_seconds: float = 0.0


@dataclass
class PluginHealth:
    """Health status of a plugin."""

    status: PluginStatus
    uptime_seconds: float = 0.0
    total_requests: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    last_error: str | None = None
    memory_mb: float = 0.0


@dataclass
class PluginManifest:
    """Plugin descriptor — plugin.json schema."""

    id: str  # "faq", "gu12", "custom.tenant123.checkout"
    name: str  # Display name
    version: str  # SemVer
    description: str
    author: str = ""
    homepage: str = ""
    license: str = "MIT"
    capabilities: list[Capability] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)  # Intent types this plugin handles
    permissions: list[PluginPermission] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)  # plugin_id → version
    config_schema: dict[str, Any] = field(default_factory=dict)  # JSON Schema for config
    is_builtin: bool = False
    is_prompt_driven: bool = False


@dataclass
class ToolDefinition:
    """External API or tool a plugin declares it can use."""

    name: str  # "search_wagon", "get_order_status"
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema for params
    returns: dict[str, Any] = field(default_factory=dict)  # JSON Schema for return
    endpoint: str = ""  # URL or internal path
    method: str = "POST"  # HTTP method
    auth_required: bool = False
    rate_limit_per_minute: int = 60


# ── Plugin Context (passed to each plugin call) ──────────────


@dataclass
class PluginContext:
    """Context passed to a plugin when handling an intent."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    channel_type: str = "unknown"  # telegram, web_widget, email
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    collected_entities: dict[str, Any] = field(default_factory=dict)
    session_state: dict[str, Any] = field(default_factory=dict)  # Form state machine
    metadata: dict[str, Any] = field(default_factory=dict)


# ── BaseServicePlugin (ABC) ──────────────────────────────────


class BaseServicePlugin(ABC):
    """Abstract base class for all service plugins.

    Every plugin MUST implement this contract.

    Usage:
        class MyPlugin(BaseServicePlugin):
            @property
            def manifest(self) -> PluginManifest:
                return PluginManifest(id="my_plugin", name="My Plugin", version="1.0.0", ...)

            async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
                ...
    """

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Plugin metadata — id, version, capabilities, permissions."""
        ...

    @abstractmethod
    async def handle_intent(self, intent: Intent, context: PluginContext) -> PluginResult:
        """Handle a classified intent. Main entry point for the plugin.

        Called by PluginRegistry when an intent matches this plugin's intents list.
        """
        ...

    # ── Lifecycle hooks (optional overrides) ─────────────────

    async def on_register(self) -> None:
        """Called when plugin is first discovered/registered."""
        pass

    async def on_validate(self) -> bool:
        """Validate plugin config, dependencies, permissions. Return True if OK."""
        return True

    async def on_activate(self) -> None:
        """Called when plugin is activated (started)."""
        pass

    async def on_deactivate(self) -> None:
        """Called when plugin is deactivated (paused)."""
        pass

    async def on_uninstall(self) -> None:
        """Called before plugin is removed. Cleanup resources."""
        pass

    # ── Health ────────────────────────────────────────────────

    async def health_check(self) -> PluginHealth:
        """Return health status. Override for custom checks."""
        return PluginHealth(status=PluginStatus.ACTIVE)

    # ── Tools ─────────────────────────────────────────────────

    def get_tools(self) -> list[ToolDefinition]:
        """Return tools this plugin exposes for AI function calling."""
        return []
