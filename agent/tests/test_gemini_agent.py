"""Unit tests for the Gemini-powered VehicleAgent and helper functions.

Tests cover content building from history, response extraction helpers,
event factory functions, and the full chat() loop for text-only,
tool-call, and max-turn-limit scenarios.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vehicle_agent.gemini_agent import (
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_TEXT_CHUNK,
    EVENT_TOOL_CALL,
    EVENT_TOOL_RESULT,
    VehicleAgent,
    _build_contents,
    _done_event,
    _error_event,
    _extract_candidate,
    _extract_function_calls,
    _extract_text,
    _text_event,
    _tool_call_event,
)


# ---------------------------------------------------------------------------
# Helpers: build fake Gemini response objects
# ---------------------------------------------------------------------------
def _make_candidate(
    text: str | None = None,
    function_calls: list[tuple[str, dict]] | None = None,
) -> MagicMock:
    """Create a fake Gemini Candidate with text or function_call parts.

    Args:
        text: Optional text to include in a text part.
        function_calls: List of (name, args) tuples for function call parts.

    Returns:
        MagicMock resembling google.genai.types.Candidate.
    """
    candidate = MagicMock()
    parts = []

    if text is not None:
        part = MagicMock()
        part.text = text
        part.function_call = None
        parts.append(part)

    for name, args in (function_calls or []):
        part = MagicMock()
        part.text = None
        fc = MagicMock()
        fc.name = name
        fc.args = args
        part.function_call = fc
        parts.append(part)

    if parts:
        candidate.content = MagicMock()
        candidate.content.parts = parts
    else:
        candidate.content = MagicMock()
        candidate.content.parts = []

    return candidate


def _make_response(candidate: MagicMock | None = None) -> MagicMock:
    """Create a fake GenerateContentResponse.

    Args:
        candidate: The single candidate to include, or None for empty response.

    Returns:
        MagicMock resembling google.genai.types.GenerateContentResponse.
    """
    response = MagicMock()
    response.candidates = [candidate] if candidate is not None else []
    return response


# ===================================================================
# _build_contents
# ===================================================================
class TestBuildContents:
    """Tests for ``_build_contents`` helper."""

    def test_empty_history_single_user_message(self) -> None:
        """Empty history produces a single user Content object."""
        contents = _build_contents([], "What is the speed?")
        assert len(contents) == 1
        assert contents[0].role == "user"

    def test_user_history_role_mapping(self) -> None:
        """History with role='user' maps to Gemini role='user'."""
        history = [{"role": "user", "content": "Hello"}]
        contents = _build_contents(history, "Follow up")
        assert contents[0].role == "user"

    def test_assistant_history_role_mapping(self) -> None:
        """History with role='assistant' maps to Gemini role='model'."""
        history = [{"role": "assistant", "content": "Hi there"}]
        contents = _build_contents(history, "Thanks")
        assert contents[0].role == "model"

    def test_history_plus_new_message_count(self) -> None:
        """History of two turns plus new message produces three Content objects."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        contents = _build_contents(history, "New question")
        assert len(contents) == 3

    def test_new_message_appended_last(self) -> None:
        """The new user message is always the last Content object."""
        history = [{"role": "user", "content": "Previous"}]
        contents = _build_contents(history, "Current message")
        assert contents[-1].role == "user"

    def test_text_part_content_is_set(self) -> None:
        """Each Content object has at least one text Part."""
        contents = _build_contents([], "Hello")
        assert contents[0].parts  # non-empty


# ===================================================================
# _extract_candidate
# ===================================================================
class TestExtractCandidate:
    """Tests for ``_extract_candidate`` helper."""

    def test_returns_first_candidate(self) -> None:
        """First candidate is returned when response has candidates."""
        candidate = _make_candidate(text="Hello")
        response = _make_response(candidate)
        result = _extract_candidate(response)
        assert result is candidate

    def test_returns_none_for_empty_candidates(self) -> None:
        """Returns None when the response has no candidates."""
        response = _make_response(candidate=None)
        result = _extract_candidate(response)
        assert result is None


# ===================================================================
# _extract_function_calls
# ===================================================================
class TestExtractFunctionCalls:
    """Tests for ``_extract_function_calls`` helper."""

    def test_empty_when_no_function_calls(self) -> None:
        """Returns empty list when candidate has only text parts."""
        candidate = _make_candidate(text="Some text")
        calls = _extract_function_calls(candidate)
        assert calls == []

    def test_extracts_single_function_call(self) -> None:
        """A single function_call part is returned as a one-element list."""
        candidate = _make_candidate(
            function_calls=[("get_vehicle_signal", {"path": "Vehicle.Speed"})]
        )
        calls = _extract_function_calls(candidate)
        assert len(calls) == 1
        assert calls[0].name == "get_vehicle_signal"

    def test_extracts_multiple_function_calls(self) -> None:
        """Multiple function_call parts are all returned."""
        candidate = _make_candidate(
            function_calls=[
                ("get_vehicle_signal", {"path": "Vehicle.Speed"}),
                ("diagnose_dtc", {}),
            ]
        )
        calls = _extract_function_calls(candidate)
        assert len(calls) == 2

    def test_empty_when_no_parts(self) -> None:
        """Returns empty list when candidate content has no parts."""
        candidate = MagicMock()
        candidate.content = MagicMock()
        candidate.content.parts = []
        calls = _extract_function_calls(candidate)
        assert calls == []


