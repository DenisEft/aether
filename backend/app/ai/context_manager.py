"""Context Manager — conversation context with Redis+PostgreSQL persistence.

Manages conversation history, auto-summarization for long dialogs,
and state machine for multi-step processes (form filling, booking).
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger("aether.ai.context_manager")


@dataclass
class ConversationContext:
    """Full conversation context for AI processing."""
    conversation_id: UUID
    tenant_id: UUID
    user_id: UUID | None
    channel_type: str
    messages: list[dict[str, str]] = field(default_factory=list)
    summary: str | None = None
    active_intent: dict | None = None
    collected_entities: dict[str, str] = field(default_factory=dict)
    state: dict = field(default_factory=dict)      # State machine state
    started_at: float = 0.0
    last_activity_at: float = 0.0
    message_count: int = 0
    token_count_estimate: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "conversation_id": str(self.conversation_id),
            "tenant_id": str(self.tenant_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "channel_type": self.channel_type,
            "messages": self.messages[-20:],  # Keep last 20 for serialization
            "summary": self.summary,
            "active_intent": self.active_intent,
            "collected_entities": self.collected_entities,
            "state": self.state,
            "last_activity_at": self.last_activity_at,
            "message_count": self.message_count,
            "token_count_estimate": self.token_count_estimate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        return cls(
            conversation_id=UUID(data["conversation_id"]),
            tenant_id=UUID(data["tenant_id"]),
            user_id=UUID(data["user_id"]) if data.get("user_id") else None,
            channel_type=data.get("channel_type", "unknown"),
            messages=data.get("messages", []),
            summary=data.get("summary"),
            active_intent=data.get("active_intent"),
            collected_entities=data.get("collected_entities", {}),
            state=data.get("state", {}),
            last_activity_at=data.get("last_activity_at", 0.0),
            message_count=data.get("message_count", 0),
            token_count_estimate=data.get("token_count_estimate", 0),
        )


class ContextManager:
    """Manages conversation context across Redis (fast) and PostgreSQL (durable).

    Usage:
        mgr = ContextManager(redis_client, session)
        ctx = await mgr.get_context(conversation_id, tenant_id)
        ctx = await mgr.append_message(ctx, {"role": "user", "content": "Hello"})
        await mgr.save_context(ctx)
    """

    # Context window limits per model tier
    DEFAULT_MAX_TOKENS = 4096
    MAX_CONTEXT_MESSAGES = 50
    SUMMARIZE_AT_MESSAGES = 30

    def __init__(self, redis_client, db_session_factory):
        self._redis = redis_client
        self._db_factory = db_session_factory
        self._context_cache: dict[str, ConversationContext] = {}

    def _cache_key(self, conversation_id: UUID) -> str:
        return f"aether:context:{conversation_id}"

    # ── Context Loading ──────────────────────────────────────

    async def get_context(
        self,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID | None = None,
        channel_type: str = "unknown",
        max_tokens: int | None = None,
    ) -> ConversationContext:
        """Load conversation context. Redis first, then PostgreSQL."""
        max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS

        # Try Redis cache
        if self._redis:
            try:
                key = self._cache_key(conversation_id)
                cached = await self._redis.get(key)
                if cached:
                    data = json.loads(cached)
                    ctx = ConversationContext.from_dict(data)
                    ctx.last_activity_at = datetime.now(timezone.utc).timestamp()
                    return ctx
            except Exception as e:
                logger.warning(f"Redis context load failed: {e}")

        # Try in-memory cache
        cache_key = str(conversation_id)
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        # Load from PostgreSQL
        ctx = await self._load_from_db(conversation_id, tenant_id, user_id, channel_type)

        # Trim to fit max_tokens
        ctx = self._trim_context(ctx, max_tokens)
        self._context_cache[cache_key] = ctx
        return ctx

    async def _load_from_db(
        self,
        conversation_id: UUID,
        tenant_id: UUID,
        user_id: UUID | None,
        channel_type: str,
    ) -> ConversationContext:
        """Load conversation history from PostgreSQL."""
        now = datetime.now(timezone.utc).timestamp()
        ctx = ConversationContext(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            channel_type=channel_type,
            started_at=now,
            last_activity_at=now,
        )

        try:
            async with self._db_factory() as db:
                from sqlalchemy import select
                from app.models.conversations import Message

                result = await db.execute(
                    select(Message)
                    .where(
                        Message.tenant_id == tenant_id,
                        Message.conversation_id == conversation_id,
                    )
                    .order_by(Message.created_at.asc())
                    .limit(self.MAX_CONTEXT_MESSAGES)
                )
                messages = result.scalars().all()

                for msg in messages:
                    ctx.messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })
                ctx.message_count = len(ctx.messages)
                ctx.token_count_estimate = self._estimate_tokens(ctx.messages)
        except Exception as e:
            logger.warning(f"DB context load failed: {e}")

        return ctx

    # ── Message Management ───────────────────────────────────

    async def append_message(
        self, context: ConversationContext, role: str, content: str
    ) -> ConversationContext:
        """Add a message to the context. Auto-trims if needed."""
        context.messages.append({"role": role, "content": content})
        context.message_count = len(context.messages)
        context.last_activity_at = datetime.now(timezone.utc).timestamp()
        context.token_count_estimate += self._estimate_tokens([{"role": role, "content": content}])

        # Auto-summarize for long conversations
        if context.message_count > self.SUMMARIZE_AT_MESSAGES:
            context = await self.summarize(context, keep_last_n=10)

        return context

    # ── Context Trimming ─────────────────────────────────────

    def _trim_context(
        self, context: ConversationContext, max_tokens: int
    ) -> ConversationContext:
        """Trim context to fit within max_tokens."""
        if context.token_count_estimate <= max_tokens:
            return context

        # Keep system message if present, trim oldest messages
        messages = context.messages
        if messages and messages[0].get("role") == "system":
            system_msg = [messages[0]]
            remaining = messages[1:]
        else:
            system_msg = []
            remaining = messages

        # Trim from the front
        while (
            self._estimate_tokens(system_msg + remaining) > max_tokens
            and len(remaining) > 2
        ):
            remaining.pop(0)

        context.messages = system_msg + remaining
        context.token_count_estimate = self._estimate_tokens(context.messages)
        return context

    async def summarize(
        self, context: ConversationContext, keep_last_n: int = 10
    ) -> ConversationContext:
        """Summarize conversation history, keeping last N messages."""
        if len(context.messages) <= keep_last_n:
            return context

        old_messages = context.messages[:-keep_last_n]
        recent_messages = context.messages[-keep_last_n:]

        # Simple truncation-based summary for now
        old_text = " ".join(
            m["content"] for m in old_messages if m.get("content")
        )
        # Truncate to reasonable summary length
        if len(old_text) > 500:
            old_text = old_text[:500] + "..."

        summary = (
            f"[Previous conversation summary: {len(old_messages)} messages. "
            f"Topics discussed: {old_text}]"
        )

        context.summary = summary
        context.messages = [
            {"role": "system", "content": summary},
            *recent_messages,
        ]
        context.token_count_estimate = self._estimate_tokens(context.messages)
        return context

    # ── State Machine ────────────────────────────────────────

    def get_state(self, context: ConversationContext) -> dict:
        """Get the current state machine state."""
        return context.state

    def update_state(
        self, context: ConversationContext, state_update: dict
    ) -> ConversationContext:
        """Update state machine state. Used by FormPlugin etc."""
        context.state.update(state_update)
        return context

    def clear_state(self, context: ConversationContext) -> None:
        """Clear the state machine state."""
        context.state.clear()

    # ── Persistence ──────────────────────────────────────────

    async def save_context(self, context: ConversationContext) -> None:
        """Persist context to Redis and in-memory cache."""
        context.last_activity_at = datetime.now(timezone.utc).timestamp()

        # In-memory cache
        cache_key = str(context.conversation_id)
        self._context_cache[cache_key] = context

        # Redis cache (with TTL)
        if self._redis:
            try:
                key = self._cache_key(context.conversation_id)
                data = json.dumps(context.to_dict(), default=str)
                await self._redis.setex(key, 3600, data)  # 1 hour TTL
            except Exception as e:
                logger.warning(f"Redis context save failed: {e}")

    async def expire_context(
        self, conversation_id: UUID, ttl_seconds: int = 3600
    ) -> None:
        """Set expiry for a conversation context (for inactive conversations)."""
        cache_key = str(conversation_id)
        if cache_key in self._context_cache:
            del self._context_cache[cache_key]
        if self._redis:
            try:
                await self._redis.expire(
                    self._cache_key(conversation_id), ttl_seconds
                )
            except Exception:
                pass

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, str]]) -> int:
        """Rough token estimation: 1 token ≈ 4 characters."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += max(1, len(content) // 4)
        return total
