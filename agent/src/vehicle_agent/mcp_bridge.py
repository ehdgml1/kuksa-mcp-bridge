"""MCP client bridge for the Vehicle AI Agent.

Manages a subprocess running the kuksa-mcp-bridge MCP server and
maintains a persistent MCP client session over stdio transport.
Converts MCP tool schemas into Gemini-compatible function declarations.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import Tool as McpTool

from vehicle_agent.config import AgentConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOOL_CACHE_KEY = "_cached_tools"


class McpBridgeError(Exception):
    """Raised when the MCP bridge encounters an unrecoverable error."""

    def __init__(self, detail: str = "MCP bridge error") -> None:
        """Initialise with a human-readable error detail.

        Args:
            detail: Description of the bridge failure.
        """
        self.detail = detail
        super().__init__(detail)


class McpBridge:
    """Manages MCP client connection to kuksa-mcp-bridge subprocess via stdio.

    Launches the MCP server as a child process, maintains the client
    session, caches tool definitions, and translates between MCP and
    Gemini function-calling schemas.

    Args:
        config: Agent configuration with MCP server launch parameters.
    """

    def __init__(self, config: AgentConfig) -> None:
        """Initialise the bridge with agent configuration.

        Args:
            config: Agent configuration containing MCP server command,
                arguments, working directory, and Kuksa connection details.
        """
        self._config = config
        self._session: ClientSession | None = None
        self._tools_cache: list[McpTool] | None = None
        self._background_task: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether the MCP session is active and the subprocess is alive."""
        return self._connected and self._session is not None

    async def connect(self) -> None:
        """Launch kuksa_mcp.server as subprocess and initialise MCP session.

        Sets up the stdio transport to the child process, creates a
        ``ClientSession``, calls ``initialize()``, and caches available
        tool definitions.

        Raises:
            McpBridgeError: If the subprocess cannot be started or the
                MCP handshake fails.
        """
        if self._connected:
            logger.warning("McpBridge.connect() called but already connected")
            return

        env = self._build_subprocess_env()
        server_params = StdioServerParameters(
            command=self._config.mcp_server_command,
            args=self._config.mcp_server_args,
            cwd=self._config.mcp_server_cwd,
            env=env,
        )

        logger.info(
            "Launching MCP server subprocess: %s %s (cwd=%s)",
            self._config.mcp_server_command,
            " ".join(self._config.mcp_server_args),
            self._config.mcp_server_cwd or "(inherited)",
        )

        self._background_task = asyncio.create_task(
            self._run_session(server_params),
        )

        # Wait briefly for the session to initialise
        for _ in range(50):
            if self._connected:
                break
            await asyncio.sleep(0.1)

        if not self._connected:
            raise McpBridgeError(
                "MCP server subprocess failed to initialise within 5 seconds"
            )

        logger.info("MCP bridge connected successfully")

    async def disconnect(self) -> None:
        """Clean shutdown of the MCP session and subprocess."""
        self._connected = False
        self._session = None
        self._tools_cache = None

        if self._background_task is not None and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

        logger.info("MCP bridge disconnected")

    async def list_tools(self) -> list[McpTool]:
        """Return available MCP tools, using cache after first call.

        Returns:
            List of MCP tool definitions.

        Raises:
            McpBridgeError: If not connected.
        """
        self._ensure_session()

        if self._tools_cache is not None:
            return self._tools_cache

        assert self._session is not None  # guarded by _ensure_session
        result = await self._session.list_tools()
        self._tools_cache = list(result.tools)

        logger.info(
            "Cached %d MCP tools: %s",
            len(self._tools_cache),
            [t.name for t in self._tools_cache],
        )
        return self._tools_cache

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool and return the text result.

        Args:
            name: MCP tool name (e.g. ``get_vehicle_signal``).
            arguments: Tool arguments as a dictionary.

        Returns:
            Concatenated text content from the tool response.

        Raises:
            McpBridgeError: If not connected or the tool call fails.
        """
        self._ensure_session()
        assert self._session is not None  # guarded by _ensure_session

        logger.info("Calling MCP tool '%s' with args: %s", name, arguments)

        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:
            raise McpBridgeError(
                f"MCP tool '{name}' failed: {exc}"
            ) from exc

        text_parts = [
            part.text for part in result.content
            if hasattr(part, "text") and part.text
        ]
        response_text = "\n".join(text_parts) if text_parts else ""

        logger.debug("MCP tool '%s' returned: %s", name, response_text[:200])
        return response_text

    def get_gemini_tool_declarations(self) -> list[dict[str, Any]]:
        """Convert cached MCP tool schemas to Gemini function declarations.

        Each MCP tool carries ``name``, ``description``, and ``inputSchema``
        (JSON Schema). This method transforms them into the format expected
        by the Gemini ``function_declarations`` API.

        Returns:
            List of Gemini-compatible function declaration dicts.

        Raises:
            McpBridgeError: If tools have not been cached yet.
        """
        if self._tools_cache is None:
            raise McpBridgeError(
                "Tools not cached; call list_tools() first"
            )

        declarations: list[dict[str, Any]] = []
        for tool in self._tools_cache:
            declaration = _mcp_tool_to_gemini_declaration(tool)
            declarations.append(declaration)

        return declarations

    # -- Internal helpers ---------------------------------------------------

    def _ensure_session(self) -> None:
        """Verify that the MCP session is active.

        Raises:
            McpBridgeError: If the session is not connected.
        """
        if not self._connected or self._session is None:
            raise McpBridgeError("MCP bridge is not connected")

    def _build_subprocess_env(self) -> dict[str, str]:
        """Build environment variables for the MCP server subprocess.

        Passes Kuksa connection parameters so the child process can
        reach the Databroker.

        Returns:
            Environment variable dictionary.
        """
        env = dict(os.environ)
        env["KUKSA_DATABROKER_HOST"] = self._config.kuksa_databroker_host
        env["KUKSA_DATABROKER_PORT"] = str(self._config.kuksa_databroker_port)
        return env

    async def _run_session(self, server_params: StdioServerParameters) -> None:
        """Run the MCP stdio client session as a long-lived background task.

        Keeps the context managers alive for the lifetime of the bridge.

        Args:
            server_params: Parameters for launching the MCP server subprocess.
        """
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    self._session = session
                    self._connected = True

                    logger.info("MCP session initialised, caching tools")
                    await self.list_tools()

                    # Block until cancelled to keep context managers alive
                    try:
                        await asyncio.Future()
                    except asyncio.CancelledError:
                        logger.info("MCP session task cancelled")
        except asyncio.CancelledError:
            logger.info("MCP background task cancelled during setup")
        except Exception:
            logger.error("MCP session failed unexpectedly", exc_info=True)
        finally:
            self._connected = False
            self._session = None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _mcp_tool_to_gemini_declaration(tool: McpTool) -> dict[str, Any]:
    """Convert a single MCP tool definition to a Gemini function declaration.

    Args:
        tool: MCP tool with name, description, and inputSchema.

    Returns:
        Dict with ``name``, ``description``, and ``parameters`` keys
        conforming to the Gemini function calling schema.
    """
    parameters = _extract_parameters_schema(tool.inputSchema)

    return {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": parameters,
    }


def _extract_parameters_schema(
    input_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract a clean parameters schema from an MCP inputSchema.

    Strips keys not recognised by the Gemini API while preserving
    the essential ``type``, ``properties``, and ``required`` fields.

    Args:
        input_schema: JSON Schema from the MCP tool definition.

    Returns:
        Cleaned parameters dict suitable for Gemini.
    """
    if not input_schema:
        return {"type": "object", "properties": {}}

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    cleaned_properties: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        cleaned_properties[prop_name] = _clean_property_schema(prop_schema)

    result: dict[str, Any] = {
        "type": "object",
        "properties": cleaned_properties,
    }
    if required:
        result["required"] = required

    return result


def _clean_property_schema(prop_schema: dict[str, Any]) -> dict[str, Any]:
    """Clean a single property schema for Gemini compatibility.

    Gemini function declarations support a subset of JSON Schema.
    This strips unsupported keys and normalises type representations.

    Args:
        prop_schema: JSON Schema for a single property.

    Returns:
        Cleaned property schema dict.
    """
    allowed_keys = {"type", "description", "enum", "items", "properties", "required"}
    cleaned: dict[str, Any] = {}

    for key, value in prop_schema.items():
        if key in allowed_keys:
            cleaned[key] = value

    # Handle anyOf / oneOf by selecting the first non-null type
    if "type" not in cleaned:
        for union_key in ("anyOf", "oneOf"):
            if union_key in prop_schema:
                types = prop_schema[union_key]
                for t in types:
                    if isinstance(t, dict) and t.get("type") != "null":
                        cleaned["type"] = t.get("type", "string")
                        break

    # Default to string if type is still missing
    if "type" not in cleaned:
        cleaned["type"] = "string"

    return cleaned