# ===================================================================
# _extract_text
# ===================================================================
class TestExtractText:
    """Tests for ``_extract_text`` helper."""

    def test_extracts_single_text_part(self) -> None:
        """A single text part is returned as-is."""
        candidate = _make_candidate(text="Hello, world!")
        text = _extract_text(candidate)
        assert text == "Hello, world!"

    def test_concatenates_multiple_text_parts(self) -> None:
        """Multiple text parts are concatenated without separator."""
        candidate = MagicMock()
        part_a = MagicMock()
        part_a.text = "Hello"
        part_b = MagicMock()
        part_b.text = " World"
        candidate.content = MagicMock()
        candidate.content.parts = [part_a, part_b]
        text = _extract_text(candidate)
        assert text == "Hello World"

    def test_empty_string_when_no_text_parts(self) -> None:
        """Returns empty string when candidate has no text parts."""
        candidate = _make_candidate(
            function_calls=[("diagnose_dtc", {})]
        )
        text = _extract_text(candidate)
        assert text == ""


# ===================================================================
# Event factory functions
# ===================================================================
class TestEventFactories:
    """Tests for event factory helper functions."""

    def test_tool_call_event_structure(self) -> None:
        """_tool_call_event returns dict with correct keys and type."""
        event = _tool_call_event("get_vehicle_signal", {"path": "Vehicle.Speed"})
        assert event["type"] == EVENT_TOOL_CALL
        assert event["name"] == "get_vehicle_signal"
        assert event["args"] == {"path": "Vehicle.Speed"}

    def test_text_event_structure(self) -> None:
        """_text_event returns dict with correct type and content."""
        event = _text_event("The speed is 65 km/h")
        assert event["type"] == EVENT_TEXT_CHUNK
        assert event["content"] == "The speed is 65 km/h"

    def test_error_event_structure(self) -> None:
        """_error_event returns dict with correct type and message."""
        event = _error_event("Something went wrong")
        assert event["type"] == EVENT_ERROR
        assert event["message"] == "Something went wrong"

    def test_done_event_structure(self) -> None:
        """_done_event returns dict with type='done'."""
        event = _done_event()
        assert event["type"] == EVENT_DONE
        assert len(event) == 1  # only 'type' key

    def test_tool_call_event_with_empty_args(self) -> None:
        """_tool_call_event handles empty args dict."""
        event = _tool_call_event("diagnose_dtc", {})
        assert event["args"] == {}


