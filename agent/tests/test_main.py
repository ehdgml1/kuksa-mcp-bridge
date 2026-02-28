"""Integration tests for the FastAPI application endpoints.

Tests the /api/health and /api/chat endpoints using httpx.AsyncClient
with the app's ASGI interface, mocking the MCP bridge and agent to
avoid requiring live external services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from vehicle_agent.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _iter_events(*events: dict) -> None:
    """Async generator that yields dicts for agent event streaming.

    Args:
        events: Dicts to yield in order.

    Yields:
        Each dict in sequence.
    """
    for event in events:
        yield event


# ===================================================================
# /api/health
# ===================================================================
class TestHealthEndpoint:
    """Tests for GET /api/health."""

    async def test_health_returns_200(self) -> None:
        """GET /api/health returns HTTP 200 OK."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")
        assert response.status_code == 200

    async def test_health_response_schema(self) -> None:
        """GET /api/health response contains required fields."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

        body = response.json()
        assert "status" in body
        assert "mcp_connected" in body
        assert "gemini_configured" in body

    async def test_health_status_is_ok(self) -> None:
        """GET /api/health always returns status='ok' regardless of service health."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

        assert response.json()["status"] == "ok"

    async def test_health_gemini_configured_false_without_key(self) -> None:
        """gemini_configured is False when no API key is set in environment."""
        # The test environment has no real GEMINI_API_KEY; the app is started
        # without lifespan so _config remains None → gemini_configured=False
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

        # Without lifespan, _config is None → gemini_configured=False
        assert response.json()["gemini_configured"] is False

    async def test_health_mcp_connected_false_without_lifespan(self) -> None:
        """mcp_connected is False when app is tested without starting lifespan."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

        assert response.json()["mcp_connected"] is False


# ===================================================================
# /api/chat — 503 without API key
# ===================================================================
class TestChatEndpointNoApiKey:
    """Tests for POST /api/chat when no Gemini API key is configured."""

    async def test_chat_returns_503_without_api_key(self) -> None:
        """POST /api/chat returns 503 when no Gemini API key is set."""
        # Without lifespan, _agent is None → 503 is returned
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "What is the vehicle speed?"},
            )
        assert response.status_code == 503

    async def test_chat_503_body_contains_error_key(self) -> None:
        """POST /api/chat 503 response body contains an 'error' key."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "Hello"},
            )
        assert "error" in response.json()

    async def test_chat_503_mentions_api_key(self) -> None:
        """POST /api/chat 503 response body mentions GEMINI_API_KEY."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "Hello"},
            )
        assert "GEMINI_API_KEY" in response.json()["error"]

    async def test_chat_missing_message_returns_422(self) -> None:
        """POST /api/chat without a message field returns 422 Unprocessable Entity."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/chat", json={})
        assert response.status_code == 422


# ===================================================================
# /api/chat — streaming with injected agent
# ===================================================================
class TestChatEndpointWithAgent:
    """Tests for POST /api/chat with a mocked agent injected."""

    async def test_chat_streams_events_with_agent(self) -> None:
        """POST /api/chat with injected agent returns streaming SSE response."""
        import vehicle_agent.main as main_module

        mock_config = MagicMock()
        mock_config.gemini_api_key = "fake-key"

        mock_agent = MagicMock()
        mock_agent.chat = MagicMock(
            return_value=_iter_events(
                {"type": "text_chunk", "content": "Speed is 65 km/h"},
                {"type": "done"},
            )
        )

        original_config = main_module._config
        original_agent = main_module._agent

        try:
            main_module._config = mock_config  # type: ignore[assignment]
            main_module._agent = mock_agent  # type: ignore[assignment]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "What is the speed?"},
                )

            assert response.status_code == 200
        finally:
            main_module._config = original_config
            main_module._agent = original_agent

    async def test_chat_response_content_type_is_event_stream(self) -> None:
        """POST /api/chat with agent configured returns text/event-stream content type."""
        import vehicle_agent.main as main_module

        mock_config = MagicMock()
        mock_config.gemini_api_key = "fake-key"

        mock_agent = MagicMock()
        mock_agent.chat = MagicMock(
            return_value=_iter_events({"type": "done"})
        )

        original_config = main_module._config
        original_agent = main_module._agent

        try:
            main_module._config = mock_config  # type: ignore[assignment]
            main_module._agent = mock_agent  # type: ignore[assignment]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "Hello"},
                )

            assert "text/event-stream" in response.headers.get("content-type", "")
        finally:
            main_module._config = original_config
            main_module._agent = original_agent

    async def test_chat_sse_format_data_prefix(self) -> None:
        """Streamed events follow the SSE format: 'data: <json>\\n\\n'."""
        import vehicle_agent.main as main_module

        mock_config = MagicMock()
        mock_config.gemini_api_key = "fake-key"

        mock_agent = MagicMock()
        mock_agent.chat = MagicMock(
            return_value=_iter_events(
                {"type": "text_chunk", "content": "Hello"},
                {"type": "done"},
            )
        )

        original_config = main_module._config
        original_agent = main_module._agent

        try:
            main_module._config = mock_config  # type: ignore[assignment]
            main_module._agent = mock_agent  # type: ignore[assignment]

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json={"message": "Hi"},
                )

            body = response.text
            # SSE events must start with "data: "
            for line in body.strip().split("\n"):
                if line:
                    assert line.startswith("data: ")
        finally:
            main_module._config = original_config
            main_module._agent = original_agent
