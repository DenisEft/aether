"""Telegram webhook — full AI funnel: receive → classify → generate → reply."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.manager import ai_manager
from app.config import settings
from app.database import get_db

logger = logging.getLogger("aether.webhooks.telegram")
router = APIRouter(tags=["webhooks"])


async def _send_telegram_message(
    chat_id: int,
    text: str,
    bot_token: str | None = None,
    reply_to_message_id: int | None = None,
) -> dict:
    """Send a message back to Telegram via Bot API."""
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not configured — cannot send reply")
        return {"ok": False, "error": "No bot token configured"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return {"ok": False, "error": str(e)}


async def _resolve_tenant_from_channel(channel_id: str, db: AsyncSession) -> str | None:
    """Look up tenant_id from channel configuration."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.channels import Channel

    # Try UUID lookup first
    try:
        channel_uuid = UUID(channel_id)
        result = await db.execute(select(Channel).where(Channel.id == channel_uuid))
        channel = result.scalars().first()
        if channel:
            logger.info(f"Resolved tenant={channel.tenant_id} from channel={channel_id}")
            return str(channel.tenant_id)
    except (ValueError, Exception):
        logger.debug(f"Channel ID '{channel_id}' is not a valid UUID, trying dev fallback")

    # Dev-mode fallback: if no channel found, try to find any active tenant for testing
    if settings.ENVIRONMENT == "development":
        try:
            from app.models.tenants import Tenant

            result = await db.execute(select(Tenant).limit(1))
            tenant = result.scalars().first()
            if tenant:
                logger.info(
                    f"Dev fallback: using tenant={tenant.id} for unknown channel={channel_id}"
                )
                return str(tenant.id)
        except Exception as e:
            logger.error(f"Dev fallback failed: {e}", exc_info=True)

    logger.warning(f"Could not resolve tenant for channel={channel_id}")
    return None


