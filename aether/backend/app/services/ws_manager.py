"""WebSocket Connection Manager for Aether.

Manages WebSocket connections and message broadcasting.
Uses Redis pub/sub for cross-process communication in production.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("aether.ws.manager")


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        # In-memory storage for connections (replace with Redis in production)
        # Structure: {channel_type: {channel_id: {connection_id: connection_info}}}
        self.connections: Dict[str, Dict[str, Dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))

        # Store connection metadata: {connection_id: {user_id, tenant_id, connected_at, channel_type, channel_id}}
        self.connection_metadata: Dict[str, dict] = {}

        # For heartbeat tracking
        self.connection_heartbeats: Dict[str, int] = {}

        # For session persistence (optional)
        self.active_sessions: Dict[str, dict] = {}

    async def register(self, connection_id: str, websocket: WebSocket, channel_type: str, channel_id: str,
                       user_id: str, tenant_id: str, session_id: str = None) -> bool:
        """Register a new WebSocket connection."""
        try:
            # Store connection metadata
            self.connection_metadata[connection_id] = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "channel_type": channel_type,
                "channel_id": channel_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
            }

            # Register connection in the channels structure
            self.connections[channel_type][channel_id][connection_id] = {
                "ws": websocket,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }

            # Reset heartbeat counter
            self.connection_heartbeats[connection_id] = 0

            logger.info("WebSocket registered: connection_id=%s, channel=%s/%s", connection_id, channel_type, channel_id)
            return True

        except Exception as e:
            logger.error("Failed to register WebSocket connection: %s", e, exc_info=True)
            return False

    async def unregister(self, connection_id: str) -> bool:
        """Unregister a WebSocket connection."""
        try:
            # Get metadata to clean up properly
            metadata = self.connection_metadata.get(connection_id)
            if not metadata:
                return False

            channel_type = metadata.get("channel_type")
            channel_id = metadata.get("channel_id")

            # Remove from connections
            if channel_type in self.connections and channel_id in self.connections[channel_type]:
                if connection_id in self.connections[channel_type][channel_id]:
                    del self.connections[channel_type][channel_id][connection_id]
                    if not self.connections[channel_type][channel_id]:
                        del self.connections[channel_type][channel_id]
                        if not self.connections[channel_type]:
                            del self.connections[channel_type]

            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

            # Remove heartbeat tracking
            if connection_id in self.connection_heartbeats:
                del self.connection_heartbeats[connection_id]

            logger.info("WebSocket unregistered: connection_id=%s", connection_id)
            return True

        except Exception as e:
            logger.error("Failed to unregister WebSocket connection: %s", e, exc_info=True)
            return False

    async def broadcast(self, channel_type: str, channel_id: str, message: dict) -> int:
        """Broadcast a message to all connections in a channel."""
        try:
            connections = self.connections.get(channel_type, {}).get(channel_id, {})
            if not connections:
                return 0

            # Convert to JSON
            message_str = json.dumps(message, ensure_ascii=False)

            # Send to all connections in channel
            sent_count = 0
            for conn_id, connection_info in list(connections.items()):
                try:
                    ws = connection_info.get("ws")
                    if ws and not ws.application_state == "DISCONNECTED":
                        await ws.send_text(message_str)
                        sent_count += 1
                    else:
                        # Connection is invalid, remove it
                        await self.unregister(conn_id)
                except Exception as e:
                    logger.warning("Failed to send message to connection %s: %s", conn_id, e)
                    await self.unregister(conn_id)

            logger.debug("Broadcast sent to %d connections in %s/%s", sent_count, channel_type, channel_id)
            return sent_count

        except Exception as e:
            logger.error("Failed to broadcast message: %s", e, exc_info=True)
            return 0

    async def send_personal(self, message: dict, connection_id: str) -> bool:
        """Send a message to a specific connection."""
        try:
            connection_info = self._get_connection(connection_id)
            if not connection_info:
                return False

            ws = connection_info.get("ws")
            if not ws or ws.application_state == "DISCONNECTED":
                await self.unregister(connection_id)
                return False

            message_str = json.dumps(message, ensure_ascii=False)
            await ws.send_text(message_str)

            logger.debug("Personal message sent to connection %s", connection_id)
            return True

        except Exception as e:
            logger.error("Failed to send personal message to %s: %s", connection_id, e, exc_info=True)
            return False

    async def broadcast_to_tenant(self, tenant_id: str, channel: str, message: dict) -> int:
        """Broadcast a message to all connections for a tenant's channel.

        Channel naming convention: tenant:{tenant_id}:{channel}

        Returns count of sent messages.
        """
        total_sent = 0
        tenant_key = f"tenant:{tenant_id}"

        for channel_type, channel_data in self.connections.items():
            if channel_type == tenant_key:
                for channel_id, connections in channel_data.items():
                    if channel_id == channel:
                        sent = await self.broadcast(channel_type, channel_id, message)
                        total_sent += sent

        logger.debug("Broadcast to tenant %s/%s: %d connections", tenant_id, channel, total_sent)
        return total_sent

    async def get_active_connections(self, channel_type: str, channel_id: str) -> int:
        """Get count of active connections in a channel."""
        connections = self.connections.get(channel_type, {}).get(channel_id, {})
        return len(connections)

    async def update_heartbeat(self, connection_id: str) -> bool:
        """Update heartbeat counter for connection."""
        try:
            if connection_id in self.connection_heartbeats:
                self.connection_heartbeats[connection_id] += 1
                return True
            return False
        except Exception as e:
            logger.error("Failed to update heartbeat for connection %s: %s", connection_id, e, exc_info=True)
            return False

    async def get_connection_heartbeat(self, connection_id: str) -> int:
        """Get current heartbeat count for connection."""
        return self.connection_heartbeats.get(connection_id, 0)

    def _get_connection(self, connection_id: str) -> Optional[dict]:
        """Helper to get connection info."""
        for channel_type, channel_data in self.connections.items():
            for channel_id, connections in channel_data.items():
                if connection_id in connections:
                    return connections[connection_id]
        return None

    async def send_typing_indicator(self, channel_type: str, channel_id: str,
                                   user_id: str, is_typing: bool, user_name: str = "") -> int:
        """Send typing indicator to all connections in a channel."""
        try:
            message = {
                "type": "chat.typing",
                "conversation_id": channel_id,
                "user_id": user_id,
                "user_name": user_name,
                "is_typing": is_typing,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return await self.broadcast(channel_type, channel_id, message)

        except Exception as e:
            logger.error("Failed to send typing indicator: %s", e, exc_info=True)
            return 0

    async def send_read_receipt(self, channel_type: str, channel_id: str,
                          message_id: str) -> int:
        """Send read receipt to all connections in a channel."""
        try:
            message = {
                "type": "chat.delivery_status",
                "message_id": message_id,
                "status": "read",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            return await self.broadcast(channel_type, channel_id, message)

        except Exception as e:
            logger.error("Failed to send read receipt: %s", e, exc_info=True)
            return 0
