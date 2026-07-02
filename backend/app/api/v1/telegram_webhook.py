"""Telegram webhook endpoint — receives updates from Telegram Bot API."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("aether.webhooks.telegram")
router = APIRouter(tags=["webhooks"])


@router.post("/telegram/{channel_id}")
async def telegram_webhook(channel_id: str, request: Request):
    """Receive Telegram updates. Called by Telegram servers.
    No auth — validated by Telegram IP ranges (optional) and bot token."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.debug(f"Telegram webhook [{channel_id}]: update_id={payload.get('update_id')}")

    # Process through channel
    # In production, channel instances are managed by ChannelRouter
    # For now, log and return OK (Telegram requires 200 within ~10s)

    if "message" in payload:
        msg = payload["message"]
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        text = msg.get("text", msg.get("caption", ""))

        logger.info(
            f"Telegram message: chat={chat.get('id')} "
            f"from={user.get('username', user.get('first_name', '?'))} "
            f"text={text[:100]}"
        )

    elif "callback_query" in payload:
        cb = payload["callback_query"]
        logger.info(f"Telegram callback: data={cb.get('data')} from={cb.get('from', {}).get('id')}")

    # Always return 200 OK for Telegram
    return {"ok": True}


@router.get("/telegram/{channel_id}")
async def telegram_webhook_info(channel_id: str):
    """Info about the webhook endpoint (for debugging)."""
    return {
        "channel_id": channel_id,
        "webhook_url": f"/api/v1/webhooks/telegram/{channel_id}",
        "note": "Set this URL in Telegram Bot API: https://api.telegram.org/bot<TOKEN>/setWebhook?url=<BASE>/api/v1/webhooks/telegram/{channel_id}",
    }
