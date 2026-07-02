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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select

from app.core.security import decode_token
from app.database import async_session_factory

logger = logging.getLogger("aether.ws")

router = APIRouter()

# ── Constants ────────────────────────────────────────────────

HEARTBEAT_INTERVAL = 30
MAX_MISSED_HEARTBEATS = 3

# ── Connection registry (in-memory, replace with Redis in prod) ──

connections: dict[str, dict] = {}  # tenant_id -> {connection_id: {...}}


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


# ── Message builders ─────────────────────────────────────────

def _sys_msg(event: str, **kwargs) -> str:
    return json.dumps({"type": "system", "event": event, "timestamp": _ts(), **kwargs}, ensure_ascii=False)


def _err(code: str, message: str, **kwargs) -> str:
    return json.dumps({"type": "error", "code": code, "message": message, "timestamp": _ts(), **kwargs}, ensure_ascii=False)


def _ts() -> str:
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

    # 2. Accept connection
    await websocket.accept()

    # 3. Register connection
    conn_id = connection_id()
    conn_key = str(tenant_id)
    if conn_key not in connections:
        connections[conn_key] = {}
    connections[conn_key][conn_id] = {
        "ws": websocket,
        "user_id": user_id,
        "connected_at": _ts(),
    }

    # 4. Send connected event
    try:
        await websocket.send_text(_sys_msg("connected", connection_id=conn_id, user_id=user_id))

        # 5. Main loop — receive messages + heartbeat
        heartbeat_missed = 0
        heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))

        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_INTERVAL)
                heartbeat_missed = 0  # reset on any message

                # Parse and handle message
                await _handle_inbound(websocket, tenant_id, conn_id, user_id, raw)

            except asyncio.TimeoutError:
                # No message in heartbeat window — send ping
                heartbeat_missed += 1
                if heartbeat_missed > MAX_MISSED_HEARTBEATS:
                    await websocket.close(code=4001, reason="Heartbeat timeout")
                    break
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception as e:
                    logger.warning("WebSocket send ping error: %s", e, exc_info=True)
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for conn=%s", conn_id)
        pass
    except Exception as e:
        logger.warning("WebSocket error for conn=%s: %s", conn_id, e, exc_info=True)
        pass
    finally:
        # Cleanup
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        if conn_key in connections:
            connections[conn_key].pop(conn_id, None)
            if not connections[conn_key]:
                del connections[conn_key]


async def _heartbeat_loop(websocket: WebSocket):
    """Send periodic pings."""
    HEARTBEAT_INTERVAL_SECONDS = HEARTBEAT_INTERVAL
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        try:
            await websocket.send_text(json.dumps({"type": "ping"}))
        except Exception:
            break


