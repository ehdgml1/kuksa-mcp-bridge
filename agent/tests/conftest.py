"""Shared test fixtures for the Vehicle AI Agent tests.

Provides pre-configured mock objects for McpBridge, AgentConfig,
and Gemini clients to enable fast, isolated unit tests without
requiring live external services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vehicle_agent.config import AgentConfig


@pytest.fixture
def mock_config() -> AgentConfig:
    """Create an AgentConfig with safe test values.

    Returns:
        AgentConfig instance with fake API key and test-friendly settings.
    """
    return AgentConfig(
        gemini_api_key="test-fake-api-key-abc123",
        gemini_model="gemini-2.0-flash",
        kuksa_databroker_host="localhost",
        kuksa_databroker_port=55555,
        mcp_server_command="python",
        mcp_server_args=["-m", "kuksa_mcp.server"],
        mcp_server_cwd=None,
        agent_log_level="DEBUG",
        max_tool_calls_per_turn=5,
    )


@pytest.fixture
def mock_mcp_bridge() -> AsyncMock:
    """Create a mock McpBridge that is already connected with fake tools.

    Returns:
        AsyncMock with is_connected=True and a pre-populated tool list.
    """
    from vehicle_agent.mcp_bridge import McpBridge

    bridge = AsyncMock(spec=McpBridge)
    bridge.is_connected = True

    # Pre-populated Gemini function declarations
    bridge.get_gemini_tool_declarations.return_value = [
        {
            "name": "get_vehicle_signal",
            "description": "Query a single VSS signal",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "VSS signal path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "diagnose_dtc",
            "description": "Retrieve active DTC codes",
            "parameters": {"type": "object", "properties": {}},
        },
    ]

    bridge.call_tool.return_value = '{"path": "Vehicle.Speed", "value": 65.0, "unit": "km/h"}'
    bridge.list_tools.return_value = []

    return bridge


@pytest.fixture
def mock_gemini_client() -> MagicMock:
    """Create a mock for google.genai.Client.

    Returns:
        MagicMock with a models.generate_content stub.
    """
    client = MagicMock()
    client.models = MagicMock()
    client.models.generate_content = MagicMock()
    return client
