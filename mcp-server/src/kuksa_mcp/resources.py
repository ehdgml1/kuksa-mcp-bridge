"""MCP Resource definitions for the Kuksa MCP Bridge.

Registers three resources on a FastMCP instance that expose
read-only vehicle metadata via the Model Context Protocol:

1. ``vss://tree`` -- full VSS signal tree overview
2. ``vss://metadata/{path}`` -- per-signal metadata lookup
3. ``vss://dtc-database`` -- complete DTC code reference
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from kuksa_mcp.dtc_database import get_full_database
from kuksa_mcp.kuksa_client import (
    DatabrokerConnectionError,
    KuksaClientWrapper,
    SignalNotFoundError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
JSON_INDENT = 2
TREE_HEADER = "VSS Signal Tree — Available Vehicle Signals"
TREE_SEPARATOR = "=" * 60


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_resources(mcp: FastMCP, kuksa: KuksaClientWrapper) -> None:
    """Register all MCP resources on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to attach resources to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """
    _register_vss_tree_resource(mcp, kuksa)
    _register_metadata_resource(mcp, kuksa)
    _register_dtc_database_resource(mcp)


def _register_vss_tree_resource(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the VSS tree overview resource.

    Args:
        mcp: The FastMCP server to attach the resource to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.resource(
        "vss://tree",
        name="vss_tree",
        description="Complete VSS signal tree with paths and data types",
        mime_type="text/plain",
    )
    async def get_vss_tree() -> str:
        """Return a formatted text overview of all available VSS signals.

        Returns:
            Human-readable tree listing every signal path, its data type,
            and description.
        """
        logger.info("Resource vss://tree requested")
        try:
            signals = await kuksa.search_tree("")
        except DatabrokerConnectionError as exc:
            logger.error("Cannot fetch VSS tree: %s", exc)
            return f"Error: Unable to retrieve VSS tree ({exc})"

        return _format_signal_tree(signals)


def _register_metadata_resource(
    mcp: FastMCP, kuksa: KuksaClientWrapper
) -> None:
    """Register the per-signal metadata template resource.

    Args:
        mcp: The FastMCP server to attach the resource to.
        kuksa: Shared Kuksa client wrapper for Databroker access.
    """

    @mcp.resource(
        "vss://metadata/{path}",
        name="vss_signal_metadata",
        description="Metadata for a specific VSS signal (type, unit, description)",
        mime_type="application/json",
    )
    async def get_signal_metadata(path: str) -> str:
        """Return JSON metadata for a single VSS signal.

        Args:
            path: Dot-separated VSS path (e.g. ``Vehicle.Speed``).

        Returns:
            JSON string with data type, unit, description, and entry type.
        """
        logger.info("Resource vss://metadata/%s requested", path)
        try:
            metadata = await kuksa.get_metadata(path)
            return json.dumps(metadata.model_dump(), indent=JSON_INDENT)
        except SignalNotFoundError:
            logger.warning("Metadata not found for %s", path)
            return json.dumps(
                {"error": f"Signal not found: {path}"},
                indent=JSON_INDENT,
            )
        except DatabrokerConnectionError as exc:
            logger.error("Cannot fetch metadata for %s: %s", path, exc)
            return json.dumps(
                {"error": f"Databroker error: {exc}"},
                indent=JSON_INDENT,
            )


def _register_dtc_database_resource(mcp: FastMCP) -> None:
    """Register the DTC database reference resource.

    Args:
        mcp: The FastMCP server to attach the resource to.
    """

    @mcp.resource(
        "vss://dtc-database",
        name="dtc_code_database",
        description="Complete DTC code reference with descriptions and severity",
        mime_type="text/plain",
    )
    async def get_dtc_database() -> str:
        """Return the full DTC database as formatted text.

        Returns:
            Human-readable reference listing every DTC code with its
            description, severity, system, and recommended action.
        """
        logger.info("Resource vss://dtc-database requested")
        database = get_full_database()
        return _format_dtc_database(database)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_signal_tree(signals: list[Any]) -> str:
    """Format a list of signal info objects into a human-readable tree.

    Args:
        signals: List of ``SignalInfo`` instances.

    Returns:
        Multi-line string listing signals grouped by top-level branch.
    """
    if not signals:
        return "No signals available in the VSS tree."

    lines: list[str] = [
        TREE_HEADER,
        TREE_SEPARATOR,
        f"Total signals: {len(signals)}",
        "",
    ]

    grouped = _group_signals_by_branch(signals)
    for branch in sorted(grouped):
        lines.append(f"[{branch}]")
        for sig in sorted(grouped[branch], key=lambda s: s.path):
            desc = f" -- {sig.description}" if sig.description else ""
            lines.append(f"  {sig.path} ({sig.data_type}){desc}")
        lines.append("")

    return "\n".join(lines)


def _group_signals_by_branch(signals: list[Any]) -> dict[str, list[Any]]:
    """Group signals by their top-level VSS branch name.

    Args:
        signals: List of ``SignalInfo`` instances.

    Returns:
        Dict mapping branch name to its signals.
    """
    grouped: dict[str, list[Any]] = {}
    for sig in signals:
        branch = sig.path.split(".")[0] if "." in sig.path else sig.path
        grouped.setdefault(branch, []).append(sig)
    return grouped


def _format_dtc_database(database: dict[str, Any]) -> str:
    """Format the DTC database dict into a human-readable reference.

    Args:
        database: Mapping of DTC code to ``DTCInfo``.

    Returns:
        Multi-line string organised by code family (P/B/C/U).
    """
    lines: list[str] = [
        "DTC Code Database Reference",
        TREE_SEPARATOR,
        f"Total codes: {len(database)}",
        "",
    ]

    families: dict[str, str] = {
        "P": "Powertrain",
        "B": "Body",
        "C": "Chassis",
        "U": "Network",
    }

    grouped = _group_dtc_by_family(database)
    for prefix in ("P", "B", "C", "U"):
        entries = grouped.get(prefix, [])
        if not entries:
            continue
        family_name = families.get(prefix, "Other")
        lines.append(f"=== {family_name} Codes ({prefix}xxxx) ===")
        for info in entries:
            lines.extend(_format_single_dtc(info))

    return "\n".join(lines)


def _group_dtc_by_family(database: dict[str, Any]) -> dict[str, list[Any]]:
    """Group DTC entries by their family prefix letter.

    Args:
        database: Mapping of DTC code to ``DTCInfo``.

    Returns:
        Dict mapping prefix letter to list of ``DTCInfo`` objects.
    """
    grouped: dict[str, list[Any]] = {}
    for code, info in sorted(database.items()):
        prefix = code[0] if code else "?"
        grouped.setdefault(prefix, []).append(info)
    return grouped


def _format_single_dtc(info: Any) -> list[str]:
    """Format a single DTC entry into display lines.

    Args:
        info: A ``DTCInfo`` instance.

    Returns:
        List of formatted lines for this entry.
    """
    return [
        f"  {info.code}: {info.description}",
        f"    Severity: {info.severity} | System: {info.system}",
        f"    Action: {info.recommended_action}",
        "",
    ]
