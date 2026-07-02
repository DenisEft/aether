"""Anthropic driver for AI inference."""

from __future__ import annotations

import logging

import httpx

from ..drivers.base import (
    BaseDriver,
    DriverCapability,
    DriverHealth,
    DriverMetrics,
    EmbeddingRequest,
    EmbeddingResponse,
    InferenceRequest,
    InferenceResponse,
)

logger = logging.getLogger("aether.ai.anthropic_driver")


class AnthropicDriver(BaseDriver):
    """Driver for Anthropic API inference."""

    def __init__(
        self,
        model_id: str,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com",
        **config,
    ):
        super().__init__(model_id, **config)
        self.api_key = api_key
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._capabilities = [DriverCapability.CHAT, DriverCapability.COMPLETION]

    @property
    def driver_type(self) -> str:
        return "anthropic"

    def capabilities(self) -> list[DriverCapability]:
        return self._capabilities

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            if not self._client:
                return DriverHealth(status="error", message="Not initialized")

            resp = await self._client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model_id,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
            if resp.status_code in (200, 429):
                return DriverHealth(
                    status="healthy", latency_ms=resp.elapsed.total_seconds() * 1000
                )
            return DriverHealth(status="error", message=f"Status code: {resp.status_code}")
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        messages = []
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model_id,
            "max_tokens": request.max_tokens or 1024,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        import time

        start = time.time()
        resp = await self._client.post(
            f"{self.base_url}/v1/messages",
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        content = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})

        result = InferenceResponse(
            model=self.model_id,
            driver_type=self.driver_type,
            content=content,
            finish_reason=data.get("stop_reason", "end_turn"),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            latency_ms=elapsed_ms,
        )

        self.record_success(
            elapsed_ms, usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        )
        return result

    async def generate_stream(self, request: InferenceRequest):
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in request.messages]
        payload = {
            "model": self.model_id,
            "max_tokens": request.max_tokens or 1024,
            "messages": messages,
            "stream": True,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.temperature:
            payload["temperature"] = request.temperature

        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        try:
                            import json

                            event = json.loads(chunk)
                            if event.get("type") == "content_block_delta":
                                yield event["delta"].get("text", "")
                        except Exception as exc:
                            logger.debug("Malformed Anthropic streaming chunk", exc_info=exc)
                            continue
        except Exception as e:
            self.record_failure(str(e))
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        # Anthropic doesn't support embeddings, return empty result
        try:
            result = EmbeddingResponse(
                embeddings=[], model=self.model_id, driver_type=self.driver_type, usage={}
            )
            return result
        except Exception as e:
            error_msg = f"Embedding not supported: {str(e)}"
            self.record_failure(error_msg)
            raise

    async def get_available_models(self) -> list[str]:
        try:
            # Get models from Anthropic API
            resp = await self._client.get(
                f"{self.base_url}/v1/models",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [model["id"] for model in data.get("data", [])]
            return []
        except Exception:
            return []

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
