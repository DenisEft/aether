"""Billing integration for WebSocket streaming AI responses.

Since streaming drivers (generate_stream) don't return token counts,
we estimate tokens from text length and record after stream completes.

Token estimation: 1 token ≈ 4 chars for mixed Russian/English text.
This is an approximation; actual billing precision comes from
non-streaming generate() which returns real token counts.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.services.billing_service import BillingService, QuotaExceededError

logger = logging.getLogger("aether.billing.streaming")


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    Rough heuristic: 1 token ≈ 4 characters for mixed Cyrillic/Latin text.
    Falls back to tiktoken if available, but this keeps zero dependencies.
    """
    if not text:
        return 0
    # Average: Russian chars are 1.5-2 tokens, English ≈ 1 token per 4 chars
    # We use a conservative 3.5 chars/token to slightly overestimate
    return max(1, len(text) // 3)


def estimate_prompt_tokens(messages: list[dict]) -> int:
    """Estimate total prompt tokens from a list of message dicts."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
    return total


class StreamingBillingTracker:
    """Tracks token usage during streaming AI responses.

    Usage (in ws.py or streaming endpoint):
        tracker = StreamingBillingTracker(session, tenant_id, user_id)
        await tracker.check_quota(messages)  # before streaming

        full_response = ""
        async for chunk in driver.generate_stream(...):
            full_response += chunk
            yield chunk

        await tracker.record(full_response, model, driver_type)  # after streaming
    """

    def __init__(
        self,
        session,
        tenant_id: UUID,
        user_id: UUID | None = None,
        commit: bool = True,
    ):
        self.billing = BillingService(session)
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._commit = commit
        self._estimated_prompt_tokens: int = 0

    async def check_quota(self, messages: list[dict] | None = None) -> None:
        """Check if tenant has available tokens before streaming.

        Estimates prompt tokens from messages for a rough quota check.
        """
        if messages:
            self._estimated_prompt_tokens = estimate_prompt_tokens(messages)

        # Check with a small buffer — real count comes after stream
        estimated_total = self._estimated_prompt_tokens + 500  # buffer
        try:
            await self.billing.check_quota(self.tenant_id, "tokens", float(estimated_total))
        except QuotaExceededError as e:
            logger.warning(
                f"Streaming quota exceeded before start: tenant={self.tenant_id} "
                f"limit={e.limit} current={e.current}"
            )
            raise

    async def record(
        self,
        response_text: str,
        model: str = "unknown",
        driver_type: str = "unknown",
    ) -> None:
        """Record estimated token usage after streaming completes."""
        completion_tokens = estimate_tokens(response_text)
        self._estimated_prompt_tokens + completion_tokens

        try:
            await self.billing.record_tokens(
                tenant_id=self.tenant_id,
                prompt_tokens=self._estimated_prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
                driver_type=driver_type,
                commit=self._commit,
            )
            logger.debug(
                f"Streaming billing recorded: tenant={self.tenant_id} "
                f"prompt={self._estimated_prompt_tokens} completion={completion_tokens} "
                f"model={model} driver={driver_type}"
            )
        except Exception:
            # Don't block the response if usage recording fails
            logger.exception(f"Failed to record streaming token usage for tenant={self.tenant_id}")


async def check_streaming_quota(
    session,
    tenant_id: UUID,
    estimated_tokens: int = 500,
) -> bool:
    """Quick pre-stream quota check. Returns True if OK, False if exceeded."""
    billing = BillingService(session)
    try:
        await billing.check_quota(tenant_id, "tokens", float(estimated_tokens))
        return True
    except QuotaExceededError:
        return False
