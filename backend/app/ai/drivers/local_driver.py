"""Local LLM driver using llama.cpp server."""

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

logger = logging.getLogger("aether.ai.local_driver")


class LocalDriver(BaseDriver):
    """Driver for local LLM inference using llama.cpp server."""

    def __init__(self, model_id: str, base_url: str = "http://localhost:8080", **config):
        super().__init__(model_id, **config)
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._capabilities = [
            DriverCapability.CHAT,
            DriverCapability.COMPLETION,
            DriverCapability.EMBEDDING,
        ]

    @property
    def driver_type(self) -> str:
        return "local"

    def capabilities(self) -> list[DriverCapability]:
        return self._capabilities

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            if not self._client:
                return DriverHealth(status="error", message="Not initialized")

            resp = await self._client.get(f"{self.base_url}/health")
            if resp.status_code == 200:
                data = resp.json()
                return DriverHealth(
                    status="healthy" if data.get("status") == "ok" else "degraded",
                    latency_ms=resp.elapsed.total_seconds() * 1000,
                    message=data.get("status", ""),
                    error_count=0,
                )
            return DriverHealth(status="error", message=f"Status code: {resp.status_code}")
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        # Prepare prompt
        prompt = ""
        if request.system_prompt:
            prompt += f"<|system|>\n{request.system_prompt}\n"
        for msg in request.messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<|{role}|>\n{msg['content']}\n"
        prompt += "<|assistant|>\n"

        payload = {
            "prompt": prompt,
            "temperature": request.temperature or 0.7,
            "n_predict": request.max_tokens or 512,
            "stop": request.stop_sequences or ["<|end|>", "<|user|>"],
            "stream": False,
        }

        import time

        start = time.time()
        resp = await self._client.post(f"{self.base_url}/completion", json=payload)
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        content = data.get("content", "").replace("<|end|>", "").strip()
        tokens = data.get("tokens_evaluated", 0) + data.get("tokens_predicted", 0)

        result = InferenceResponse(
            model=self.model_id,
            driver_type=self.driver_type,
            content=content,
            finish_reason="stop",
            usage={
                "prompt_tokens": data.get("tokens_evaluated", 0),
                "completion_tokens": data.get("tokens_predicted", 0),
                "total_tokens": tokens,
            },
            latency_ms=elapsed_ms,
        )

        self.record_success(elapsed_ms, tokens)
        return result

    async def generate_stream(self, request: InferenceRequest):
        # Prepare prompt
        prompt = ""
        if request.system_prompt:
            prompt += f"<|system|>\n{request.system_prompt}\n"
        for msg in request.messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<|{role}|>\n{msg['content']}\n"
        prompt += "<|assistant|>\n"

        payload = {
            "prompt": prompt,
            "temperature": request.temperature or 0.7,
            "n_predict": request.max_tokens or 512,
            "stop": request.stop_sequences or ["<|end|>", "<|user|>"],
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST", f"{self.base_url}/completion", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            import json

                            chunk = json.loads(line[6:])
                            if "content" in chunk:
                                yield chunk["content"]
                        except Exception as exc:
                            logger.debug("Malformed local streaming chunk", exc_info=exc)
                            continue
        except Exception as e:
            self.record_failure(str(e))
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        # For embeddings, we need to implement a different endpoint
        # This is a placeholder - in real implementation would use the embedding endpoint
        try:
            # For now, return empty embeddings - you'd implement actual embedding here
            embeddings = [[0.0] * 1024] * len(request.texts)  # Dummy embeddings

            result = EmbeddingResponse(
                embeddings=embeddings,
                model=self.model_id,
                driver_type=self.driver_type,
                usage={"prompt_tokens": 0, "total_tokens": 0},
            )
            return result
        except Exception as e:
            error_msg = f"Embedding failed: {str(e)}"
            self.record_failure(error_msg)
            raise

    async def get_available_models(self) -> list[str]:
        # For now, return just our model
        return [self.model_id]

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