# ===================================================================
# VehicleAgent.chat — text-only response
# ===================================================================
class TestVehicleAgentChatTextOnly:
    """Tests for VehicleAgent.chat with a text-only Gemini response."""

    async def test_text_only_yields_text_chunk_and_done(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """Text-only response yields text_chunk then done events."""
        candidate = _make_candidate(text="Speed is 65 km/h")
        response = _make_response(candidate)

        with patch("vehicle_agent.gemini_agent.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(return_value=response)

            events = []
            async for event in agent.chat("What is the speed?", []):
                events.append(event)

        types_seen = [e["type"] for e in events]
        assert EVENT_TEXT_CHUNK in types_seen
        assert EVENT_DONE in types_seen
        text_event = next(e for e in events if e["type"] == EVENT_TEXT_CHUNK)
        assert "65 km/h" in text_event["content"]

    async def test_no_candidates_yields_error_and_done(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """Empty candidates list yields error event then done event."""
        response = _make_response(candidate=None)

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(return_value=response)

            events = []
            async for event in agent.chat("Test", []):
                events.append(event)

        types_seen = [e["type"] for e in events]
        assert EVENT_ERROR in types_seen
        assert EVENT_DONE in types_seen

    async def test_gemini_api_exception_yields_error(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """An exception from _generate yields an error event and done."""
        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(side_effect=RuntimeError("API unavailable"))

            events = []
            async for event in agent.chat("Test", []):
                events.append(event)

        types_seen = [e["type"] for e in events]
        assert EVENT_ERROR in types_seen
        assert EVENT_DONE in types_seen
        error_event = next(e for e in events if e["type"] == EVENT_ERROR)
        assert "API unavailable" in error_event["message"]


# ===================================================================
# VehicleAgent.chat — tool call then text response
# ===================================================================
class TestVehicleAgentChatWithToolCall:
    """Tests for VehicleAgent.chat with one tool call followed by text."""

    async def test_tool_call_yields_tool_events_then_text(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """Tool call followed by text response yields tool_call, tool_result, text_chunk, done."""
        tool_candidate = _make_candidate(
            function_calls=[("get_vehicle_signal", {"path": "Vehicle.Speed"})]
        )
        # tool_candidate.content needs to be appendable
        tool_candidate.content.role = "model"

        text_candidate = _make_candidate(text="The speed is 65 km/h.")

        tool_response = _make_response(tool_candidate)
        text_response = _make_response(text_candidate)

        mock_mcp_bridge.call_tool.return_value = '{"value": 65.0}'

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            # First call returns tool response, second returns text
            agent._generate = AsyncMock(
                side_effect=[tool_response, text_response]
            )

            events = []
            async for event in agent.chat("What is the speed?", []):
                events.append(event)

        types_seen = [e["type"] for e in events]
        assert EVENT_TOOL_CALL in types_seen
        assert EVENT_TOOL_RESULT in types_seen
        assert EVENT_TEXT_CHUNK in types_seen
        assert EVENT_DONE in types_seen

    async def test_tool_call_invokes_mcp_bridge(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """chat() calls mcp_bridge.call_tool with correct name and args."""
        tool_candidate = _make_candidate(
            function_calls=[("diagnose_dtc", {})]
        )
        tool_candidate.content.role = "model"

        text_candidate = _make_candidate(text="No active DTCs found.")

        mock_mcp_bridge.call_tool.return_value = '{"dtcs": []}'

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(
                side_effect=[_make_response(tool_candidate), _make_response(text_candidate)]
            )

            async for _ in agent.chat("Check DTCs", []):
                pass

        mock_mcp_bridge.call_tool.assert_awaited_once_with("diagnose_dtc", {})

    async def test_failed_tool_call_yields_error_result(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """If call_tool raises, tool_result event contains error JSON."""
        tool_candidate = _make_candidate(
            function_calls=[("get_vehicle_signal", {"path": "Vehicle.Speed"})]
        )
        tool_candidate.content.role = "model"
        text_candidate = _make_candidate(text="Could not get speed.")

        mock_mcp_bridge.call_tool.side_effect = RuntimeError("connection refused")

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(
                side_effect=[_make_response(tool_candidate), _make_response(text_candidate)]
            )

            events = []
            async for event in agent.chat("Speed?", []):
                events.append(event)

        result_events = [e for e in events if e["type"] == EVENT_TOOL_RESULT]
        assert len(result_events) == 1
        assert "error" in result_events[0]["result"]


# ===================================================================
# VehicleAgent.chat — max tool calls limit
# ===================================================================
class TestVehicleAgentMaxToolCalls:
    """Tests for the max tool calls per turn limit."""

    async def test_max_tool_calls_yields_error(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """Exceeding max_tool_calls_per_turn yields an error event."""
        # max_tool_calls_per_turn is 5 in mock_config fixture
        # Always return a function_call so the loop never terminates naturally
        tool_candidate = _make_candidate(
            function_calls=[("get_vehicle_signal", {"path": "Vehicle.Speed"})]
        )
        tool_candidate.content.role = "model"
        mock_mcp_bridge.call_tool.return_value = '{"value": 65.0}'

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(
                return_value=_make_response(tool_candidate)
            )

            events = []
            async for event in agent.chat("Keep calling tools", []):
                events.append(event)

        types_seen = [e["type"] for e in events]
        assert EVENT_ERROR in types_seen
        error_event = next(e for e in events if e["type"] == EVENT_ERROR)
        assert "maximum tool calls" in error_event["message"]
        assert EVENT_DONE in types_seen

    async def test_max_tool_calls_count_equals_config(
        self, mock_mcp_bridge: AsyncMock, mock_config
    ) -> None:
        """The number of _generate calls equals max_tool_calls_per_turn."""
        tool_candidate = _make_candidate(
            function_calls=[("get_vehicle_signal", {"path": "Vehicle.Speed"})]
        )
        tool_candidate.content.role = "model"
        mock_mcp_bridge.call_tool.return_value = '{"value": 65.0}'

        with patch("vehicle_agent.gemini_agent.genai"):
            agent = VehicleAgent(mock_mcp_bridge, mock_config)
            agent._generate = AsyncMock(
                return_value=_make_response(tool_candidate)
            )

            async for _ in agent.chat("Spam tool calls", []):
                pass

        assert agent._generate.await_count == mock_config.max_tool_calls_per_turn
