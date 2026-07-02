from typing import AsyncGenerator, Optional
import httpx
from loguru import logger
from .. import BaseDriver, DriverCapability, DriverHealth, DriverMetrics, InferenceRequest, InferenceResponse

class AnthropicDriver(BaseDriver):
    def __init__(self, model_id: str, api_key: str = "", base_url: str = "https://api.anthropic.com"):
        super().__init__(model_id=model_id, api_key=api_key, base_url=base_url)
        self.api_key = api_key
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._last_health = DriverHealth(status="unknown")
        self.anthropic_version = "2023-06-01"

    @property
    def driver_type(self) -> str: return "anthropic"

    def capabilities(self) -> list[DriverCapability]:
        return [DriverCapability.CHAT, DriverCapability.COMPLETION]

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            resp = await self._client.post(f"{self.base_url}/v1/messages", headers={"x-api-key": self.api_key, "anthropic-version": self.anthropic_version, "content-type": "application/json"}, json={"model": self.model_id, "max_tokens": 10, "messages": [{"role": "user", "content": "ping"}]})
            if resp.status_code in (200, 429):
                return DriverHealth(status="healthy", latency_ms=resp.elapsed.total_seconds()*1000)
            return DriverHealth(status="error", message=resp.text[:200])
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        messages = []
        for msg in request.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model_id,
            "max_tokens": request.max_tokens or 1024,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.system_prompt: payload["system"] = request.system_prompt

        import time
        start = time.time()
        resp = await self._client.post(f"{self.base_url}/v1/messages", json=payload, headers={"x-api-key": self.api_key, "anthropic-version": self.anthropic_version, "content-type": "application/json"})
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        content = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage", {})

        n = self._metrics.total_requests
        self._metrics.total_requests += 1
        self._metrics.total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        self._metrics.avg_latency_ms = ((self._metrics.avg_latency_ms * n) + elapsed_ms) / (n + 1)
        import time as _time
        self._metrics.last_used_at = _time.time()

        return InferenceResponse(model=self.model_id, driver_type=self.driver_type, content=content, finish_reason=data.get("stop_reason", "end_turn"), usage={"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0), "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)}, latency_ms=elapsed_ms)

    async def infer_stream(self, request: InferenceRequest) -> AsyncGenerator[str, None]:
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in request.messages]
        payload = {"model": self.model_id, "max_tokens": request.max_tokens or 1024, "messages": messages, "stream": True}
        if request.system_prompt: payload["system"] = request.system_prompt
        if request.temperature: payload["temperature"] = request.temperature

        async with self._client.stream("POST", f"{self.base_url}/v1/messages", json=payload, headers={"x-api-key": self.api_key, "anthropic-version": self.anthropic_version, "content-type": "application/json"}) as resp:
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

    async def shutdown(self) -> None:
        if self._client: await self._client.aclose()

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