async def _handle_inbound(websocket: WebSocket, tenant_id: uuid.UUID, conn_id: str, user_id: str, raw: str):
    """Parse and route incoming WebSocket messages."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_text(_err("invalid_json", "Message is not valid JSON"))
        return

    msg_type = msg.get("type", "")

    if msg_type == "pong":
        pass  # heartbeat already tracked by TimeoutError counter

    elif msg_type == "chat.message":
        await _handle_chat_message(websocket, tenant_id, conn_id, user_id, msg)

    elif msg_type == "chat.typing":
        await _handle_typing(websocket, tenant_id, conn_id, user_id, msg)

    elif msg_type == "chat.quick_reply":
        await _handle_quick_reply(websocket, tenant_id, conn_id, user_id, msg)

    else:
        await websocket.send_text(_err("unknown_type", f"Unknown message type: {msg_type}"))


# ── Message handlers ─────────────────────────────────────────

async def _handle_chat_message(websocket: WebSocket, tenant_id: uuid.UUID, conn_id: str, user_id: str, msg: dict):
    """Handle incoming chat message from widget."""
    conversation_id = msg.get("conversation_id")
    text = msg.get("text", "").strip()
    message_id = msg.get("message_id", uuid.uuid4().hex)

    if not text:
        await websocket.send_text(_err("invalid_message", "text is required"))
        return

    # Persist message asynchronously
    async with async_session_factory() as db:
        try:
            from app.models.conversations import Conversation, Message
            from sqlalchemy import select

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
                content=text,
            )
            db.add(db_msg)
            await db.commit()
            await db.refresh(db_msg)

            # Ack to sender
            await websocket.send_text(json.dumps({
                "type": "chat.message_sent",
                "message_id": str(db_msg.id),
                "client_message_id": message_id,
                "timestamp": db_msg.created_at.isoformat(),
            }, ensure_ascii=False))

            # Route to AI for response generation (Stage 4)
            await _generate_ai_response(websocket, tenant_id, conversation_id, text, db_msg.id)

        except Exception as e:
            await db.rollback()
            await websocket.send_text(_err("persist_error", str(e)))


async def _generate_ai_response(
    websocket: WebSocket,
    tenant_id: uuid.UUID,
    conversation_id: str,
    user_text: str,
    user_message_id: uuid.UUID,
):
    """Stage 4: Route user message to AI core and stream response back."""
    try:
        from app.ai.manager import ai_manager

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
        await websocket.send_text(json.dumps({
            "type": "chat.typing",
            "conversation_id": conversation_id,
            "is_typing": True,
            "user_id": "ai",
            "user_name": "Aether AI",
            "timestamp": _ts(),
        }, ensure_ascii=False))

        # Generate AI response (streaming)
        full_response = ""
        async for chunk in ai_manager.generate_stream(
            messages=messages,
            system_prompt="You are a helpful business assistant. Be concise and friendly.",
            temperature=0.7,
            max_tokens=1024,
        ):
            full_response += chunk
            # Stream each chunk to the client
            await websocket.send_text(json.dumps({
                "type": "chat.message_chunk",
                "conversation_id": conversation_id,
                "chunk": chunk,
                "timestamp": _ts(),
            }, ensure_ascii=False))

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
            await websocket.send_text(json.dumps({
                "type": "chat.message",
                "message_id": str(ai_msg.id),
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": full_response,
                "timestamp": ai_msg.created_at.isoformat(),
            }, ensure_ascii=False))

            # Stop typing
            await websocket.send_text(json.dumps({
                "type": "chat.typing",
                "conversation_id": conversation_id,
                "is_typing": False,
                "user_id": "ai",
                "user_name": "Aether AI",
                "timestamp": _ts(),
            }, ensure_ascii=False))

    except Exception:
        logger.exception("AI response generation failed for tenant=%s conv=%s", tenant_id, conversation_id)
        await websocket.send_text(json.dumps({
            "type": "chat.message",
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "Sorry, I couldn't process your request right now. Please try again.",
            "error": True,
            "timestamp": _ts(),
        }, ensure_ascii=False))
    """Handle typing indicator."""
    conversation_id = msg.get("conversation_id")
    is_typing = msg.get("is_typing", False)
    user_name = msg.get("user_name", "")

    # Broadcast to other connections in same tenant
    # In real impl this would be conversation-scoped, not tenant-broadcast
    payload = json.dumps({
        "type": "chat.typing",
        "conversation_id": conversation_id,
        "user_id": user_id,
        "user_name": user_name,
        "is_typing": is_typing,
        "timestamp": _ts(),
    }, ensure_ascii=False)

    # Just ack for now (Stage 4: proper broadcast per-conversation)
    # await _broadcast(tenant_id, conn_id, payload)


async def _handle_quick_reply(websocket: WebSocket, tenant_id: uuid.UUID, conn_id: str, user_id: str, msg: dict):
    """Handle quick reply button click from widget."""
    conversation_id = msg.get("conversation_id")
    reply_payload = msg.get("payload", "")

    if not conversation_id or not reply_payload:
        await websocket.send_text(_err("invalid_reply", "conversation_id and payload required"))
        return

    # Persist as a message with type=quick_reply
    async with async_session_factory() as db:
        try:
            from app.models.conversations import Message

            db_msg = Message(
                tenant_id=tenant_id,
                conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
                user_id=uuid.UUID(user_id),
                role="user",
                content=reply_payload,
                metadata={"type": "quick_reply"},
            )
            db.add(db_msg)
            await db.commit()
            await db.refresh(db_msg)

            await websocket.send_text(json.dumps({
                "type": "chat.quick_reply_ack",
                "message_id": str(db_msg.id),
                "timestamp": db_msg.created_at.isoformat(),
            }, ensure_ascii=False))

        except Exception as e:
            await db.rollback()
            await websocket.send_text(_err("persist_error", str(e)))
