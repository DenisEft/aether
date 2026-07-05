"""WebSocket handler for WebWidget channel.

Protocol: Aether WebSocket Protocol v1 (docs/specs/websocket-protocol.md).

Endpoint:  /ws/widget/{tenant_id}?token={jwt_token}

Message flow:
  - Client connects → JWT validation → system.connected
  - Ping/pong heartbeat (30s interval, max 3 missed)
  - Messages JSON-encoded with type field
  - Typing indicators, message delivery, quick replies
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select

from app.core.security import decode_token
from app.database import async_session_factory
from app.services.ws_manager import WebSocketManager

logger = logging.getLogger("aether.ws")

router = APIRouter()

# ── Constants ────────────────────────────────────────────────

HEARTBEAT_INTERVAL = 30
MAX_MISSED_HEARTBEATS = 3

# Global WebSocket manager instance
ws_manager = WebSocketManager()


# ── Helpers ──────────────────────────────────────────────────

async def validate_token(token: str) -> dict | None:
    """Validate JWT and return payload or None."""
    payload = decode_token(token)
    if payload is None:
        return None
    return payload


def connection_id() -> str:
    """Generate a short connection id."""
    return uuid.uuid4().hex[:12]


def _ts() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ── WebSocket endpoint ───────────────────────────────────────

@router.websocket("/ws/widget/{tenant_id}")
async def widget_websocket(
    websocket: WebSocket,
    tenant_id: uuid.UUID,
    token: str = Query(...),
):
    """WebSocket endpoint for WebWidget channel."""

    # 1. Validate JWT BEFORE accepting connection
    payload = await validate_token(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    # Verify tenant_id matches token
    token_tenant = payload.get("tenant_id")
    if token_tenant and str(tenant_id) != str(token_tenant):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Tenant mismatch")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token missing subject")
        return

    # Generate connection ID
    conn_id = connection_id()

    # 2. Accept connection
    await websocket.accept()

    # 3. Register connection
    channel_type = "widget"
    session_id = payload.get("session_id", conn_id)

    if not await ws_manager.register(conn_id, websocket, channel_type, str(tenant_id), user_id, str(tenant_id), session_id):
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Failed to register connection")
        return

    # 4. Send connected event
    try:
        connected_msg = {
            "type": "system.connected",
            "id": f"conn_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": 0,
            "session_id": session_id,
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "config": {
                "greeting_message": "Hello! How can I assist you today?",
                "locale": "en",
                "max_file_size_bytes": 10485760,
                "rate_limit": {
                    "messages_per_minute": 30,
                    "messages_per_day": 1000
                },
                "working_hours": {
                    "enabled": True,
                    "timezone": "UTC",
                    "schedule": "09:00-18:00"
                }
            }
        }

        await websocket.send_text(json.dumps(connected_msg, ensure_ascii=False))

        # 5. Main loop — receive messages + heartbeat
        heartbeat_missed = 0
        heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket, conn_id))

        last_seq = 0
        while True:
            try:
                try:
                    # Use a shorter timeout to allow more responsive heartbeat checking
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Check heartbeat timeout
                    heartbeat_missed += 1
                    if heartbeat_missed > MAX_MISSED_HEARTBEATS:
                        logger.info("WebSocket heartbeat timeout for connection %s", conn_id)
                        await websocket.close(code=4001, reason="Heartbeat timeout")
                        break
                    # Send ping
                    try:
                        ping_msg = {"type": "ping"}
                        await websocket.send_text(json.dumps(ping_msg))
                    except Exception as e:
                        logger.warning("WebSocket send ping error: %s", e, exc_info=True)
                        break
                    continue

                heartbeat_missed = 0  # Reset on any message

                # Parse and handle message
                await _handle_inbound(websocket, conn_id, user_id, tenant_id, raw, last_seq)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected for conn=%s", conn_id)
                break
            except Exception as e:
                logger.warning("WebSocket error for conn=%s: %s", conn_id, e, exc_info=True)
                # Don't close connection here, just log and continue processing

    except Exception as e:
        logger.error("WebSocket connection error for conn=%s: %s", conn_id, e, exc_info=True)
        pass
    finally:
        # Cleanup
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        await ws_manager.unregister(conn_id)


async def _heartbeat_loop(websocket: WebSocket, conn_id: str):
    """Send periodic pings."""
    HEARTBEAT_INTERVAL_SECONDS = HEARTBEAT_INTERVAL
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            # Send ping
            ping_msg = {"type": "ping"}
            await websocket.send_text(json.dumps(ping_msg))
        except Exception:
            # Connection probably closed
            logger.debug("Heartbeat ping failed — connection likely closed")
            break


async def _handle_inbound(websocket: WebSocket, conn_id: str, user_id: str, tenant_id: uuid.UUID, raw: str, last_seq: int):
    """Parse and route incoming WebSocket messages."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": last_seq + 1,
            "code": "INVALID_JSON",
            "message": "Message is not valid JSON"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))
        return

    msg_type = msg.get("type", "")
    seq = msg.get("seq", 0)

    if msg_type == "pong":
        # Heartbeat ping response
        logger.debug("Received pong for connection %s", conn_id)
        # No action needed, heartbeat is handled by timeout logic

    elif msg_type == "chat.message":
        await _handle_chat_message(websocket, conn_id, user_id, tenant_id, msg, seq)

    elif msg_type == "chat.typing":
        await _handle_typing(websocket, conn_id, user_id, tenant_id, msg, seq)

    elif msg_type == "chat.quick_reply":
        await _handle_quick_reply(websocket, conn_id, user_id, tenant_id, msg, seq)

    elif msg_type == "chat.subscription":
        # Handle subscription (subscribe/unsubscribe)
        await _handle_subscription(websocket, conn_id, user_id, tenant_id, msg, seq)

    else:
        # Unknown message type
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": last_seq + 1,
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": f"Unknown message type: {msg_type}"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))


