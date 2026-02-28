"""Gemini-powered vehicle diagnostic agent with MCP tool calling.

Implements a ReAct-style agent loop that uses Google Gemini 2.0 Flash
for reasoning and the MCP bridge for executing vehicle data tools.
Yields streaming events for real-time UI updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from google import genai
from google.genai import types

from vehicle_agent.config import AgentConfig
from vehicle_agent.mcp_bridge import McpBridge
from vehicle_agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_TEXT_CHUNK = "text_chunk"
EVENT_ERROR = "error"
EVENT_DONE = "done"


class VehicleAgent:
    """Gemini 2.0 Flash agent with MCP tool calling for vehicle diagnostics.

    Processes user messages through a ReAct-style loop: the LLM decides
    whether to call tools or respond with text, and the agent executes
    tool calls via the MCP bridge until the model produces a final answer.

    Args:
        mcp_bridge: Connected MCP bridge for tool execution.
        config: Agent configuration with Gemini credentials and limits.
    """

    def __init__(self, mcp_bridge: McpBridge, config: AgentConfig) -> None:
        """Initialise the agent with MCP bridge and configuration.

        Args:
            mcp_bridge: Connected MCP bridge for tool execution.
            config: Agent configuration with Gemini model and API key.
        """
        self._mcp_bridge = mcp_bridge
        self._config = config
        self._client = genai.Client(api_key=config.gemini_api_key)

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process a user message and yield streaming agent events.

        Executes a ReAct loop:
        1. Build conversation contents from history + new message
        2. Call Gemini with tool declarations
        3. If function_call parts: execute tools, yield events, continue
        4. If text parts: yield text_chunk + done events, break

        Args:
            message: The new user message.
            history: Prior conversation turns (role + content dicts).

        Yields:
            AgentEvent-compatible dicts with type and payload fields.
        """
        contents = _build_contents(history, message)
        declarations = self._mcp_bridge.get_gemini_tool_declarations()

        for turn in range(self._config.max_tool_calls_per_turn):
            logger.info("Agent turn %d/%d", turn + 1, self._config.max_tool_calls_per_turn)

            try:
                response = await self._generate(contents, declarations)
            except Exception as exc:
                logger.error("Gemini API error: %s", exc)
                yield _error_event(f"Gemini API error: {exc}")
                yield _done_event()
                return

            candidate = _extract_candidate(response)
            if candidate is None:
                yield _error_event("No response from Gemini")
                yield _done_event()
                return

            function_calls = _extract_function_calls(candidate)

            if not function_calls:
                async for event in self._handle_text_response(candidate):
                    yield event
                return

            async for event in self._handle_tool_calls(
                contents, candidate, function_calls,
            ):
                yield event

        yield _error_event(
            f"Reached maximum tool calls ({self._config.max_tool_calls_per_turn})"
        )
        yield _done_event()

    async def _generate(
        self,
        contents: list[types.Content],
        declarations: list[dict[str, Any]],
    ) -> types.GenerateContentResponse:
        """Call the Gemini API with tool declarations.

        Args:
            contents: Conversation history as Gemini Content objects.
            declarations: Gemini function declarations from MCP tools.

        Returns:
            The Gemini generation response.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.models.generate_content(
                model=self._config.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=declarations)],
                    system_instruction=SYSTEM_PROMPT,
                ),
            ),
        )

    async def _handle_text_response(
        self,
        candidate: types.Candidate,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield text_chunk and done events from a text response.

        Args:
            candidate: Gemini response candidate containing text parts.

        Yields:
            text_chunk events for each text part, then a done event.
        """
        text = _extract_text(candidate)
        if text:
            yield _text_event(text)
        yield _done_event()

    async def _handle_tool_calls(
        self,
        contents: list[types.Content],
        candidate: types.Candidate,
        function_calls: list[types.FunctionCall],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute tool calls and append results to the conversation.

        Modifies ``contents`` in place to add the model's function call
        turn and the function response turn.

        Args:
            contents: Mutable conversation contents list.
            candidate: The candidate that produced the function calls.
            function_calls: Extracted function call parts.

        Yields:
            tool_call and tool_result events for each function call.
        """
        # Append the model's response (with function_call parts) to history
        contents.append(candidate.content)

        function_responses: list[types.Part] = []

        for fc in function_calls:
            args = dict(fc.args) if fc.args else {}
            yield _tool_call_event(fc.name, args)

            try:
                result_text = await self._mcp_bridge.call_tool(fc.name, args)
            except Exception as exc:
                logger.error("Tool '%s' execution failed: %s", fc.name, exc)
                result_text = json.dumps({"error": str(exc)})

            yield _tool_result_event(fc.name, result_text)

            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result_text},
                ),
            )

        # Append the tool results as a user turn
        contents.append(types.Content(role="user", parts=function_responses))


# ---------------------------------------------------------------------------
# Content building helpers
# ---------------------------------------------------------------------------
def _build_contents(
    history: list[dict[str, str]],
    message: str,
) -> list[types.Content]:
    """Build Gemini conversation contents from history and new message.

    Args:
        history: Prior conversation turns with ``role`` and ``content``.
        message: The new user message.

    Returns:
        List of Gemini Content objects.
    """
    contents: list[types.Content] = []

    for turn in history:
        role = turn.get("role", "user")
        text = turn.get("content", "")
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=text)],
            ),
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        ),
    )

    return contents


# ---------------------------------------------------------------------------
# Response extraction helpers
# ---------------------------------------------------------------------------
def _extract_candidate(
    response: types.GenerateContentResponse,
) -> types.Candidate | None:
    """Safely extract the first candidate from a Gemini response.

    Args:
        response: Gemini API response.

    Returns:
        The first candidate, or None if unavailable.
    """
    if not response.candidates:
        return None
    return response.candidates[0]


def _extract_function_calls(
    candidate: types.Candidate,
) -> list[types.FunctionCall]:
    """Extract all function_call parts from a candidate.

    Args:
        candidate: Gemini response candidate.

    Returns:
        List of FunctionCall objects found in the candidate's parts.
    """
    calls: list[types.FunctionCall] = []
    if candidate.content and candidate.content.parts:
        for part in candidate.content.parts:
            if part.function_call is not None:
                calls.append(part.function_call)
    return calls


def _extract_text(candidate: types.Candidate) -> str:
    """Extract concatenated text from a candidate's parts.

    Args:
        candidate: Gemini response candidate.

    Returns:
        Combined text from all text parts.
    """
    texts: list[str] = []
    if candidate.content and candidate.content.parts:
        for part in candidate.content.parts:
            if part.text:
                texts.append(part.text)
    return "".join(texts)


# ---------------------------------------------------------------------------
# Event factory helpers
# ---------------------------------------------------------------------------
def _tool_call_event(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Create a tool_call agent event.

    Args:
        name: Tool name being called.
        args: Arguments passed to the tool.

    Returns:
        AgentEvent-compatible dict.
    """
    return {"type": EVENT_TOOL_CALL, "name": name, "args": args}


def _tool_result_event(name: str, result: str) -> dict[str, Any]:
    """Create a tool_result agent event.

    Args:
        name: Tool name that produced the result.
        result: Text result from tool execution.

    Returns:
        AgentEvent-compatible dict.
    """
    return {"type": EVENT_TOOL_RESULT, "name": name, "result": result}


def _text_event(content: str) -> dict[str, Any]:
    """Create a text_chunk agent event.

    Args:
        content: Text content from the model.

    Returns:
        AgentEvent-compatible dict.
    """
    return {"type": EVENT_TEXT_CHUNK, "content": content}


def _error_event(message: str) -> dict[str, Any]:
    """Create an error agent event.

    Args:
        message: Error description.

    Returns:
        AgentEvent-compatible dict.
    """
    return {"type": EVENT_ERROR, "message": message}


def _done_event() -> dict[str, Any]:
    """Create a done agent event.

    Returns:
        AgentEvent-compatible dict signalling end of response.
    """
    return {"type": EVENT_DONE}
