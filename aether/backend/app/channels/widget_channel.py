from typing import Optional, AsyncGenerator
from .base import BaseChannel, ChannelConfig, ChannelStatus, MessageContext


class WidgetChannel(BaseChannel):
    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.primary_color = config.config.get("primary_color", "#1a73e8")
        self.position = config.config.get("position", "bottom-right")
        self.greeting = config.config.get("greeting", "Hi! How can we help?")
    
    async def initialize(self) -> None:
        self._status = ChannelStatus.CONNECTED
        return True
    
    async def check_health(self) -> bool:
        return True
    
    async def send_message(self, chat_id: str, text: str, **kwargs) -> dict:
        return {"type": "message", "content": text, "timestamp": __import__("datetime").datetime.utcnow().isoformat()}
    
    async def send_quick_replies(self, chat_id: str, text: str, buttons: list[str]) -> dict:
        return {"type": "quick_replies", "content": text, "buttons": buttons}
    
    async def send_typing(self, chat_id: str) -> dict:
        return {"type": "typing"}
    
    async def poll_messages(self) -> AsyncGenerator[MessageContext, None]:
        return
        yield  # Widget uses WebSocket, not polling
    
    async def shutdown(self) -> None:
        pass
