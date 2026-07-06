"""Channel router: manages channel lifecycle, routes messages."""

from __future__ import annotations

import asyncio
import logging

from . import create_channel
from .base import BaseChannel, ChannelConfig

logger = logging.getLogger("aether.channels.router")


class ChannelRouter:
    """Manages all communication channels: lifecycle, routing, message dispatch."""

    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}
        self._running = False
        self._poll_tasks: dict[str, asyncio.Task] = {}
        self._message_handlers: list = []  # list of async callables

    def register_handler(self, handler):
        """Register a message handler.

        async def handler(ctx: MessageContext, channel: BaseChannel) -> None
        """
        self._message_handlers.append(handler)

    async def start_channel(self, config: ChannelConfig) -> BaseChannel:
        """Start a channel by config."""
        key = f"{config.channel_type}:{config.id}"
        if key in self._channels:
            await self.stop_channel(key)

        channel = create_channel(config.channel_type, config)
        await channel.initialize()
        self._channels[key] = channel

        # Start polling if channel supports it
        task = asyncio.create_task(self._poll_loop(key, channel))
        self._poll_tasks[key] = task

        logger.info(f"Channel started: {key}")
        return channel

    async def stop_channel(self, key: str):
        """Stop a channel."""
        channel = self._channels.pop(key, None)
        task = self._poll_tasks.pop(key, None)

        if task:
            task.cancel()
        if channel:
            await channel.shutdown()
            logger.info(f"Channel stopped: {key}")

    async def _poll_loop(self, key: str, channel: BaseChannel):
        """Poll channel for messages and dispatch to handlers."""
        try:
            async for ctx in channel.poll_messages():
                for handler in self._message_handlers:
                    try:
                        await handler(ctx, channel)
                    except Exception as e:
                        logger.error(f"Handler error for {key}: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Poll error for {key}: {e}")

    async def send_message(
        self, channel_type: str, channel_id: str, chat_id: str, text: str
    ) -> dict:
        """Send a message through a specific channel."""
        key = f"{channel_type}:{channel_id}"
        channel = self._channels.get(key)
        if not channel:
            raise ValueError(f"Channel not found: {key}")
        return await channel.send_message(chat_id, text)

    async def broadcast(self, chat_ids: list[str], text: str, exclude_channel: str | None = None):
        """Send message to multiple chat_ids across all channels."""
        results = []
        for key, channel in self._channels.items():
            if exclude_channel and key == exclude_channel:
                continue
            for chat_id in chat_ids:
                try:
                    result = await channel.send_message(chat_id, text)
                    results.append({"channel": key, "chat_id": chat_id, "result": result})
                except Exception as e:
                    results.append({"channel": key, "chat_id": chat_id, "error": str(e)})
        return results

    def get_status(self) -> dict:
        """Get status of all channels."""
        return {
            key: {
                "type": ch.config.channel_type,
                "status": ch.status.value,
                "display_name": ch.config.display_name,
            }
            for key, ch in self._channels.items()
        }

    async def shutdown_all(self):
        """Stop all channels."""
        for key in list(self._channels.keys()):
            await self.stop_channel(key)
        logger.info("All channels stopped")


# Global router singleton
channel_router = ChannelRouter()
