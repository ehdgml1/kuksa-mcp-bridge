"""FastMCP server entry point for the Kuksa MCP Bridge.

Creates and configures the MCP server that bridges Eclipse Kuksa
Databroker vehicle data to AI assistants via the Model Context Protocol.
Manages the Kuksa gRPC client lifecycle and registers all tools,
resources, and prompts.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from kuksa_mcp.config import get_config
from kuksa_mcp.kuksa_client import KuksaClientWrapper
from kuksa_mcp.prompts import register_prompts
from kuksa_mcp.resources import register_resources
from kuksa_mcp.tools import register_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
config = get_config()

logging.basicConfig(
    level=getattr(logging, config.mcp_log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Shared Kuksa client (lazy-connecting via _ensure_connected)
# ---------------------------------------------------------------------------
kuksa_client = KuksaClientWrapper(
    host=config.kuksa_databroker_host,
    port=config.kuksa_databroker_port,
)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Manage the Kuksa client connection across the server lifecycle.

    Attempts to connect on startup and guarantees cleanup on shutdown.
    If the broker is not yet available, tools will lazy-reconnect on
    first invocation via ``KuksaClientWrapper._ensure_connected``.

    Args:
        server: The FastMCP server instance (unused but required by API).

    Yields:
        None -- the lifespan context carries no additional state.
    """
    logger.info(
        "Starting Kuksa MCP Bridge (broker=%s:%s)",
        config.kuksa_databroker_host,
        config.kuksa_databroker_port,
    )
    try:
        await kuksa_client.connect()
        logger.info("Kuksa Databroker connection established")
    except Exception:
        logger.warning(
            "Kuksa Databroker not available at startup; "
            "tools will attempt lazy reconnection on first call",
            exc_info=True,
        )

    try:
        yield
    finally:
        await kuksa_client.disconnect()
        logger.info("Kuksa MCP Bridge shut down")


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name=config.mcp_server_name,
    lifespan=app_lifespan,
)

# Register all tools, resources, and prompts
register_tools(mcp, kuksa_client)
register_resources(mcp, kuksa_client)
register_prompts(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Run the MCP server using stdio transport."""
    logger.info("Launching %s MCP server (stdio)", config.mcp_server_name)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
