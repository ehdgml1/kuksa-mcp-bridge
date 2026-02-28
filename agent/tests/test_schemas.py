"""Unit tests for Pydantic schemas used in the Vehicle AI Agent HTTP API.

Validates that ChatMessage, ChatRequest, AgentEvent, and HealthResponse
enforce their field constraints correctly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vehicle_agent.schemas import AgentEvent, ChatMessage, ChatRequest, HealthResponse


# ===================================================================
# ChatMessage
# ===================================================================
class TestChatMessage:
    """Tests for the ChatMessage model."""

    def test_valid_user_role(self) -> None:
        """ChatMessage with role='user' is accepted."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_valid_assistant_role(self) -> None:
        """ChatMessage with role='assistant' is accepted."""
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_invalid_role_raises_validation_error(self) -> None:
        """ChatMessage with an unrecognised role raises ValidationError."""
        with pytest.raises(ValidationError):
            ChatMessage(role="system", content="You are a bot")  # type: ignore[arg-type]

    def test_empty_content_is_allowed(self) -> None:
        """ChatMessage accepts empty string content."""
        msg = ChatMessage(role="user", content="")
        assert msg.content == ""

    @pytest.mark.parametrize("role", ["user", "assistant"])
    def test_parametrized_valid_roles(self, role: str) -> None:
        """Both valid roles are accepted by ChatMessage."""
        msg = ChatMessage(role=role, content="test")  # type: ignore[arg-type]
        assert msg.role == role


# ===================================================================
# ChatRequest
# ===================================================================
class TestChatRequest:
    """Tests for the ChatRequest model."""

    def test_message_only_no_history(self) -> None:
        """ChatRequest with only a message defaults history to empty list."""
        req = ChatRequest(message="What is the vehicle speed?")
        assert req.message == "What is the vehicle speed?"
        assert req.history == []

    def test_with_history(self) -> None:
        """ChatRequest correctly stores provided conversation history."""
        history = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help?"),
        ]
        req = ChatRequest(message="Check speed", history=history)
        assert len(req.history) == 2
        assert req.history[0].role == "user"
        assert req.history[1].role == "assistant"

    def test_empty_message_is_allowed(self) -> None:
        """ChatRequest accepts an empty string message."""
        req = ChatRequest(message="")
        assert req.message == ""

    def test_missing_message_raises_validation_error(self) -> None:
        """ChatRequest without a message raises ValidationError."""
        with pytest.raises(ValidationError):
            ChatRequest()  # type: ignore[call-arg]

    def test_explicit_empty_history(self) -> None:
        """ChatRequest with explicit empty history list stores empty list."""
        req = ChatRequest(message="test", history=[])
        assert req.history == []


# ===================================================================
# AgentEvent
# ===================================================================
class TestAgentEvent:
    """Tests for the AgentEvent server-sent event model."""

    def test_tool_call_event(self) -> None:
        """tool_call event stores name and args."""
        event = AgentEvent(
            type="tool_call",
            name="get_vehicle_signal",
            args={"path": "Vehicle.Speed"},
        )
        assert event.type == "tool_call"
        assert event.name == "get_vehicle_signal"
        assert event.args == {"path": "Vehicle.Speed"}

    def test_tool_result_event(self) -> None:
        """tool_result event stores name and result."""
        event = AgentEvent(
            type="tool_result",
            name="get_vehicle_signal",
            result='{"value": 65.0}',
        )
        assert event.type == "tool_result"
        assert event.result == '{"value": 65.0}'

    def test_text_chunk_event(self) -> None:
        """text_chunk event stores content field."""
        event = AgentEvent(type="text_chunk", content="The current speed is 65 km/h.")
        assert event.type == "text_chunk"
        assert event.content == "The current speed is 65 km/h."

    def test_error_event(self) -> None:
        """error event stores message field."""
        event = AgentEvent(type="error", message="Gemini API unavailable")
        assert event.type == "error"
        assert event.message == "Gemini API unavailable"

    def test_done_event(self) -> None:
        """done event requires only the type field."""
        event = AgentEvent(type="done")
        assert event.type == "done"
        assert event.name is None
        assert event.args is None
        assert event.result is None
        assert event.content is None
        assert event.message is None

    def test_invalid_type_raises_validation_error(self) -> None:
        """AgentEvent with an unrecognised type raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentEvent(type="unknown_type")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "event_type",
        ["tool_call", "tool_result", "text_chunk", "error", "done"],
    )
    def test_all_valid_types_accepted(self, event_type: str) -> None:
        """All documented event types are accepted by AgentEvent."""
        event = AgentEvent(type=event_type)  # type: ignore[arg-type]
        assert event.type == event_type

    def test_optional_fields_default_to_none(self) -> None:
        """Unspecified optional fields default to None."""
        event = AgentEvent(type="done")
        assert event.name is None
        assert event.args is None
        assert event.result is None
        assert event.content is None
        assert event.message is None


# ===================================================================
# HealthResponse
# ===================================================================
class TestHealthResponse:
    """Tests for the HealthResponse model."""

    def test_healthy_all_ok(self) -> None:
        """HealthResponse with all systems up is valid."""
        resp = HealthResponse(
            status="ok",
            mcp_connected=True,
            gemini_configured=True,
        )
        assert resp.status == "ok"
        assert resp.mcp_connected is True
        assert resp.gemini_configured is True

    def test_degraded_no_api_key(self) -> None:
        """HealthResponse reflects missing Gemini API key."""
        resp = HealthResponse(
            status="ok",
            mcp_connected=True,
            gemini_configured=False,
        )
        assert resp.gemini_configured is False

    def test_degraded_mcp_disconnected(self) -> None:
        """HealthResponse reflects disconnected MCP bridge."""
        resp = HealthResponse(
            status="ok",
            mcp_connected=False,
            gemini_configured=True,
        )
        assert resp.mcp_connected is False

    def test_missing_required_field_raises(self) -> None:
        """HealthResponse raises ValidationError when required fields are absent."""
        with pytest.raises(ValidationError):
            HealthResponse(status="ok")  # type: ignore[call-arg]
