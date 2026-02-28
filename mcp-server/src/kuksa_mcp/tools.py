"""MCP Tool definitions for the Kuksa MCP Bridge.

Registers six tools on a FastMCP instance that expose Kuksa Databroker
vehicle signals via the Model Context Protocol:

1. ``get_vehicle_signal`` -- single signal query
2. ``get_multiple_signals`` -- batch signal query
3. ``set_actuator`` -- actuator target control
4. ``diagnose_dtc`` -- DTC retrieval with human-readable descriptions
5. ``search_vss_tree`` -- keyword search across the VSS catalog
6. ``subscribe_signals`` -- time-bounded signal subscription
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from kuksa_mcp.dtc_database import get_dtc_description
from kuksa_mcp.kuksa_client import (
    DatabrokerConnectionError,
    KuksaClientWrapper,
    SignalNotFoundError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STATUS_OK = "ok"
STATUS_ERROR = "error"
VSS_DTC_LIST_PATH = "Vehicle.OBD.DTCList"
MAX_SUBSCRIBE_DURATION_SECONDS = 60
DEFAULT_SUBSCRIBE_DURATION_SECONDS = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _error_response(message: str) -> dict[str, Any]:
    """Build a standardised error response dict.

    Args:
        message: Human-readable error description.

    Returns:
        Dict with ``status`` set to ``error`` and the ``message``.
    """
    return {"status": STATUS_ERROR, "message": message}


# ---------------------------------------------------------------------------
# Tool registration (split by concern to keep each function short)
# ---------------------------------------------------------------------------
def register_tools(mcp: FastMCP, kuksa: KuksaClientWrapper) -> None:
    """Register all MCP tools on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to attach tools to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """
    _register_single_signal_tool(mcp, kuksa)
    _register_multi_signal_tool(mcp, kuksa)
    _register_actuator_tool(mcp, kuksa)
    _register_dtc_tool(mcp, kuksa)
    _register_search_tool(mcp, kuksa)
    _register_subscription_tool(mcp, kuksa)


def _register_single_signal_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the single-signal query tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def get_vehicle_signal(path: str) -> dict[str, Any]:
        """Query a single VSS signal from the Kuksa Databroker.

        Args:
            path: VSS signal path (e.g. "Vehicle.Speed").

        Returns:
            Dict with keys: path, value, unit, timestamp, status.
        """
        logger.info("Tool get_vehicle_signal called: path=%s", path)
        try:
            signal = await kuksa.get_signal(path)
            return {**signal.model_dump(), "status": STATUS_OK}
        except SignalNotFoundError as exc:
            logger.warning("Signal not found: %s", path)
            return _error_response(str(exc))
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))


def _register_multi_signal_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the batch signal query tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def get_multiple_signals(paths: list[str]) -> dict[str, Any]:
        """Query multiple VSS signals from the Kuksa Databroker at once.

        Args:
            paths: List of VSS signal paths to query.

        Returns:
            Dict with keys: signals (list), count, status.
        """
        logger.info("Tool get_multiple_signals called: paths=%s", paths)
        try:
            result = await kuksa.get_signals(paths)
            signals = [sv.model_dump() for sv in result.values()]
            return {
                "signals": signals,
                "count": len(signals),
                "status": STATUS_OK,
            }
        except SignalNotFoundError as exc:
            logger.warning("Signal not found in batch: %s", exc)
            return _error_response(str(exc))
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))


def _register_actuator_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the actuator control tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def set_actuator(
        path: str, value: float | str | bool
    ) -> dict[str, Any]:
        """Set a target value for a vehicle actuator.

        Use this to control actuators such as HVAC temperature settings,
        window positions, or seat adjustments.

        Args:
            path: VSS actuator path (e.g. "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature").
            value: Desired target value.

        Returns:
            Dict with keys: path, value, status, message.
        """
        logger.info("Tool set_actuator called: path=%s, value=%s", path, value)
        try:
            await kuksa.set_actuator(path, value)
            return {
                "path": path,
                "value": value,
                "status": STATUS_OK,
                "message": f"Actuator {path} set to {value}",
            }
        except SignalNotFoundError as exc:
            logger.warning("Actuator path not found: %s", path)
            return _error_response(str(exc))
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))


def _register_dtc_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the DTC diagnostic tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def diagnose_dtc() -> dict[str, Any]:
        """Retrieve active DTC codes with human-readable diagnostics.

        Reads the current DTC list from the vehicle OBD system and
        enriches each code with description, severity, affected system,
        and recommended action from the built-in DTC database.

        Returns:
            Dict with keys: dtc_codes (list of enriched DTCs), count, status.
        """
        logger.info("Tool diagnose_dtc called")
        try:
            signal = await kuksa.get_signal(VSS_DTC_LIST_PATH)
        except SignalNotFoundError:
            logger.warning("DTC list path not available")
            return {
                "dtc_codes": [],
                "count": 0,
                "status": STATUS_OK,
                "message": "DTC signal path not available on this vehicle",
            }
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))

        return _parse_dtc_value(signal.value)


def _register_search_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the VSS tree search tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def search_vss_tree(keyword: str) -> dict[str, Any]:
        """Search the VSS signal catalog by keyword.

        Performs a case-insensitive search against signal paths and
        descriptions. Returns matching signals with their data types.

        Args:
            keyword: Search term (e.g. "speed", "temperature", "battery").

        Returns:
            Dict with keys: results (list), count, status.
        """
        logger.info("Tool search_vss_tree called: keyword=%s", keyword)
        try:
            results = await kuksa.search_tree(keyword)
            return {
                "results": [r.model_dump() for r in results],
                "count": len(results),
                "status": STATUS_OK,
            }
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))


def _register_subscription_tool(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the signal subscription tool.

    Args:
        mcp: The FastMCP server to attach the tool to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.tool()
    async def subscribe_signals(
        paths: list[str],
        duration_seconds: int = DEFAULT_SUBSCRIBE_DURATION_SECONDS,
    ) -> dict[str, Any]:
        """Subscribe to signal changes and collect a trend over time.

        Monitors the specified signals for *duration_seconds* and
        returns every observed value update as a time series.

        Args:
            paths: VSS signal paths to monitor.
            duration_seconds: Collection window in seconds (max 60, default 10).

        Returns:
            Dict with keys: updates (list), duration, status.
        """
        clamped_duration = min(duration_seconds, MAX_SUBSCRIBE_DURATION_SECONDS)
        logger.info(
            "Tool subscribe_signals called: paths=%s, duration=%ss",
            paths,
            clamped_duration,
        )
        try:
            updates = await kuksa.subscribe(paths, clamped_duration)
            return {
                "updates": updates,
                "duration": clamped_duration,
                "status": STATUS_OK,
            }
        except DatabrokerConnectionError as exc:
            logger.error("Databroker connection error: %s", exc)
            return _error_response(str(exc))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _parse_dtc_value(raw_value: Any) -> dict[str, Any]:
    """Parse a raw DTC list value into enriched diagnostic entries.

    Handles both list and comma-separated string representations of
    DTC codes from the Databroker.

    Args:
        raw_value: Raw value from ``Vehicle.OBD.DTCList`` (list or str).

    Returns:
        Standardised response dict with enriched DTC entries.
    """
    if raw_value is None:
        return {
            "dtc_codes": [],
            "count": 0,
            "status": STATUS_OK,
            "message": "No active diagnostic trouble codes",
        }

    codes = _normalize_dtc_codes(raw_value)
    if not codes:
        return {
            "dtc_codes": [],
            "count": 0,
            "status": STATUS_OK,
            "message": "No active diagnostic trouble codes",
        }

    enriched = _enrich_dtc_codes(codes)
    return {
        "dtc_codes": enriched,
        "count": len(enriched),
        "status": STATUS_OK,
    }


def _normalize_dtc_codes(raw_value: Any) -> list[str]:
    """Normalise a raw DTC value into a clean list of code strings.

    Args:
        raw_value: String, list, or other representation of DTC codes.

    Returns:
        List of trimmed, non-empty DTC code strings.
    """
    if isinstance(raw_value, list):
        return [str(c).strip() for c in raw_value if str(c).strip()]
    if isinstance(raw_value, str):
        return [c.strip() for c in raw_value.split(",") if c.strip()]
    return []


def _enrich_dtc_codes(codes: list[str]) -> list[dict[str, str]]:
    """Look up each DTC code in the database and build enriched entries.

    Args:
        codes: List of DTC code strings.

    Returns:
        List of dicts with code, description, severity, system, and
        recommended_action fields.
    """
    enriched: list[dict[str, str]] = []
    for code in codes:
        info = get_dtc_description(code)
        if info is not None:
            enriched.append(info.model_dump())
        else:
            enriched.append({
                "code": code,
                "description": f"Unknown DTC code: {code}",
                "severity": "medium",
                "system": "Unknown",
                "recommended_action": "Consult a qualified technician for diagnosis.",
            })
    return enriched
