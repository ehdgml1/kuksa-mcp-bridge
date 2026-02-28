"""Pydantic models for the Vehicle AI Agent HTTP API.

Defines request/response schemas and server-sent event types
used by the FastAPI endpoints.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the conversation history.

    Attributes:
        role: Message author role.
        content: Text content of the message.
    """

    role: Literal["user", "assistant"] = Field(
        description="Message author: 'user' or 'assistant'",
    )
    content: str = Field(
        description="Text content of the message",
    )


class ChatRequest(BaseModel):
    """Incoming chat request from the dashboard.

    Attributes:
        message: The new user message to process.
        history: Previous conversation turns for context.
    """

    message: str = Field(
        description="User message to send to the agent",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation turns for context",
    )


class AgentEvent(BaseModel):
    """Server-sent event emitted during agent processing.

    Each event carries a ``type`` discriminator and optional payload
    fields depending on the event kind.

    Attributes:
        type: Event discriminator.
        name: Tool name (for tool_call events).
        args: Tool arguments (for tool_call events).
        result: Tool execution result (for tool_result events).
        content: Text content (for text_chunk events).
        message: Error description (for error events).
    """

    type: Literal["tool_call", "tool_result", "text_chunk", "error", "done"] = Field(
        description="Event type discriminator",
    )
    name: str | None = Field(
        default=None,
        description="Tool name (tool_call events only)",
    )
    args: dict[str, Any] | None = Field(
        default=None,
        description="Tool arguments (tool_call events only)",
    )
    result: str | None = Field(
        default=None,
        description="Tool execution result (tool_result events only)",
    )
    content: str | None = Field(
        default=None,
        description="Text content (text_chunk events only)",
    )
    message: str | None = Field(
        default=None,
        description="Error description (error events only)",
    )


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Overall service status.
        mcp_connected: Whether the MCP bridge subprocess is alive.
        gemini_configured: Whether a Gemini API key is set.
    """

    status: str = Field(
        description="Overall service status",
    )
    mcp_connected: bool = Field(
        description="Whether the MCP bridge subprocess is alive",
    )
    gemini_configured: bool = Field(
        description="Whether a Gemini API key is configured",
    )
