"""Shared test fixtures for Kuksa MCP Bridge server tests.

Provides pre-configured mock objects for the KuksaClientWrapper and
other common test dependencies, enabling fast isolated unit tests
without a real Kuksa Databroker connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kuksa_mcp.kuksa_client import (
    KuksaClientWrapper,
    SignalInfo,
    SignalMetadata,
    SignalValue,
)


@pytest.fixture
def mock_kuksa_client() -> AsyncMock:
    """Create a mock KuksaClientWrapper with pre-configured responses.

    Returns:
        AsyncMock spec'd to ``KuksaClientWrapper`` with sensible default
        return values for every public method.
    """
    client = AsyncMock(spec=KuksaClientWrapper)

    # -- get_signal default -------------------------------------------------
    client.get_signal.return_value = SignalValue(
        path="Vehicle.Speed",
        value=65.0,
        timestamp="2026-02-27T10:30:00+00:00",
        unit="km/h",
    )

    # -- get_signals default ------------------------------------------------
    client.get_signals.return_value = {
        "Vehicle.Speed": SignalValue(
            path="Vehicle.Speed",
            value=65.0,
            timestamp="2026-02-27T10:30:00+00:00",
            unit="km/h",
        ),
        "Vehicle.Powertrain.CombustionEngine.Speed": SignalValue(
            path="Vehicle.Powertrain.CombustionEngine.Speed",
            value=1500.0,
            timestamp="2026-02-27T10:30:00+00:00",
            unit="rpm",
        ),
    }

    # -- set_actuator default -----------------------------------------------
    client.set_actuator.return_value = True

    # -- search_tree default ------------------------------------------------
    client.search_tree.return_value = [
        SignalInfo(
            path="Vehicle.Speed",
            data_type="FLOAT",
            description="Vehicle speed",
        ),
        SignalInfo(
            path="Vehicle.Powertrain.CombustionEngine.Speed",
            data_type="FLOAT",
            description="Engine speed",
        ),
    ]

    # -- subscribe default --------------------------------------------------
    client.subscribe.return_value = [
        {
            "path": "Vehicle.Speed",
            "value": 65.0,
            "timestamp": "2026-02-27T10:30:00+00:00",
        },
        {
            "path": "Vehicle.Speed",
            "value": 67.0,
            "timestamp": "2026-02-27T10:30:01+00:00",
        },
    ]

    # -- get_metadata default -----------------------------------------------
    client.get_metadata.return_value = SignalMetadata(
        path="Vehicle.Speed",
        data_type="FLOAT",
        description="Vehicle speed",
        unit="km/h",
        entry_type="SENSOR",
    )

    return client
