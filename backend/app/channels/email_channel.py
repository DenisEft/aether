from typing import Optional, AsyncGenerator
import logging
import email
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib
from aioimaplib import IMAP4_SSL, aioimaplib

from .base import BaseChannel, ChannelConfig, ChannelStatus, MessageContext

logger = logging.getLogger("aether.channels.email")


class EmailChannel(BaseChannel):
    """Full IMAP/SMTP email channel: receive via IMAP IDLE, send via SMTP."""

    def __init__(self, config: ChannelConfig):
        super().__init__(config)
        self.imap_host = config.config.get("imap_host", "")
        self.imap_port = int(config.config.get("imap_port", 993))
        self.smtp_host = config.config.get("smtp_host", "")
        self.smtp_port = int(config.config.get("smtp_port", 587))
        self.email_address = config.config.get("email_address", "")
        self.email_password = config.config.get("email_password", "")
        self.use_tls = config.config.get("use_tls", True)
        self._imap: Optional[aioimaplib.IMAP4_SSL] = None
        self._idle_running = False

    async def initialize(self) -> bool:
        """Connect to IMAP and SMTP."""
        try:
            # IMAP connection
            self._imap = aioimaplib.IMAP4_SSL(
                host=self.imap_host,
                port=self.imap_port,
            )
            await self._imap.wait_hello_from_server()
            await self._imap.login(self.email_address, self.email_password)
            await self._imap.select("INBOX")
            self._status = ChannelStatus.CONNECTED
            logger.info(f"Email channel connected: {self.email_address} via IMAP {self.imap_host}:{self.imap_port}")
            return True
        except Exception as e:
            logger.error(f"Email channel init failed: {e}")
            self._status = ChannelStatus.ERROR
            return False

    async def check_health(self) -> bool:
        """Check IMAP connection."""
        if not self._imap:
            return False
        try:
            result = await self._imap.noop()
            return result.result == "OK"
        except Exception:
            return False

    async def send_message(
        self,
        chat_id: str,
        text: str,
        subject: str = "",
        html: bool = False,
        **kwargs,
    ) -> dict:
        """Send an email via SMTP."""
        try:
            message = MIMEMultipart("alternative")
            message["From"] = self.email_address
            message["To"] = chat_id
            message["Subject"] = subject or "New message from Aether"

            content_type = "html" if html else "plain"
            message.attach(MIMEText(text, content_type, "utf-8"))

            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=self.use_tls,
            ) as smtp:
                await smtp.login(self.email_address, self.email_password)
                await smtp.send_message(message)

            logger.info(f"Email sent: {self.email_address} → {chat_id}")
            return {"status": "sent", "to": chat_id, "subject": subject}
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"status": "error", "error": str(e)}

    async def poll_messages(self) -> AsyncGenerator[MessageContext, None]:
        """Poll IMAP for new messages with IDLE support."""
        if not self._imap:
            try:
                await self.initialize()
            except Exception:
                return

        self._idle_running = True

        while self._idle_running:
            try:
                # Search for unseen messages
                result = await self._imap.search("UNSEEN")
                if result.result == "OK" and result.lines:
                    msg_ids = result.lines[0].decode().split()
                    
                    for msg_id in msg_ids:
                        ctx = await self._fetch_message(int(msg_id))
                        if ctx:
                            # Mark as seen
                            await self._imap.store(str(msg_id), "+FLAGS", "\\Seen")
                            yield ctx

                # Wait for new messages (IDLE or polling)
                try:
                    idle_task = asyncio.create_task(self._imap.idle_start(timeout=30))
                    response = await self._imap.wait_server_push()
                    self._imap.idle_done()
                except Exception:
                    await asyncio.sleep(10)  # Fallback polling

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Email poll error: {e}")
                await asyncio.sleep(30)
                # Reconnect if needed
                try:
                    await self.initialize()
                except Exception:
                    pass

    async def _fetch_message(self, msg_id: int) -> Optional[MessageContext]:
        """Fetch and parse a single email message."""
        try:
            result = await self._imap.fetch(str(msg_id), "(RFC822)")
            if result.result != "OK":
                return None

            raw_email = result.lines[1]
            msg = email.message_from_bytes(raw_email)

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            return MessageContext(
                channel_type="email",
                channel_id=self.config.id,
                external_user_id=msg.get("From", ""),
                external_user_name=msg.get("From", ""),
                text=body[:4000],  # Truncate very long emails
                attachments=[],
                metadata={
                    "subject": msg.get("Subject", ""),
                    "message_id": msg.get("Message-ID", ""),
                    "date": msg.get("Date", ""),
                },
            )
        except Exception as e:
            logger.error(f"Email fetch error for msg {msg_id}: {e}")
            return None

    async def shutdown(self) -> None:
        """Close IMAP connection."""
        self._idle_running = False
        if self._imap:
            try:
                await self._imap.logout()
            except Exception:
                pass
            self._imap = None
        self._status = ChannelStatus.DISCONNECTED