async def _handle_chat_message(websocket: WebSocket, conn_id: str, user_id: str, tenant_id: uuid.UUID, msg: dict, seq: int):
    """Handle incoming chat message from widget."""
    conversation_id = msg.get("conversation_id")
    content = msg.get("content", "").strip()
    message_id = msg.get("id", str(uuid.uuid4()))

    if not content:
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "code": "INVALID_MESSAGE_CONTENT",
            "message": "Content is required"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))
        return

    # Get channel type from connection metadata
    metadata = ws_manager.connection_metadata.get(conn_id)
    channel_type = metadata.get("channel_type") if metadata else "widget"

    # Persist message asynchronously
    async with async_session_factory() as db:
        try:
            from app.models.conversations import Conversation, Message

            # If no conversation_id, create one or find existing
            if not conversation_id:
                result = await db.execute(
                    select(Conversation).where(
                        Conversation.tenant_id == tenant_id,
                        Conversation.status == "active",
                    ).order_by(Conversation.updated_at.desc()).limit(1)
                )
                conv = result.scalar_one_or_none()
                if conv:
                    conversation_id = str(conv.id)
                else:
                    # Create a new conversation
                    conv = Conversation(
                        tenant_id=tenant_id,
                        subject="WebWidget Chat",
                        channel_type="web_widget",
                    )
                    db.add(conv)
                    await db.flush()
                    conversation_id = str(conv.id)

            # Create message
            db_msg = Message(
                tenant_id=tenant_id,
                conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                user_id=uuid.UUID(user_id),
                role="user",
                content=content,
            )
            db.add(db_msg)
            await db.commit()
            await db.refresh(db_msg)

            # Ack to sender
            ack_msg = {
                "type": "chat.message_ack",
                "id": f"ack_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + 1,
                "message_id": str(db_msg.id),
                "client_message_id": message_id,
                "status": "delivered"
            }
            await websocket.send_text(json.dumps(ack_msg, ensure_ascii=False))

            # Route to AI for response generation
            await _generate_ai_response(websocket, conn_id, user_id, tenant_id, conversation_id, content, db_msg.id, seq + 1)

        except Exception as e:
            await db.rollback()
            error_msg = {
                "type": "system.error",
                "id": f"err_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + 1,
                "code": "PERSIST_ERROR",
                "message": str(e)
            }
            await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))


