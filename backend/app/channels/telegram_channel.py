from collections.abc import AsyncGenerator

import httpx
from loguru import logger

from .base import BaseChannel, ChannelConfig, ChannelStatus, MessageContext


class TelegramChannel(BaseChannel):
    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.bot_token = config.config.get("bot_token", "")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._client: httpx.AsyncClient | None = None
        self._webhook_url: str | None = None
        self._offset = 0

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        await self._call("getMe")
        self._status = ChannelStatus.CONNECTED
        return True

    async def _call(self, method: str, params: dict = None) -> dict:
        resp = await self._client.post(f"{self.api_url}/{method}", json=params or {})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise Exception(f"Telegram API error: {data.get('description')}")
        return data.get("result", {})

    async def check_health(self) -> bool:
        try:
            await self._call("getMe")
            return True
        except Exception as exc:
            logger.error("Telegram health check failed", exc_info=exc)
            return False

    async def send_message(
        self, chat_id: str, text: str, parse_mode: str = "HTML", reply_markup: dict = None
    ) -> dict:
        params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            params["reply_markup"] = reply_markup
        return await self._call("sendMessage", params)

    async def send_photo(self, chat_id: str, photo_url: str, caption: str = "") -> dict:
        return await self._call(
            "sendPhoto", {"chat_id": chat_id, "photo": photo_url, "caption": caption}
        )

    async def send_file(self, chat_id: str, file_url: str, filename: str = "") -> dict:
        return await self._call(
            "sendDocument", {"chat_id": chat_id, "document": file_url, "caption": filename}
        )

    async def send_quick_replies(self, chat_id: str, text: str, buttons: list[str]) -> dict:
        keyboard = [[{"text": btn}] for btn in buttons]
        return await self.send_message(
            chat_id,
            text,
            reply_markup={
                "keyboard": keyboard,
                "resize_keyboard": True,
                "one_time_keyboard": True,
            },
        )

    async def set_webhook(self, url: str) -> bool:
        result = await self._call(
            "setWebhook", {"url": url, "allowed_updates": ["message", "callback_query"]}
        )
        if result:
            self._webhook_url = url
        return bool(result)

    async def delete_webhook(self) -> bool:
        return bool(await self._call("deleteWebhook"))

    async def get_updates(self, limit: int = 100, timeout: int = 30) -> list[dict]:
        updates = await self._call(
            "getUpdates", {"offset": self._offset, "limit": limit, "timeout": timeout}
        )
        if updates:
            self._offset = max(u["update_id"] for u in updates) + 1
        return updates or []

    async def poll_messages(self) -> AsyncGenerator[MessageContext, None]:
        if not self._client:
            await self.initialize()

        while True:
            try:
                updates = await self.get_updates(timeout=30)
                for update in updates:
                    if "message" not in update:
                        continue
                    msg = update["message"]
                    chat = msg.get("chat", {})
                    user = msg.get("from", {})

                    ctx = MessageContext(
                        channel_type="telegram",
                        channel_id=self.config.id,
                        external_user_id=str(chat.get("id", "")),
                        external_user_name=(
                            f"{user.get('first_name', '')} "
                            f"{user.get('last_name', '')}"
                        ).strip()
                        or user.get("username", "Unknown"),
                        text=msg.get("text", msg.get("caption", "")),
                        attachments=[msg["photo"][-1]["file_id"]] if "photo" in msg else [],
                        metadata={
                            "chat_type": chat.get("type"),
                            "chat_title": chat.get("title", ""),
                            "username": user.get("username", ""),
                            "message_id": msg.get("message_id"),
                        },
                    )
                    yield ctx
            except Exception as e:
                import asyncio
                import logging

                logging.getLogger("aether.channels.telegram").error(f"Poll error: {e}")
                await asyncio.sleep(5)

    async def listen_webhook(self, payload: dict) -> MessageContext | None:
        if "message" not in payload:
            return None

        msg = payload["message"]
        chat = msg.get("chat", {})
        user = msg.get("from", {})

        return MessageContext(
            channel_type="telegram",
            channel_id=self.config.id,
            external_user_id=str(chat.get("id", "")),
            external_user_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            text=msg.get("text", ""),
            attachments=[],
            metadata={"chat_type": chat.get("type"), "message_id": msg.get("message_id")},
        )

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