async def _get_or_create_conversation(
    tenant_id: str,
    channel_id: str,
    external_user_id: str,
    db: AsyncSession,
) -> str | None:
    """Find active conversation or create a new one. Returns conversation_id."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.conversations import Conversation

    # Try to parse channel_id as UUID; if not, skip channel filtering
    try:
        channel_uuid = UUID(channel_id)
    except ValueError:
        logger.debug(f"channel_id '{channel_id}' is not a UUID — using tenant-only lookup")
        # Look for any active conversation with this external user for this tenant
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == UUID(tenant_id),
                Conversation.external_user_id == external_user_id,
                Conversation.status == "active",
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conv = result.scalars().first()
        if conv:
            return str(conv.id)
        return None  # Can't create without valid channel UUID

    # Look for active conversation with this external user on this channel
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == UUID(tenant_id),
            Conversation.channel_id == channel_uuid,
            Conversation.external_user_id == external_user_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conv = result.scalars().first()
    if conv:
        return str(conv.id)

    # Create new conversation
    conv = Conversation(
        tenant_id=UUID(tenant_id),
        channel_id=channel_uuid,
        external_user_id=external_user_id,
        status="active",
    )
    db.add(conv)
    await db.flush()
    logger.info(f"New conversation created: {conv.id} for external_user={external_user_id}")
    return str(conv.id)


async def _save_message(
    tenant_id: str,
    conversation_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    entities: dict | None = None,
    tokens_used: int | None = None,
    db: AsyncSession | None = None,
) -> None:
    """Save a message to the conversation history.

    Uses db.add() + db.flush() only — caller is responsible for db.commit().
    This avoids interfering with the parent session lifecycle (Depends/get_session).
    """
    if not db:
        return
    from uuid import UUID

    from app.models.conversations import Message

    try:
        msg = Message(
            tenant_id=UUID(tenant_id),
            conversation_id=UUID(conversation_id),
            role=role,
            content=content,
            intent=intent,
            entities=entities or {},
            tokens_used=tokens_used,
        )
        db.add(msg)
        await db.flush()
        logger.debug(f"Message staged: role={role}, intent={intent}, len={len(content)}")
    except Exception as e:
        logger.error(f"Failed to stage message: {e}", exc_info=True)


# ── Core Webhook ──────────────────────────────────────────────


@router.post("/telegram/{channel_id}")
async def telegram_webhook(
    channel_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Receive Telegram update → run AI funnel → reply to user.

    Flow:
    1. Parse Telegram update (message or callback_query)
    2. Resolve tenant_id from channel config
    3. Run AIManager.process_incoming() — intent classify + AI generate
    4. Send AI response back to Telegram chat

    Telegram requires HTTP 200 within ~10 seconds.
    For long AI generations, we respond immediately and send the reply async.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    update_id = payload.get("update_id")
    logger.debug(f"Telegram webhook [{channel_id}]: update_id={update_id}")

    # ── Resolve tenant ───────────────────────────────────────
    try:
        tenant_id = await _resolve_tenant_from_channel(channel_id, db)
    except Exception as e:
        logger.warning(f"Failed to resolve tenant for channel={channel_id}: {e}")
        # Dev fallback: query any tenant directly
        if settings.ENVIRONMENT == "development":
            try:
                from sqlalchemy import select as sa_select

                from app.models.tenants import Tenant

                result = await db.execute(sa_select(Tenant).limit(1))
                tenant = result.scalars().first()
                if tenant:
                    tenant_id = str(tenant.id)
                    logger.info(f"Emergency fallback: using tenant={tenant_id}")
                else:
                    tenant_id = None
            except Exception as e2:
                logger.error(f"Emergency fallback also failed: {e2}")
                tenant_id = None
        else:
            tenant_id = None
    if not tenant_id:
        logger.warning(f"Unknown channel {channel_id} — cannot resolve tenant")
        return {"ok": True, "warning": "unknown_channel"}

    # ── Handle message ───────────────────────────────────────
    if "message" in payload:
        msg = payload["message"]
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        text = msg.get("text", msg.get("caption", ""))
        message_id = msg.get("message_id")
        chat_id = chat.get("id")

        if not text or not chat_id:
            return {"ok": True, "note": "no_text"}

        external_user_id = str(user.get("id", chat_id))
        logger.info(
            f"Telegram message: chat={chat_id} "
            f"from=@{user.get('username', user.get('first_name', '?'))} "
            f"text={text[:100]}"
        )

        # ── Get or create conversation ───────────────────────
        conversation_id = await _get_or_create_conversation(
            tenant_id=tenant_id,
            channel_id=channel_id,
            external_user_id=external_user_id,
            db=db,
        )

        # ── Save user message (skip if no conversation yet) ──
        if conversation_id:
            await _save_message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                role="user",
                content=text,
                db=db,
            )

        # ── Run AI Funnel ────────────────────────────────────
        try:
            result = await ai_manager.process_incoming(
                text=text,
                tenant_id=tenant_id,
                channel_type="telegram",
                db=db,
                user_context={
                    "username": user.get("username", ""),
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "user_id": str(user.get("id", "")),
                },
            )

            # ── Send AI reply ─────────────────────────────────
            response_text = result.get("response_text", "")
            if response_text:
                # Truncate to Telegram's 4096 char limit
                if len(response_text) > 4000:
                    response_text = response_text[:4000] + "…"

                # ── Save AI response to conversation ──────────
                if conversation_id:
                    await _save_message(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=response_text,
                        intent=result.get("intent_name"),
                        entities=result.get("entities"),
                        tokens_used=result.get("tokens_used"),
                        db=db,
                    )

                send_result = await _send_telegram_message(
                    chat_id=chat_id,
                    text=response_text,
                    reply_to_message_id=message_id,
                )
                logger.info(
                    f"AI reply sent: chat={chat_id}, "
                    f"intent={result.get('intent_name')}, "
                    f"model={result.get('model_used')}, "
                    f"telegram_ok={send_result.get('ok')}"
                )
            else:
                logger.warning(f"Empty AI response for chat={chat_id}")

        except Exception as e:
            logger.error(f"AI funnel failed for chat={chat_id}: {e}", exc_info=True)
            # Send fallback message
            await _send_telegram_message(
                chat_id=chat_id,
                text="Извините, произошла ошибка при обработке сообщения. Попробуйте позже.",
                reply_to_message_id=message_id,
            )

    # ── Handle callback query (inline buttons) ────────────────
    elif "callback_query" in payload:
        cb = payload["callback_query"]
        cb_data = cb.get("data", "")
        cb_chat_id = cb.get("message", {}).get("chat", {}).get("id")
        cb_user = cb.get("from", {})

        logger.info(
            f"Telegram callback: data={cb_data} "
            f"from=@{cb_user.get('username', cb_user.get('id'))}"
        )

        if cb_chat_id and cb_data:
            try:
                result = await ai_manager.process_incoming(
                    text=cb_data,
                    tenant_id=tenant_id,
                    channel_type="telegram",
                    db=db,
                    user_context={"user_id": str(cb_user.get("id", ""))},
                )
                if result.get("response_text"):
                    await _send_telegram_message(
                        chat_id=cb_chat_id,
                        text=result["response_text"][:4000],
                    )
            except Exception as e:
                logger.error(f"Callback AI funnel failed: {e}", exc_info=True)

    # ── Final commit: flush all staged messages in one transaction ─────
    try:
        await db.commit()
    except Exception as e:
        logger.warning(f"Final commit failed (non-fatal): {e}")

    # Always return 200 OK for Telegram
    return {"ok": True}


@router.get("/telegram/{channel_id}")
async def telegram_webhook_info(channel_id: str):
    """Debug info for the webhook endpoint."""
    return {
        "channel_id": channel_id,
        "webhook_url": f"/api/v1/webhooks/telegram/{channel_id}",
        "note": (
            "Set webhook via Telegram Bot API:\n"
            f"  https://api.telegram.org/bot<TOKEN>/setWebhook?"
            f"url=<BASE_URL>/api/v1/webhooks/telegram/{channel_id}"
        ),
        "bot_token_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "funnel": "intent_classify → entity_extract → ai_generate → telegram_reply",
    }