async def _generate_ai_response(
    websocket: WebSocket,
    conn_id: str,
    user_id: str,
    tenant_id: uuid.UUID,
    conversation_id: str,
    user_text: str,
    user_message_id: uuid.UUID,
    seq: int
):
    """Stage 4: Route user message to AI core and stream response back."""
    try:
        from app.ai.manager import ai_manager

        # Get channel type from connection metadata
        metadata = ws_manager.connection_metadata.get(conn_id)
        channel_type = metadata.get("channel_type") if metadata else "widget"

        # Build conversation context (last N messages)
        messages: list[dict] = []
        async with async_session_factory() as db:
            from app.models.conversations import Message
            from sqlalchemy import select

            result = await db.execute(
                select(Message)
                .where(
                    Message.tenant_id == tenant_id,
                    Message.conversation_id == uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                )
                .order_by(Message.created_at.desc())
                .limit(20)
            )
            history = result.scalars().all()
            # Reverse for chronological order
            for msg in reversed(history):
                if msg.id == user_message_id:
                    continue  # skip the message we just persisted (it's the current user text)
                role = "assistant" if msg.role == "assistant" else "user"
                messages.append({"role": role, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": user_text})

        # Send typing indicator
        typing_msg = {
            "type": "chat.typing",
            "id": f"typing_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "conversation_id": conversation_id,
            "status": "started",
            "role": "ai"
        }
        await ws_manager.broadcast(channel_type, conversation_id, typing_msg)

        # Generate AI response (streaming)
        full_response = ""
        chunk_count = 0
        async for chunk in ai_manager.generate_stream(
            messages=messages,
            system_prompt="You are a helpful business assistant. Be concise and friendly.",
            temperature=0.7,
            max_tokens=1024,
        ):
            full_response += chunk
            chunk_count += 1
            # Stream each chunk to the client
            chunk_msg = {
                "type": "chat.message_chunk",
                "id": f"chunk_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + chunk_count,
                "conversation_id": conversation_id,
                "chunk": chunk,
                "status": "processing"
            }
            await ws_manager.broadcast(channel_type, conversation_id, chunk_msg)

        # Persist AI response
        async with async_session_factory() as db:
            from app.models.conversations import Message

            ai_msg = Message(
                tenant_id=tenant_id,
                conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                role="assistant",
                content=full_response,
            )
            db.add(ai_msg)
            await db.commit()
            await db.refresh(ai_msg)

            # Send final message
            final_msg = {
                "type": "chat.message",
                "id": f"msg_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + chunk_count + 1,
                "conversation_id": conversation_id,
                "message_id": str(ai_msg.id),
                "role": "assistant",
                "content": full_response
            }
            await ws_manager.broadcast(channel_type, conversation_id, final_msg)

            # Stop typing
            stop_typing_msg = {
                "type": "chat.typing",
                "id": f"typing_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + chunk_count + 2,
                "conversation_id": conversation_id,
                "status": "stopped",
                "role": "ai"
            }
            await ws_manager.broadcast(channel_type, conversation_id, stop_typing_msg)

    except Exception as e:
        logger.exception("AI response generation failed for tenant=%s conv=%s", tenant_id, conversation_id)
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "code": "AI_RESPONSE_ERROR",
            "message": "Failed to generate AI response"
        }
        await ws_manager.broadcast(channel_type, conversation_id, error_msg)

        # Send fallback message
        fallback_msg = {
            "type": "chat.message",
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Sorry, I couldn't process your request right now. Please try again.",
            "error": True
        }
        await ws_manager.broadcast(channel_type, conversation_id, fallback_msg)


async def _handle_typing(websocket: WebSocket, conn_id: str, user_id: str, tenant_id: uuid.UUID, msg: dict, seq: int):
    """Handle typing indicator from client."""
    conversation_id = msg.get("conversation_id")
    status = msg.get("status", "started")

    if not conversation_id:
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "code": "INVALID_TYPING_DATA",
            "message": "Conversation ID is required"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))
        return

    # Get channel type from connection metadata
    metadata = ws_manager.connection_metadata.get(conn_id)
    channel_type = metadata.get("channel_type") if metadata else "widget"

    # Broadcast typing indicator to all connections in the conversation
    typing_msg = {
        "type": "chat.typing",
        "id": f"typing_{uuid.uuid4().hex[:8]}",
        "timestamp": _ts(),
        "seq": seq + 1,
        "conversation_id": conversation_id,
        "status": status,
        "role": "human",
        "user_id": user_id
    }

    await ws_manager.broadcast(channel_type, conversation_id, typing_msg)


