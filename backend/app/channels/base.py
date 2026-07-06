"""Base channel ABC and data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import StrEnum


class ChannelStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ChannelConfig:
    id: str
    channel_type: str
    tenant_id: str
    display_name: str = ""
    is_active: bool = True
    config: dict = field(default_factory=dict)


@dataclass
class ChannelMessage:
    id: str
    channel_id: str
    conversation_id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str = ""
    metadata: dict = field(default_factory=dict)


class BaseChannel(ABC):
    """Abstract base for all communication channels."""

    def __init__(self, config: ChannelConfig):
        self.config = config
        self._status = ChannelStatus.DISCONNECTED

    @property
    def status(self) -> ChannelStatus:
        return self._status

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the channel (connect, auth, etc.). Returns True on success."""
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if channel is healthy."""
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, text: str, **kwargs) -> dict:
        """Send a message through this channel."""
        ...

    @abstractmethod
    async def poll_messages(self) -> AsyncGenerator[MessageContext, None]:
        """Poll for new messages (for polling-based channels)."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup channel resources."""
        ...


@dataclass
class MessageContext:
    """Normalized message from any channel."""

    channel_type: str
    channel_id: str
    external_user_id: str
    external_user_name: str
    text: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
