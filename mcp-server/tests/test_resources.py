"""Unit tests for MCP Resource definitions.

Tests the three resources registered by ``register_resources``:
vss://tree, vss://metadata/{path}, and vss://dtc-database, using
a mocked KuksaClientWrapper.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from kuksa_mcp.kuksa_client import (
    DatabrokerConnectionError,
    KuksaClientWrapper,
    SignalInfo,
    SignalMetadata,
    SignalNotFoundError,
)
from kuksa_mcp.resources import (
    TREE_HEADER,
    TREE_SEPARATOR,
    _format_dtc_database,
    _format_signal_tree,
    _format_single_dtc,
    _group_dtc_by_family,
    _group_signals_by_branch,
    register_resources,
)


# ---------------------------------------------------------------------------
# Helpers to extract registered resource / template functions
# ---------------------------------------------------------------------------
def _build_mcp_with_resources(
    mock_kuksa_client: AsyncMock,
) -> FastMCP:
    """Build a FastMCP instance with resources registered.

    Args:
        mock_kuksa_client: Mocked KuksaClientWrapper.

    Returns:
        Configured FastMCP instance.
    """
    mcp = FastMCP(name="test")
    register_resources(mcp, mock_kuksa_client)
    return mcp


# ===================================================================
# vss://tree resource
# ===================================================================
class TestVssTreeResource:
    """Tests for the ``vss://tree`` resource."""

    @pytest.mark.asyncio
    async def test_returns_formatted_tree(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Tree resource returns a formatted text with signal listing."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://tree"]
        result = await resource.fn()

        assert TREE_HEADER in result
        assert "Vehicle.Speed" in result
        assert "Vehicle.Powertrain.CombustionEngine.Speed" in result

    @pytest.mark.asyncio
    async def test_shows_total_count(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Tree output includes the total signal count."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://tree"]
        result = await resource.fn()

        assert "Total signals: 2" in result

    @pytest.mark.asyncio
    async def test_connection_error(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Connection failure returns an error message string."""
        mock_kuksa_client.search_tree.side_effect = DatabrokerConnectionError(
            "broker down",
        )
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://tree"]
        result = await resource.fn()

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_empty_tree(self, mock_kuksa_client: AsyncMock) -> None:
        """Empty signal list produces a 'no signals' message."""
        mock_kuksa_client.search_tree.return_value = []
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://tree"]
        result = await resource.fn()

        assert "No signals" in result


# ===================================================================
# vss://metadata/{path} template resource
# ===================================================================
class TestVssMetadataResource:
    """Tests for the ``vss://metadata/{path}`` template resource."""

    @pytest.mark.asyncio
    async def test_returns_valid_json(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Metadata resource returns valid JSON."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        template = mcp._resource_manager._templates["vss://metadata/{path}"]
        result = await template.fn(path="Vehicle.Speed")

        parsed = json.loads(result)
        assert parsed["path"] == "Vehicle.Speed"
        assert parsed["data_type"] == "FLOAT"
        assert parsed["unit"] == "km/h"
        assert parsed["entry_type"] == "SENSOR"

    @pytest.mark.asyncio
    async def test_signal_not_found(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Missing signal returns JSON with error key."""
        mock_kuksa_client.get_metadata.side_effect = SignalNotFoundError(
            "Bad.Path",
        )
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        template = mcp._resource_manager._templates["vss://metadata/{path}"]
        result = await template.fn(path="Bad.Path")

        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_connection_error(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Connection failure returns JSON with error key."""
        mock_kuksa_client.get_metadata.side_effect = DatabrokerConnectionError(
            "timeout",
        )
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        template = mcp._resource_manager._templates["vss://metadata/{path}"]
        result = await template.fn(path="Vehicle.Speed")

        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_contains_all_metadata_fields(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Result JSON contains all five metadata fields."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        template = mcp._resource_manager._templates["vss://metadata/{path}"]
        result = await template.fn(path="Vehicle.Speed")

        parsed = json.loads(result)
        expected_keys = {"path", "data_type", "description", "unit", "entry_type"}
        assert expected_keys.issubset(set(parsed.keys()))


# ===================================================================
# vss://dtc-database resource
# ===================================================================
class TestDtcDatabaseResource:
    """Tests for the ``vss://dtc-database`` resource."""

    @pytest.mark.asyncio
    async def test_returns_formatted_database(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """DTC database resource returns formatted text."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://dtc-database"]
        result = await resource.fn()

        assert "DTC Code Database" in result
        assert "Powertrain" in result

    @pytest.mark.asyncio
    async def test_contains_known_codes(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Output includes known DTC codes from the database."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://dtc-database"]
        result = await resource.fn()

        assert "P0301" in result
        assert "P0420" in result

    @pytest.mark.asyncio
    async def test_contains_all_families(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Output includes all DTC families (P, B, C, U)."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://dtc-database"]
        result = await resource.fn()

        assert "Powertrain" in result
        assert "Body" in result
        assert "Chassis" in result
        assert "Network" in result

    @pytest.mark.asyncio
    async def test_contains_total_count(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Output includes a total codes count."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)
        resource = mcp._resource_manager._resources["vss://dtc-database"]
        result = await resource.fn()

        assert "Total codes:" in result


# ===================================================================
# Resource registration
# ===================================================================
class TestRegisterResources:
    """Tests for the ``register_resources`` function."""

    def test_all_resources_registered(
        self, mock_kuksa_client: AsyncMock
    ) -> None:
        """Two static resources and one template are registered."""
        mcp = _build_mcp_with_resources(mock_kuksa_client)

        resources = mcp._resource_manager._resources
        templates = mcp._resource_manager._templates

        assert "vss://tree" in resources
        assert "vss://dtc-database" in resources
        assert "vss://metadata/{path}" in templates


# ===================================================================
# Formatting helpers (pure functions)
# ===================================================================
class TestFormatSignalTree:
    """Tests for ``_format_signal_tree``."""

    def test_empty_list(self) -> None:
        """Empty signal list produces 'no signals' message."""
        result = _format_signal_tree([])
        assert "No signals" in result

    def test_single_signal(self) -> None:
        """Single signal appears in formatted output."""
        signals = [
            SignalInfo(
                path="Vehicle.Speed",
                data_type="FLOAT",
                description="Vehicle speed",
            ),
        ]
        result = _format_signal_tree(signals)
        assert "Vehicle.Speed" in result
        assert "FLOAT" in result
        assert "Vehicle speed" in result

    def test_header_present(self) -> None:
        """Output includes the standard header."""
        signals = [
            SignalInfo(path="Vehicle.Speed", data_type="FLOAT", description=""),
        ]
        result = _format_signal_tree(signals)
        assert TREE_HEADER in result
        assert TREE_SEPARATOR in result


class TestGroupSignalsByBranch:
    """Tests for ``_group_signals_by_branch``."""

    def test_groups_by_top_level(self) -> None:
        """Signals are grouped by their first path component."""
        signals = [
            SignalInfo(path="Vehicle.Speed", data_type="FLOAT", description=""),
            SignalInfo(
                path="Vehicle.Powertrain.Speed",
                data_type="FLOAT",
                description="",
            ),
            SignalInfo(
                path="Chassis.Axle.Count",
                data_type="INT",
                description="",
            ),
        ]
        grouped = _group_signals_by_branch(signals)
        assert "Vehicle" in grouped
        assert "Chassis" in grouped
        assert len(grouped["Vehicle"]) == 2
        assert len(grouped["Chassis"]) == 1

    def test_single_component_path(self) -> None:
        """Path without dots uses the full path as branch."""
        signals = [
            SignalInfo(path="Speed", data_type="FLOAT", description=""),
        ]
        grouped = _group_signals_by_branch(signals)
        assert "Speed" in grouped


class TestGroupDtcByFamily:
    """Tests for ``_group_dtc_by_family``."""

    def test_groups_by_prefix(self) -> None:
        """DTCs are grouped by their prefix letter."""
        from kuksa_mcp.dtc_database import DTCInfo

        database = {
            "P0301": DTCInfo(
                code="P0301",
                description="misfire",
                severity="high",
                system="Engine",
                recommended_action="fix",
            ),
            "B0001": DTCInfo(
                code="B0001",
                description="airbag",
                severity="critical",
                system="Restraint",
                recommended_action="inspect",
            ),
        }
        grouped = _group_dtc_by_family(database)
        assert "P" in grouped
        assert "B" in grouped
        assert len(grouped["P"]) == 1
        assert len(grouped["B"]) == 1


class TestFormatSingleDtc:
    """Tests for ``_format_single_dtc``."""

    def test_contains_all_fields(self) -> None:
        """Formatted lines include code, description, severity, system, action."""
        from kuksa_mcp.dtc_database import DTCInfo

        info = DTCInfo(
            code="P0301",
            description="Cylinder 1 misfire",
            severity="high",
            system="Engine",
            recommended_action="Check spark plug",
        )
        lines = _format_single_dtc(info)
        combined = "\n".join(lines)

        assert "P0301" in combined
        assert "Cylinder 1 misfire" in combined
        assert "high" in combined
        assert "Engine" in combined
        assert "Check spark plug" in combined


class TestFormatDtcDatabase:
    """Tests for ``_format_dtc_database``."""

    def test_empty_database(self) -> None:
        """Empty database still produces a header."""
        result = _format_dtc_database({})
        assert "DTC Code Database" in result
        assert "Total codes: 0" in result

    def test_with_entries(self) -> None:
        """Database with entries produces formatted output."""
        from kuksa_mcp.dtc_database import DTCInfo

        database = {
            "P0301": DTCInfo(
                code="P0301",
                description="misfire",
                severity="high",
                system="Engine",
                recommended_action="fix",
            ),
        }
        result = _format_dtc_database(database)
        assert "P0301" in result
        assert "Powertrain" in result
