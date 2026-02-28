"""Unit tests for MCP Tool definitions.

Tests each of the six MCP tools registered by ``register_tools``
using a mocked KuksaClientWrapper, verifying success responses,
error handling, and edge cases.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from kuksa_mcp.kuksa_client import (
    DatabrokerConnectionError,
    KuksaClientWrapper,
    SignalInfo,
    SignalNotFoundError,
    SignalValue,
)
from kuksa_mcp.tools import (
    MAX_SUBSCRIBE_DURATION_SECONDS,
    STATUS_ERROR,
    STATUS_OK,
    _enrich_dtc_codes,
    _error_response,
    _normalize_dtc_codes,
    _parse_dtc_value,
    register_tools,
)


# ---------------------------------------------------------------------------
# Helper to extract a registered tool function by name
# ---------------------------------------------------------------------------
def _get_tool_fn(
    mock_kuksa_client: AsyncMock,
    tool_name: str,
) -> Any:
    """Build a FastMCP server with tools and return one tool's callable.

    Args:
        mock_kuksa_client: Mocked KuksaClientWrapper.
        tool_name: Name of the tool to retrieve.

    Returns:
        The async callable registered under *tool_name*.
    """
    mcp = FastMCP(name="test")
    register_tools(mcp, mock_kuksa_client)
    return mcp._tool_manager._tools[tool_name].fn


# ===================================================================
# Pure helper tests
# ===================================================================
class TestErrorResponse:
    """Tests for ``_error_response``."""

    def test_builds_error_dict(self) -> None:
        """Returns dict with error status and message."""
        result = _error_response("something broke")
        assert result["status"] == STATUS_ERROR
        assert result["message"] == "something broke"


class TestNormalizeDtcCodes:
    """Tests for ``_normalize_dtc_codes``."""

    def test_comma_separated_string(self) -> None:
        """Comma-separated string produces a list of codes."""
        result = _normalize_dtc_codes("P0301,P0420")
        assert result == ["P0301", "P0420"]

    def test_list_input(self) -> None:
        """List input is converted with trimming."""
        result = _normalize_dtc_codes(["P0301", " P0420 "])
        assert result == ["P0301", "P0420"]

    def test_empty_string(self) -> None:
        """Empty string produces empty list."""
        result = _normalize_dtc_codes("")
        assert result == []

    def test_none_returns_empty(self) -> None:
        """Non-string, non-list input returns empty list."""
        result = _normalize_dtc_codes(None)
        assert result == []

    def test_int_returns_empty(self) -> None:
        """Integer input returns empty list."""
        result = _normalize_dtc_codes(42)
        assert result == []

    def test_string_with_whitespace(self) -> None:
        """Whitespace-only entries are filtered out."""
        result = _normalize_dtc_codes(" , P0301, , P0420 , ")
        assert result == ["P0301", "P0420"]


class TestParseDtcValue:
    """Tests for ``_parse_dtc_value``."""

    def test_none_returns_no_dtcs(self) -> None:
        """None value produces zero DTCs."""
        result = _parse_dtc_value(None)
        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    def test_empty_string_returns_no_dtcs(self) -> None:
        """Empty string produces zero DTCs."""
        result = _parse_dtc_value("")
        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    def test_valid_codes_enriched(self) -> None:
        """Known DTC codes are enriched with database info."""
        result = _parse_dtc_value("P0301")
        assert result["status"] == STATUS_OK
        assert result["count"] == 1
        assert result["dtc_codes"][0]["code"] == "P0301"
        assert "description" in result["dtc_codes"][0]

    def test_unknown_code_has_fallback(self) -> None:
        """Unknown DTC codes get a fallback description."""
        result = _parse_dtc_value("P9999")
        assert result["count"] == 1
        assert "Unknown" in result["dtc_codes"][0]["description"]

    def test_list_input_with_known_codes(self) -> None:
        """list[str] input (STRING_ARRAY) is handled correctly."""
        result = _parse_dtc_value(["P0301", "P0420"])
        assert result["status"] == STATUS_OK
        assert result["count"] == 2

    def test_empty_list_returns_no_dtcs(self) -> None:
        """Empty list produces zero DTCs."""
        result = _parse_dtc_value([])
        assert result["status"] == STATUS_OK
        assert result["count"] == 0


class TestEnrichDtcCodes:
    """Tests for ``_enrich_dtc_codes``."""

    def test_known_code(self) -> None:
        """Known code includes full database info."""
        result = _enrich_dtc_codes(["P0301"])
        assert len(result) == 1
        assert result[0]["code"] == "P0301"
        assert result[0]["severity"] == "high"

    def test_unknown_code(self) -> None:
        """Unknown code has fallback description and severity."""
        result = _enrich_dtc_codes(["X9999"])
        assert len(result) == 1
        assert "Unknown" in result[0]["description"]
        assert result[0]["severity"] == "medium"

    def test_mixed_codes(self) -> None:
        """Mix of known and unknown codes are both handled."""
        result = _enrich_dtc_codes(["P0301", "X1234"])
        assert len(result) == 2
        assert result[0]["code"] == "P0301"
        assert "Unknown" in result[1]["description"]


# ===================================================================
# get_vehicle_signal tool
# ===================================================================
class TestGetVehicleSignal:
    """Tests for the ``get_vehicle_signal`` MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self, mock_kuksa_client: AsyncMock) -> None:
        """Successful query returns ok status with signal data."""
        fn = _get_tool_fn(mock_kuksa_client, "get_vehicle_signal")
        result = await fn(path="Vehicle.Speed")

        assert result["status"] == STATUS_OK
        assert result["path"] == "Vehicle.Speed"
        assert result["value"] == 65.0
        assert result["unit"] == "km/h"

    @pytest.mark.asyncio
    async def test_signal_not_found(self, mock_kuksa_client: AsyncMock) -> None:
        """Missing signal returns error status."""
        mock_kuksa_client.get_signal.side_effect = SignalNotFoundError(
            "Invalid.Path",
        )
        fn = _get_tool_fn(mock_kuksa_client, "get_vehicle_signal")
        result = await fn(path="Invalid.Path")

        assert result["status"] == STATUS_ERROR
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_kuksa_client: AsyncMock) -> None:
        """Databroker unreachable returns error status."""
        mock_kuksa_client.get_signal.side_effect = DatabrokerConnectionError(
            "unreachable",
        )
        fn = _get_tool_fn(mock_kuksa_client, "get_vehicle_signal")
        result = await fn(path="Vehicle.Speed")

        assert result["status"] == STATUS_ERROR
        assert "unreachable" in result["message"]


