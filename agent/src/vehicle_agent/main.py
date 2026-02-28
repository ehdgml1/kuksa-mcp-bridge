"""FastAPI application for the Vehicle AI Agent.

Provides HTTP endpoints for the IVI dashboard to interact with
the Gemini-powered vehicle diagnostic agent. Chat responses are
streamed via Server-Sent Events (SSE) for real-time UI updates.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from vehicle_agent.config import AgentConfig, get_config
from vehicle_agent.gemini_agent import VehicleAgent
from vehicle_agent.mcp_bridge import McpBridge
from vehicle_agent.schemas import ChatRequest, HealthResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (initialised in lifespan)
# ---------------------------------------------------------------------------
_config: AgentConfig | None = None
_mcp_bridge: McpBridge | None = None
_agent: VehicleAgent | None = None


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown of the MCP bridge and agent.

    On startup: validates Gemini API key, connects the MCP bridge,
    and creates the VehicleAgent instance. On shutdown: disconnects
    the MCP bridge cleanly.

    Args:
        app: The FastAPI application instance.

    Yields:
        None -- the lifespan context carries no additional state.
    """
    global _config, _mcp_bridge, _agent  # noqa: PLW0603

    _config = get_config()

    logging.basicConfig(
        level=getattr(logging, _config.agent_log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not _config.gemini_api_key:
        logger.error(
            "GEMINI_API_KEY not set! Agent will return 503 on chat requests."
        )

    _mcp_bridge = McpBridge(_config)

    try:
        await _mcp_bridge.connect()
        logger.info("MCP bridge connected at startup")
    except Exception:
        logger.error("Failed to connect MCP bridge at startup", exc_info=True)

    if _config.gemini_api_key:
        _agent = VehicleAgent(_mcp_bridge, _config)
        logger.info("VehicleAgent initialised with model=%s", _config.gemini_model)

    try:
        yield
    finally:
        if _mcp_bridge is not None:
            await _mcp_bridge.disconnect()
            logger.info("MCP bridge disconnected at shutdown")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Vehicle AI Agent",
    version="0.1.0",
    description="Gemini-powered vehicle diagnostics agent via MCP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=None)
async def chat(request: ChatRequest) -> StreamingResponse | JSONResponse:
    """Process a user chat message and stream agent events via SSE.

    Returns 503 if the Gemini API key is not configured.

    Args:
        request: Chat request with user message and conversation history.

    Returns:
        StreamingResponse with ``text/event-stream`` media type,
        or a 503 JSONResponse if the agent is unavailable.
    """
    if _agent is None or _config is None or not _config.gemini_api_key:
        return JSONResponse(
            status_code=503,
            content={"error": "GEMINI_API_KEY not configured"},
        )

    history = [msg.model_dump() for msg in request.history]

    return StreamingResponse(
        _event_stream(request.message, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health() -> HealthResponse:
    """Return the current health status of the agent server.

    Returns:
        HealthResponse with MCP connection and Gemini configuration status.
    """
    return HealthResponse(
        status="ok",
        mcp_connected=_mcp_bridge.is_connected if _mcp_bridge else False,
        gemini_configured=bool(_config and _config.gemini_api_key),
    )


# ---------------------------------------------------------------------------
# SSE stream helper
# ---------------------------------------------------------------------------
async def _event_stream(
    message: str,
    history: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted event strings from agent output.

    Each event is encoded as ``data: <json>\\n\\n`` following the SSE spec.

    Args:
        message: User message to process.
        history: Conversation history as list of role/content dicts.

    Yields:
        SSE-formatted strings for each agent event.
    """
    assert _agent is not None  # guarded by caller

    try:
        async for event in _agent.chat(message, history):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as exc:
        logger.error("Error during chat stream: %s", exc, exc_info=True)
        error_event = {"type": "error", "message": str(exc)}
        yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        done_event = {"type": "done"}
        yield f"data: {json.dumps(done_event)}\n\n"
