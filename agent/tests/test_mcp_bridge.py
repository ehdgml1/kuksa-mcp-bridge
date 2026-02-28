"""Unit tests for the McpBridge and schema-conversion helpers.

Tests cover MCP-to-Gemini schema translation, property schema cleaning,
the is_connected property, subprocess environment building, and guard
conditions for un-cached tool declarations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vehicle_agent.config import AgentConfig
from vehicle_agent.mcp_bridge import (
    McpBridge,
    McpBridgeError,
    _clean_property_schema,
    _extract_parameters_schema,
    _mcp_tool_to_gemini_declaration,
)


# ---------------------------------------------------------------------------
# Helpers: build a minimal fake MCP Tool for testing
# ---------------------------------------------------------------------------
def _make_mcp_tool(
    name: str = "test_tool",
    description: str = "A test tool",
    input_schema: dict | None = None,
) -> MagicMock:
    """Create a minimal MagicMock that mimics an mcp.types.Tool.

    Args:
        name: Tool name attribute.
        description: Tool description attribute.
        input_schema: JSON Schema dict or None.

    Returns:
        MagicMock with .name, .description, .inputSchema attributes.
    """
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = input_schema
    return tool


# ===================================================================
# _mcp_tool_to_gemini_declaration
# ===================================================================
class TestMcpToolToGeminiDeclaration:
    """Tests for ``_mcp_tool_to_gemini_declaration``."""

    def test_basic_conversion(self) -> None:
        """A tool with name, description, and schema is converted correctly."""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "VSS path"}},
            "required": ["path"],
        }
        tool = _make_mcp_tool(
            name="get_vehicle_signal",
            description="Query a VSS signal",
            input_schema=schema,
        )
        declaration = _mcp_tool_to_gemini_declaration(tool)

        assert declaration["name"] == "get_vehicle_signal"
        assert declaration["description"] == "Query a VSS signal"
        assert "parameters" in declaration
        assert declaration["parameters"]["type"] == "object"

    def test_empty_description_becomes_empty_string(self) -> None:
        """A tool with None description produces an empty string in the declaration."""
        tool = _make_mcp_tool(description=None)
        declaration = _mcp_tool_to_gemini_declaration(tool)
        assert declaration["description"] == ""

    def test_no_schema_produces_empty_properties(self) -> None:
        """A tool without inputSchema still produces valid parameters dict."""
        tool = _make_mcp_tool(input_schema=None)
        declaration = _mcp_tool_to_gemini_declaration(tool)
        assert declaration["parameters"] == {"type": "object", "properties": {}}


# ===================================================================
# _extract_parameters_schema
# ===================================================================
class TestExtractParametersSchema:
    """Tests for ``_extract_parameters_schema``."""

    def test_none_input_returns_empty_object(self) -> None:
        """None input schema returns a minimal empty object schema."""
        result = _extract_parameters_schema(None)
        assert result == {"type": "object", "properties": {}}

    def test_empty_dict_returns_empty_object(self) -> None:
        """Empty dict input returns a minimal empty object schema."""
        result = _extract_parameters_schema({})
        assert result == {"type": "object", "properties": {}}

    def test_schema_with_properties(self) -> None:
        """Properties are extracted and cleaned from the input schema."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Signal path"},
            },
        }
        result = _extract_parameters_schema(schema)
        assert "path" in result["properties"]
        assert result["properties"]["path"]["type"] == "string"

    def test_schema_with_required(self) -> None:
        """Required fields are preserved in the output schema."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "value": {"type": "number"},
            },
            "required": ["path"],
        }
        result = _extract_parameters_schema(schema)
        assert result["required"] == ["path"]

    def test_schema_without_required_omits_key(self) -> None:
        """Schema with no required fields omits the 'required' key."""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
        result = _extract_parameters_schema(schema)
        assert "required" not in result

    def test_multiple_properties_preserved(self) -> None:
        """All properties are included in the cleaned schema."""
        schema = {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "description": "Signal paths"},
                "duration_seconds": {"type": "integer", "description": "Duration"},
            },
            "required": ["paths"],
        }
        result = _extract_parameters_schema(schema)
        assert "paths" in result["properties"]
        assert "duration_seconds" in result["properties"]


# ===================================================================
# _clean_property_schema
# ===================================================================
class TestCleanPropertySchema:
    """Tests for ``_clean_property_schema``."""

    def test_strips_unknown_keys(self) -> None:
        """Keys not in the Gemini allowed set are removed."""
        prop = {
            "type": "string",
            "description": "A path",
            "title": "Path Title",        # not allowed
            "examples": ["Vehicle.Speed"], # not allowed
            "$comment": "ignore me",       # not allowed
        }
        cleaned = _clean_property_schema(prop)
        assert "title" not in cleaned
        assert "examples" not in cleaned
        assert "$comment" not in cleaned

    def test_preserves_allowed_keys(self) -> None:
        """Allowed keys (type, description, enum, items, properties, required) survive."""
        prop = {
            "type": "string",
            "description": "A signal path",
            "enum": ["Vehicle.Speed", "Vehicle.RPM"],
        }
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "string"
        assert cleaned["description"] == "A signal path"
        assert cleaned["enum"] == ["Vehicle.Speed", "Vehicle.RPM"]

    def test_any_of_resolved_to_first_non_null(self) -> None:
        """anyOf union is resolved to the first non-null concrete type."""
        prop = {
            "anyOf": [
                {"type": "null"},
                {"type": "string"},
            ]
        }
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "string"

    def test_one_of_resolved_to_first_non_null(self) -> None:
        """oneOf union is resolved to the first non-null concrete type."""
        prop = {
            "oneOf": [
                {"type": "null"},
                {"type": "integer"},
            ]
        }
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "integer"

    def test_defaults_to_string_when_no_type(self) -> None:
        """A property with no type information defaults to 'string'."""
        prop = {"description": "Some property"}
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "string"

    def test_items_key_preserved_for_arrays(self) -> None:
        """The 'items' key is preserved for array property schemas."""
        prop = {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of paths",
        }
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "array"
        assert cleaned["items"] == {"type": "string"}

    def test_any_of_with_no_non_null_defaults_to_string(self) -> None:
        """anyOf with only null entries falls back to 'string' default."""
        prop = {
            "anyOf": [
                {"type": "null"},
            ]
        }
        cleaned = _clean_property_schema(prop)
        assert cleaned["type"] == "string"


# ===================================================================
# McpBridge.is_connected
# ===================================================================
class TestMcpBridgeIsConnected:
    """Tests for the McpBridge.is_connected property."""

    def test_not_connected_by_default(self, mock_config: AgentConfig) -> None:
        """A freshly created McpBridge reports is_connected=False."""
        bridge = McpBridge(mock_config)
        assert bridge.is_connected is False

    def test_connected_requires_both_flags(self, mock_config: AgentConfig) -> None:
        """is_connected requires _connected=True AND _session is not None."""
        bridge = McpBridge(mock_config)
        bridge._connected = True
        # _session is still None, so is_connected should be False
        assert bridge.is_connected is False

    def test_connected_when_session_and_flag_set(
        self, mock_config: AgentConfig
    ) -> None:
        """is_connected returns True when both _connected and _session are set."""
        bridge = McpBridge(mock_config)
        bridge._connected = True
        bridge._session = MagicMock()  # type: ignore[assignment]
        assert bridge.is_connected is True


# ===================================================================
# McpBridge._build_subprocess_env
# ===================================================================
class TestMcpBridgeBuildSubprocessEnv:
    """Tests for McpBridge._build_subprocess_env."""

    def test_includes_kuksa_host(self, mock_config: AgentConfig) -> None:
        """Subprocess env includes KUKSA_DATABROKER_HOST from config."""
        bridge = McpBridge(mock_config)
        env = bridge._build_subprocess_env()
        assert env["KUKSA_DATABROKER_HOST"] == mock_config.kuksa_databroker_host

    def test_includes_kuksa_port_as_string(self, mock_config: AgentConfig) -> None:
        """Subprocess env includes KUKSA_DATABROKER_PORT as a string."""
        bridge = McpBridge(mock_config)
        env = bridge._build_subprocess_env()
        assert env["KUKSA_DATABROKER_PORT"] == str(mock_config.kuksa_databroker_port)

    def test_inherits_existing_env(self, mock_config: AgentConfig) -> None:
        """Subprocess env inherits existing OS environment variables."""
        bridge = McpBridge(mock_config)
        with patch.dict("os.environ", {"MY_EXISTING_VAR": "hello"}):
            env = bridge._build_subprocess_env()
        assert "MY_EXISTING_VAR" in env
        assert env["MY_EXISTING_VAR"] == "hello"

    def test_custom_kuksa_host(self) -> None:
        """Custom kuksa_databroker_host is reflected in subprocess env."""
        config = AgentConfig(
            kuksa_databroker_host="broker.example.com",
            kuksa_databroker_port=12345,
            _env_file=None,  # type: ignore[call-arg]
        )
        bridge = McpBridge(config)
        env = bridge._build_subprocess_env()
        assert env["KUKSA_DATABROKER_HOST"] == "broker.example.com"
        assert env["KUKSA_DATABROKER_PORT"] == "12345"


# ===================================================================
# McpBridge.get_gemini_tool_declarations — guard condition
# ===================================================================
class TestGetGeminiToolDeclarations:
    """Tests for McpBridge.get_gemini_tool_declarations."""

    def test_raises_when_tools_not_cached(self, mock_config: AgentConfig) -> None:
        """get_gemini_tool_declarations raises McpBridgeError before list_tools()."""
        bridge = McpBridge(mock_config)
        with pytest.raises(McpBridgeError, match="Tools not cached"):
            bridge.get_gemini_tool_declarations()

    def test_returns_declarations_when_cache_populated(
        self, mock_config: AgentConfig
    ) -> None:
        """get_gemini_tool_declarations returns converted declarations from cache."""
        bridge = McpBridge(mock_config)
        tool = _make_mcp_tool(
            name="diagnose_dtc",
            description="Diagnose DTCs",
            input_schema={"type": "object", "properties": {}},
        )
        bridge._tools_cache = [tool]  # type: ignore[list-item]

        declarations = bridge.get_gemini_tool_declarations()
        assert len(declarations) == 1
        assert declarations[0]["name"] == "diagnose_dtc"