async def _handle_quick_reply(websocket: WebSocket, conn_id: str, user_id: str, tenant_id: uuid.UUID, msg: dict, seq: int):
    """Handle quick reply button click from widget."""
    conversation_id = msg.get("conversation_id")
    payload = msg.get("payload", "")

    if not conversation_id or not payload:
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "code": "INVALID_QUICK_REPLY",
            "message": "Conversation ID and payload are required"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))
        return

    # Get channel type from connection metadata
    metadata = ws_manager.connection_metadata.get(conn_id)
    channel_type = metadata.get("channel_type") if metadata else "widget"

    # Persist as a message with type=quick_reply
    async with async_session_factory() as db:
        try:
            from app.models.conversations import Message

            db_msg = Message(
                tenant_id=tenant_id,
                conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                user_id=uuid.UUID(user_id),
                role="user",
                content=payload,
                metadata={"type": "quick_reply"},
            )
            db.add(db_msg)
            await db.commit()
            await db.refresh(db_msg)

            # Ack to sender
            ack_msg = {
                "type": "chat.quick_reply_ack",
                "id": f"ack_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + 1,
                "message_id": str(db_msg.id),
                "status": "delivered"
            }
            await websocket.send_text(json.dumps(ack_msg, ensure_ascii=False))

        except Exception as e:
            await db.rollback()
            error_msg = {
                "type": "system.error",
                "id": f"err_{uuid.uuid4().hex[:8]}",
                "timestamp": _ts(),
                "seq": seq + 1,
                "code": "PERSIST_ERROR",
                "message": str(e)
            }
            await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))


async def _handle_subscription(websocket: WebSocket, conn_id: str, user_id: str, tenant_id: uuid.UUID, msg: dict, seq: int):
    """Handle subscription messages (subscribe/unsubscribe)."""
    action = msg.get("action")
    channel_type = msg.get("channel_type")
    channel_id = msg.get("channel_id")

    if not action or not channel_type or not channel_id:
        error_msg = {
            "type": "system.error",
            "id": f"err_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "code": "INVALID_SUBSCRIPTION",
            "message": "Missing action, channel_type, or channel_id"
        }
        await websocket.send_text(json.dumps(error_msg, ensure_ascii=False))
        return

    if action == "subscribe":
        # For this implementation, we just acknowledge the subscription
        ack_msg = {
            "type": "chat.subscription_ack",
            "id": f"ack_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "action": "subscribe",
            "channel_type": channel_type,
            "channel_id": channel_id,
            "status": "success"
        }
        await websocket.send_text(json.dumps(ack_msg, ensure_ascii=False))

    elif action == "unsubscribe":
        # For this implementation, we just acknowledge the unsubscription
        ack_msg = {
            "type": "chat.subscription_ack",
            "id": f"ack_{uuid.uuid4().hex[:8]}",
            "timestamp": _ts(),
            "seq": seq + 1,
            "action": "unsubscribe",
            "channel_type": channel_type,
            "channel_id": channel_id,
            "status": "success"
        }
        await websocket.send_text(json.dumps(ack_msg, ensure_ascii=False))
