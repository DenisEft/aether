from typing import AsyncGenerator, Optional
import httpx
from loguru import logger
from .. import BaseDriver, DriverCapability, DriverHealth, DriverMetrics, InferenceRequest, InferenceResponse

class LocalDriver(BaseDriver):
    def __init__(self, model_id: str, base_url: str = "http://localhost:8080"):
        super().__init__(model_id=model_id, base_url=base_url)
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._last_health = DriverHealth(status="unknown")

    @property
    def driver_type(self) -> str: return "local"

    def capabilities(self) -> list[DriverCapability]:
        return [DriverCapability.CHAT, DriverCapability.COMPLETION, DriverCapability.EMBEDDING]

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)
        self._last_health = await self.health_check()

    async def health_check(self) -> DriverHealth:
        try:
            resp = await self._client.get(f"{self.base_url}/health")
            if resp.status_code == 200:
                data = resp.json()
                return DriverHealth(status="healthy" if data.get("status") == "ok" else "degraded", latency_ms=resp.elapsed.total_seconds()*1000, message=data.get("status", ""))
            return DriverHealth(status="error")
        except Exception as e:
            return DriverHealth(status="error", message=str(e))

    async def infer(self, request: InferenceRequest) -> InferenceResponse:
        prompt = ""
        if request.system_prompt: prompt += f"<|system|>\n{request.system_prompt}</s>\n"
        for msg in request.messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<|{role}|>\n{msg['content']}</s>\n"
        prompt += "<|assistant|>\n"

        payload = {
            "prompt": prompt,
            "temperature": request.temperature or 0.7,
            "n_predict": request.max_tokens or 512,
            "stop": request.stop_sequences or ["</s>", "<|user|>"],
            "stream": False,
        }

        import time
        start = time.time()
        resp = await self._client.post(f"{self.base_url}/completion", json=payload)
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000

        data = resp.json()
        content = data.get("content", "").replace("</s>", "").strip()
        tokens = data.get("tokens_evaluated", 0) + data.get("tokens_predicted", 0)

        n = self._metrics.total_requests
        self._metrics.total_requests += 1
        self._metrics.total_tokens += tokens
        self._metrics.avg_latency_ms = ((self._metrics.avg_latency_ms * n) + elapsed_ms) / (n + 1)
        import time as _time
        self._metrics.last_used_at = _time.time()

        return InferenceResponse(model=self.model_id, driver_type=self.driver_type, content=content, finish_reason="stop", usage={"prompt_tokens": data.get("tokens_evaluated", 0), "completion_tokens": data.get("tokens_predicted", 0), "total_tokens": tokens}, latency_ms=elapsed_ms)

    async def infer_stream(self, request: InferenceRequest) -> AsyncGenerator[str, None]:
        prompt = ""
        if request.system_prompt: prompt += f"<|system|>\n{request.system_prompt}</s>\n"
        for msg in request.messages:
            role = "user" if msg["role"] == "user" else "assistant"
            prompt += f"<|{role}|>\n{msg['content']}</s>\n"
        prompt += "<|assistant|>\n"

        payload = {"prompt": prompt, "temperature": request.temperature or 0.7, "n_predict": request.max_tokens or 512, "stop": request.stop_sequences or ["</s>", "<|user|>"], "stream": True}

        async with self._client.stream("POST", f"{self.base_url}/completion", json=payload) as resp:
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

    async def shutdown(self) -> None:
        if self._client: await self._client.aclose()

    def get_metrics(self) -> DriverMetrics:
        return self._metrics
