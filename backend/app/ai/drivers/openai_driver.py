from typing import AsyncGenerator, Optional
import httpx
from loguru import logger
from .. import BaseDriver, DriverCapability, DriverHealth, DriverMetrics, InferenceRequest, InferenceResponse

class OpenAIDriver(BaseDriver):
    def __init__(self, model_id: str, api_key: str = "", base_url: str = "https://api.openai.com/v1"):
        super().__init__(model_id=model_id, api_key=api_key, base_url=base_url)
        self.api_key = api_key
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._last_health = DriverHealth(status="unknown")

    @property
    def driver_type(self) -> str: return "openai"

    def capabilities(self) -> list[DriverCapability]:
        return [DriverCapability.CHAT, DriverCapability.COMPLETION, DriverCapability.EMBEDDING]

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            resp = await self._client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
            if resp.status_code == 200:
                return DriverHealth(status="healthy", latency_ms=resp.elapsed.total_seconds()*1000)
            return DriverHealth(status="error", message=resp.text[:200])
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        # Build messages
        messages = [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 1024,
        }
        if request.stop_sequences: payload["stop"] = request.stop_sequences

        import time
        start = time.time()
        resp = await self._client.post(f"{self.base_url}/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        n = self._metrics.total_requests
        self._metrics.total_requests += 1
        self._metrics.total_tokens += usage.get("total_tokens", 0)
        self._metrics.avg_latency_ms = ((self._metrics.avg_latency_ms * n) + elapsed_ms) / (n + 1)
        import time as _time
        self._metrics.last_used_at = _time.time()

        return InferenceResponse(
            model=self.model_id,
            driver_type=self.driver_type,
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0), "total_tokens": usage.get("total_tokens", 0)},
            latency_ms=elapsed_ms,
        )

    async def infer_stream(self, request: InferenceRequest) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        for msg in request.messages: messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {"model": self.model_id, "messages": messages, "temperature": request.temperature or 0.7, "max_tokens": request.max_tokens or 1024, "stream": True}
        if request.stop_sequences: payload["stop"] = request.stop_sequences

        async with self._client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.api_key}"}) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]": break
                    try:
                        import json
                        delta = json.loads(chunk)["choices"][0].get("delta", {}).get("content", "")
                        if delta: yield delta
                    except Exception as exc:
                        logger.debug("Malformed OpenAI streaming chunk", exc_info=exc)
                        continue

    async def shutdown(self) -> None:
        if self._client: await self._client.aclose()

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