# ===================================================================
# get_multiple_signals tool
# ===================================================================
class TestGetMultipleSignals:
    """Tests for the ``get_multiple_signals`` MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self, mock_kuksa_client: AsyncMock) -> None:
        """Successful batch query returns all signals."""
        fn = _get_tool_fn(mock_kuksa_client, "get_multiple_signals")
        paths = [
            "Vehicle.Speed",
            "Vehicle.Powertrain.CombustionEngine.Speed",
        ]
        result = await fn(paths=paths)

        assert result["status"] == STATUS_OK
        assert result["count"] == 2
        assert len(result["signals"]) == 2

    @pytest.mark.asyncio
    async def test_signal_not_found(self, mock_kuksa_client: AsyncMock) -> None:
        """Missing signal in batch returns error."""
        mock_kuksa_client.get_signals.side_effect = SignalNotFoundError(
            "Vehicle.Bad",
        )
        fn = _get_tool_fn(mock_kuksa_client, "get_multiple_signals")
        result = await fn(paths=["Vehicle.Bad"])

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_kuksa_client: AsyncMock) -> None:
        """Connection failure returns error."""
        mock_kuksa_client.get_signals.side_effect = DatabrokerConnectionError(
            "down",
        )
        fn = _get_tool_fn(mock_kuksa_client, "get_multiple_signals")
        result = await fn(paths=["Vehicle.Speed"])

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_signals_contain_expected_keys(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Each signal dict in the result has the expected keys."""
        fn = _get_tool_fn(mock_kuksa_client, "get_multiple_signals")
        result = await fn(paths=["Vehicle.Speed"])

        for signal in result["signals"]:
            assert "path" in signal
            assert "value" in signal
            assert "timestamp" in signal
            assert "unit" in signal


