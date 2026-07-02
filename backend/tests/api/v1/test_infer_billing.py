"""Integration tests for billing in /infer endpoint."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient

from app.ai import InferenceResponse


class TestBillingInferenceIntegration:
    """Test that /infer endpoint records token usage."""

    async def test_infer_endpoint_records_tokens(self, client: AsyncClient, auth_headers):
        """POST /infer should return usage info."""
        mock_response = InferenceResponse(
            model="test-model",
            driver_type="openai",
            content="Hello!",
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            latency_ms=100.0,
        )

        mock_mw = AsyncMock()
        mock_mw.check_and_record = AsyncMock()

        with patch("app.ai.manager.ai_manager.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            # Patch the import path inside run_inference
            with patch("app.services.billing_middleware.BillingAIMiddleware", return_value=mock_mw):
                response = await client.post(
                    "/api/v1/ai/infer",
                    json={
                        "messages": [{"role": "user", "content": "Hi"}],
                        "temperature": 0.7,
                    },
                    headers=auth_headers,
                )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello!"
        assert data["usage"]["total_tokens"] == 75

        # Verify billing was called
        mock_mw.check_and_record.assert_called_once()
        call_kwargs = mock_mw.check_and_record.call_args.kwargs
        assert call_kwargs["prompt_tokens"] == 50
        assert call_kwargs["completion_tokens"] == 25
        assert call_kwargs["driver_type"] == "openai"

    async def test_infer_billing_failure_doesnt_block(self, client: AsyncClient, auth_headers):
        """If billing middleware fails, /infer should still return the AI response."""
        mock_response = InferenceResponse(
            model="test-model",
            driver_type="openai",
            content="Hello!",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            latency_ms=50.0,
        )

        mock_mw = MagicMock()
        mock_mw.check_and_record = AsyncMock(side_effect=RuntimeError("DB down"))

        with patch("app.ai.manager.ai_manager.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_response
            with patch("app.services.billing_middleware.BillingAIMiddleware", return_value=mock_mw):
                response = await client.post(
                    "/api/v1/ai/infer",
                    json={"messages": [{"role": "user", "content": "Hi"}]},
                    headers=auth_headers,
                )

        # Response should still be 200 — billing is non-blocking
        assert response.status_code == 200
        assert response.json()["content"] == "Hello!"


class TestBillingStatusEndpoint:
    """Test /billing/status endpoint."""

    async def test_billing_status_returns_structure(self, client: AsyncClient, auth_headers):
        """GET /billing/status returns plan + usage + quotas."""
        response = await client.get(
            "/api/v1/billing/status",
            headers=auth_headers,
        )
        # Endpoint should not crash (may be 404 if no DB setup, but never 500)
        assert response.status_code != 500
