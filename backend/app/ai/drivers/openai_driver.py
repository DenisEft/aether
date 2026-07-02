"""OpenAI driver for AI inference."""

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

logger = logging.getLogger("aether.ai.openai_driver")


class OpenAIDriver(BaseDriver):
    """Driver for OpenAI API inference."""

    def __init__(
        self,
        model_id: str,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        **config,
    ):
        super().__init__(model_id, **config)
        self.api_key = api_key
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._capabilities = [
            DriverCapability.CHAT,
            DriverCapability.COMPLETION,
            DriverCapability.EMBEDDING,
        ]

    @property
    def driver_type(self) -> str:
        return "openai"

    def capabilities(self) -> list[DriverCapability]:
        return self._capabilities

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            if not self._client:
                return DriverHealth(status="error", message="Not initialized")

            resp = await self._client.get(
                f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}
            )
            if resp.status_code == 200:
                return DriverHealth(
                    status="healthy", latency_ms=resp.elapsed.total_seconds() * 1000
                )
            return DriverHealth(status="error", message=f"Status code: {resp.status_code}")
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        # Build messages
        messages = (
            [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        )
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 1024,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        import time

        start = time.time()
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        result = InferenceResponse(
            model=self.model_id,
            driver_type=self.driver_type,
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency_ms=elapsed_ms,
        )

        self.record_success(elapsed_ms, usage.get("total_tokens", 0))
        return result

    async def generate_stream(self, request: InferenceRequest):
        messages = (
            [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        )
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 1024,
            "stream": True,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            import json

                            delta = (
                                json.loads(chunk)["choices"][0].get("delta", {}).get("content", "")
                            )
                            if delta:
                                yield delta
                        except Exception as exc:
                            logger.debug("Malformed OpenAI streaming chunk", exc_info=exc)
                            continue
        except Exception as e:
            self.record_failure(str(e))
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        try:
            payload = {
                "input": request.texts,
                "model": self.model_id,
                "encoding_format": request.encoding_format,
            }
            if request.dimensions:
                payload["dimensions"] = request.dimensions

            resp = await self._client.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()

            data = resp.json()

            result = EmbeddingResponse(
                embeddings=[e["embedding"] for e in data["data"]],
                model=self.model_id,
                driver_type=self.driver_type,
                usage=data.get("usage", {}),
            )
            return result
        except Exception as e:
            error_msg = f"Embedding failed: {str(e)}"
            self.record_failure(error_msg)
            raise

    async def get_available_models(self) -> list[str]:
        try:
            resp = await self._client.get(
                f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                return [model["id"] for model in data["data"]]
            return []
        except Exception:
            return []

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