# ===================================================================
# set_actuator tool
# ===================================================================
class TestSetActuator:
    """Tests for the ``set_actuator`` MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self, mock_kuksa_client: AsyncMock) -> None:
        """Successful actuator set returns ok status with path and value."""
        fn = _get_tool_fn(mock_kuksa_client, "set_actuator")
        path = "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
        result = await fn(path=path, value=24.0)

        assert result["status"] == STATUS_OK
        assert result["path"] == path
        assert result["value"] == 24.0

    @pytest.mark.asyncio
    async def test_signal_not_found(self, mock_kuksa_client: AsyncMock) -> None:
        """Bad actuator path returns error."""
        mock_kuksa_client.set_actuator.side_effect = SignalNotFoundError(
            "Bad.Path",
        )
        fn = _get_tool_fn(mock_kuksa_client, "set_actuator")
        result = await fn(path="Bad.Path", value=24.0)

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_kuksa_client: AsyncMock) -> None:
        """Connection failure returns error."""
        mock_kuksa_client.set_actuator.side_effect = DatabrokerConnectionError(
            "timeout",
        )
        fn = _get_tool_fn(mock_kuksa_client, "set_actuator")
        result = await fn(path="Vehicle.Test", value=1.0)

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_boolean_value(self, mock_kuksa_client: AsyncMock) -> None:
        """Boolean actuator values are accepted."""
        fn = _get_tool_fn(mock_kuksa_client, "set_actuator")
        result = await fn(path="Vehicle.Test.Switch", value=True)

        assert result["status"] == STATUS_OK
        assert result["value"] is True

    @pytest.mark.asyncio
    async def test_string_value(self, mock_kuksa_client: AsyncMock) -> None:
        """String actuator values are accepted."""
        fn = _get_tool_fn(mock_kuksa_client, "set_actuator")
        result = await fn(path="Vehicle.Test.Mode", value="eco")

        assert result["status"] == STATUS_OK
        assert result["value"] == "eco"


# ===================================================================
# diagnose_dtc tool
# ===================================================================
class TestDiagnoseDtc:
    """Tests for the ``diagnose_dtc`` MCP tool."""

    @pytest.mark.asyncio
    async def test_no_dtcs_empty_string(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Empty DTC list returns count 0."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value="",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_no_dtcs_none_value(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """None DTC value returns count 0."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value=None,
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_known_dtcs(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Known DTC codes are enriched with descriptions."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value="P0301,P0420",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 2
        codes = [dtc["code"] for dtc in result["dtc_codes"]]
        assert "P0301" in codes
        assert "P0420" in codes

    @pytest.mark.asyncio
    async def test_with_unknown_dtc(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Unknown DTC codes get fallback descriptions."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value="Z9999",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["count"] == 1
        assert "Unknown" in result["dtc_codes"][0]["description"]

    @pytest.mark.asyncio
    async def test_dtc_path_not_available(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Missing DTC signal path returns empty list, not error."""
        mock_kuksa_client.get_signal.side_effect = SignalNotFoundError(
            "Vehicle.OBD.DTCList",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_connection_error(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Connection failure returns error status."""
        mock_kuksa_client.get_signal.side_effect = DatabrokerConnectionError(
            "down",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_dtc_enriched_fields(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Enriched DTC entries contain all expected fields."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value="P0301",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        dtc = result["dtc_codes"][0]
        assert "code" in dtc
        assert "description" in dtc
        assert "severity" in dtc
        assert "system" in dtc
        assert "recommended_action" in dtc

    @pytest.mark.asyncio
    async def test_with_list_dtcs(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """DTC value as list[str] (STRING_ARRAY) is handled correctly."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value=["P0301", "P0420"],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 2
        codes = [dtc["code"] for dtc in result["dtc_codes"]]
        assert "P0301" in codes
        assert "P0420" in codes

    @pytest.mark.asyncio
    async def test_with_empty_list_dtcs(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Empty list DTC value (STRING_ARRAY with no entries) returns count 0."""
        mock_kuksa_client.get_signal.return_value = SignalValue(
            path="Vehicle.OBD.DTCList",
            value=[],
            timestamp="2026-01-01T00:00:00+00:00",
        )
        fn = _get_tool_fn(mock_kuksa_client, "diagnose_dtc")
        result = await fn()

        assert result["status"] == STATUS_OK
        assert result["count"] == 0


# ===================================================================
# search_vss_tree tool
# ===================================================================
class TestSearchVssTree:
    """Tests for the ``search_vss_tree`` MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self, mock_kuksa_client: AsyncMock) -> None:
        """Successful search returns results with count."""
        fn = _get_tool_fn(mock_kuksa_client, "search_vss_tree")
        result = await fn(keyword="speed")

        assert result["status"] == STATUS_OK
        assert result["count"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_results_contain_expected_keys(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Each result contains path, data_type, description."""
        fn = _get_tool_fn(mock_kuksa_client, "search_vss_tree")
        result = await fn(keyword="speed")

        for item in result["results"]:
            assert "path" in item
            assert "data_type" in item
            assert "description" in item

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_kuksa_client: AsyncMock) -> None:
        """No matches returns count 0."""
        mock_kuksa_client.search_tree.return_value = []
        fn = _get_tool_fn(mock_kuksa_client, "search_vss_tree")
        result = await fn(keyword="nonexistent_signal")

        assert result["status"] == STATUS_OK
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_connection_error(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Connection failure returns error."""
        mock_kuksa_client.search_tree.side_effect = DatabrokerConnectionError(
            "down",
        )
        fn = _get_tool_fn(mock_kuksa_client, "search_vss_tree")
        result = await fn(keyword="speed")

        assert result["status"] == STATUS_ERROR


# ===================================================================
# subscribe_signals tool
# ===================================================================
class TestSubscribeSignals:
    """Tests for the ``subscribe_signals`` MCP tool."""

    @pytest.mark.asyncio
    async def test_success(self, mock_kuksa_client: AsyncMock) -> None:
        """Successful subscription returns updates."""
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        result = await fn(paths=["Vehicle.Speed"], duration_seconds=5)

        assert result["status"] == STATUS_OK
        assert result["duration"] == 5
        assert len(result["updates"]) == 2

    @pytest.mark.asyncio
    async def test_duration_clamped_to_max(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Duration exceeding max is clamped to MAX_SUBSCRIBE_DURATION_SECONDS."""
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        result = await fn(paths=["Vehicle.Speed"], duration_seconds=120)

        assert result["duration"] == MAX_SUBSCRIBE_DURATION_SECONDS

    @pytest.mark.asyncio
    async def test_default_duration(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Default duration is used when not specified."""
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        result = await fn(paths=["Vehicle.Speed"])

        assert result["status"] == STATUS_OK
        assert result["duration"] == 10  # DEFAULT_SUBSCRIBE_DURATION_SECONDS

    @pytest.mark.asyncio
    async def test_connection_error(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Connection failure returns error."""
        mock_kuksa_client.subscribe.side_effect = DatabrokerConnectionError(
            "down",
        )
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        result = await fn(paths=["Vehicle.Speed"], duration_seconds=5)

        assert result["status"] == STATUS_ERROR

    @pytest.mark.asyncio
    async def test_zero_duration(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Zero duration is passed through (not clamped up)."""
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        result = await fn(paths=["Vehicle.Speed"], duration_seconds=0)

        assert result["duration"] == 0

    @pytest.mark.asyncio
    async def test_multiple_paths(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Multiple subscription paths are forwarded to the client."""
        fn = _get_tool_fn(mock_kuksa_client, "subscribe_signals")
        paths = ["Vehicle.Speed", "Vehicle.Powertrain.CombustionEngine.Speed"]
        result = await fn(paths=paths, duration_seconds=5)

        assert result["status"] == STATUS_OK
        # Verify the client was called with both paths
        mock_kuksa_client.subscribe.assert_awaited_once_with(paths, 5)


# ===================================================================
# Tool registration
# ===================================================================
class TestRegisterTools:
    """Tests for ``register_tools`` registration function."""

    def test_all_six_tools_registered(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """All six tools are registered on the FastMCP instance."""
        mcp = FastMCP(name="test")
        register_tools(mcp, mock_kuksa_client)

        tools = mcp._tool_manager._tools
        expected = {
            "get_vehicle_signal",
            "get_multiple_signals",
            "set_actuator",
            "diagnose_dtc",
            "search_vss_tree",
            "subscribe_signals",
        }
        assert set(tools.keys()) == expected

    def test_tools_are_async(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """All registered tools are marked as async."""
        mcp = FastMCP(name="test")
        register_tools(mcp, mock_kuksa_client)

        for tool in mcp._tool_manager._tools.values():
            assert tool.is_async
