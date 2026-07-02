from .base import BaseChannel, ChannelConfig, ChannelStatus
from .telegram_channel import TelegramChannel
from .email_channel import EmailChannel
from .widget_channel import WidgetChannel

__all__ = ["BaseChannel", "ChannelConfig", "ChannelStatus", "TelegramChannel", "EmailChannel", "WidgetChannel"]

CHANNEL_REGISTRY = {
    "telegram": TelegramChannel,
    "email": EmailChannel,
    "web_widget": WidgetChannel,
}

def create_channel(channel_type: str, config: ChannelConfig) -> BaseChannel:
    channel_cls = CHANNEL_REGISTRY.get(channel_type)
    if not channel_cls:
        raise ValueError(f"Unknown channel type: {channel_type}. Available: {list(CHANNEL_REGISTRY)}")
    return channel_cls(config)
