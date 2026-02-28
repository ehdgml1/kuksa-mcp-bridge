"""MCP Prompt definitions for the Kuksa MCP Bridge.

Registers three prompts on a FastMCP instance that guide AI assistants
through common vehicle diagnostics and analysis workflows:

1. ``vehicle_health_check`` -- comprehensive vehicle status overview
2. ``driving_analysis`` -- driving pattern and efficiency analysis
3. ``diagnose_symptom`` -- symptom-based fault diagnosis
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal path constants (avoid magic strings in prompt bodies)
# ---------------------------------------------------------------------------
HEALTH_CHECK_SIGNALS: list[str] = [
    "Vehicle.Speed",
    "Vehicle.Powertrain.CombustionEngine.Speed",
    "Vehicle.Powertrain.CombustionEngine.ECT",
    "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
    "Vehicle.Powertrain.TractionBattery.CurrentVoltage",
    "Vehicle.Powertrain.TractionBattery.Temperature",
]

DRIVING_ANALYSIS_SIGNALS: list[str] = [
    "Vehicle.Speed",
    "Vehicle.Powertrain.CombustionEngine.Speed",
    "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server to attach prompts to.
    """
    _register_health_check_prompt(mcp)
    _register_driving_analysis_prompt(mcp)
    _register_symptom_diagnosis_prompt(mcp)


def _register_health_check_prompt(mcp: FastMCP) -> None:
    """Register the vehicle health check prompt.

    Args:
        mcp: The FastMCP server to attach the prompt to.
    """

    @mcp.prompt(
        name="vehicle_health_check",
        description="Comprehensive vehicle health status assessment",
    )
    def vehicle_health_check() -> str:
        """Return instructions for a full vehicle health check.

        Returns:
            Multi-step prompt guiding the AI to query key signals,
            run DTC diagnostics, and summarise the vehicle's condition.
        """
        logger.info("Prompt vehicle_health_check requested")
        signal_list = "\n".join(f"  - {s}" for s in HEALTH_CHECK_SIGNALS)
        return _build_health_check_text(signal_list)

    return None


def _register_driving_analysis_prompt(mcp: FastMCP) -> None:
    """Register the driving analysis prompt.

    Args:
        mcp: The FastMCP server to attach the prompt to.
    """

    @mcp.prompt(
        name="driving_analysis",
        description="Analyse driving patterns and suggest efficiency improvements",
    )
    def driving_analysis() -> str:
        """Return instructions for driving pattern analysis.

        Returns:
            Multi-step prompt guiding the AI to subscribe to signals
            and suggest efficiency improvements.
        """
        logger.info("Prompt driving_analysis requested")
        signal_list = "\n".join(f"  - {s}" for s in DRIVING_ANALYSIS_SIGNALS)
        return _build_driving_analysis_text(signal_list)

    return None


def _register_symptom_diagnosis_prompt(mcp: FastMCP) -> None:
    """Register the symptom-based diagnosis prompt.

    Args:
        mcp: The FastMCP server to attach the prompt to.
    """

    @mcp.prompt(
        name="diagnose_symptom",
        description="Diagnose a vehicle issue based on a described symptom",
    )
    def diagnose_symptom(symptom: str) -> str:
        """Return a diagnostic workflow tailored to a specific symptom.

        Args:
            symptom: Natural-language description of the vehicle issue.

        Returns:
            Step-by-step prompt for DTC checks and root-cause analysis.
        """
        logger.info("Prompt diagnose_symptom requested: symptom=%s", symptom)
        return _build_symptom_diagnosis_text(symptom)

    return None


# ---------------------------------------------------------------------------
# Prompt text builders
# ---------------------------------------------------------------------------
def _build_health_check_text(signal_list: str) -> str:
    """Build the vehicle health check prompt text.

    Args:
        signal_list: Pre-formatted list of VSS signals to query.

    Returns:
        Complete prompt instruction string.
    """
    return (
        "Perform a comprehensive vehicle health check by following "
        "these steps:\n"
        "\n"
        "1. Read the following key signals using get_multiple_signals:\n"
        f"{signal_list}\n"
        "\n"
        "2. Run diagnose_dtc to check for any active diagnostic "
        "trouble codes.\n"
        "\n"
        "3. Analyse the readings:\n"
        "   - Is the engine temperature within a safe range "
        "(80-105 C normal operating)?\n"
        "   - Is the battery state of charge adequate (above 20%)?\n"
        "   - Are RPM and speed consistent with each other?\n"
        "   - Are there any active DTC codes?\n"
        "\n"
        "4. Provide a summary report with:\n"
        "   - Overall health status (Good / Warning / Critical)\n"
        "   - Key metrics and their status\n"
        "   - Any concerns or recommendations\n"
        "   - Recommended maintenance actions if needed\n"
        "\n"
        "Format the report clearly with sections and use plain "
        "language a non-technical driver can understand."
    )


def _build_driving_analysis_text(signal_list: str) -> str:
    """Build the driving analysis prompt text.

    Args:
        signal_list: Pre-formatted list of VSS signals to subscribe to.

    Returns:
        Complete prompt instruction string.
    """
    return (
        "Analyse the current driving pattern and suggest efficiency "
        "improvements by following these steps:\n"
        "\n"
        "1. Subscribe to the following signals for 10 seconds using "
        "subscribe_signals:\n"
        f"{signal_list}\n"
        "\n"
        "2. While monitoring, also read additional context signals "
        "with get_multiple_signals:\n"
        "  - Vehicle.Powertrain.CombustionEngine.ECT\n"
        "  - Vehicle.Cabin.HVAC.AmbientAirTemperature\n"
        "\n"
        "3. Analyse the collected data:\n"
        "   - Average and peak speed during the observation window\n"
        "   - RPM patterns (frequent high-RPM events suggest "
        "aggressive driving)\n"
        "   - Battery SOC trend (draining fast or stable?)\n"
        "   - Engine temperature stability\n"
        "\n"
        "4. Provide actionable recommendations:\n"
        "   - Driving habit adjustments for better fuel/energy "
        "efficiency\n"
        "   - Optimal RPM ranges for the current conditions\n"
        "   - HVAC usage impact on energy consumption\n"
        "   - Estimated efficiency score (1-10)\n"
        "\n"
        "Present the analysis in a friendly, encouraging tone."
    )


def _build_symptom_diagnosis_text(symptom: str) -> str:
    """Build the symptom diagnosis prompt text.

    Args:
        symptom: Natural-language description of the vehicle issue.

    Returns:
        Complete prompt instruction string.
    """
    return (
        f'The driver reports the following symptom: "{symptom}"\n'
        "\n"
        "Perform a systematic diagnosis by following these steps:\n"
        "\n"
        "1. Run diagnose_dtc to check for any active DTC codes that "
        "may be related to the reported symptom.\n"
        "\n"
        "2. Based on the symptom, read relevant signals using "
        "get_multiple_signals. Choose signals that relate to the "
        "symptom -- for example:\n"
        "   - Engine noise -> Engine RPM, ECT, oil pressure signals\n"
        "   - Poor acceleration -> Throttle, MAF, fuel pressure\n"
        "   - Battery warning -> SOC, voltage, battery temperature\n"
        "   - Overheating -> ECT, coolant signals, cabin temperature\n"
        "   - Strange vibration -> Wheel speed, engine RPM\n"
        "\n"
        "3. Search the VSS tree using search_vss_tree if you need "
        "to discover additional relevant signals.\n"
        "\n"
        "4. Cross-reference the DTC codes (if any) with the signal "
        "readings to determine the most likely root cause.\n"
        "\n"
        "5. Provide a diagnosis report with:\n"
        "   - Most likely cause(s) ranked by probability\n"
        "   - Supporting evidence from DTC codes and signal data\n"
        "   - Severity assessment (can the driver continue driving?)\n"
        "   - Recommended immediate actions\n"
        "   - Estimated repair complexity and urgency\n"
        "\n"
        "Be thorough but reassuring. If the issue appears dangerous, "
        "clearly advise the driver to stop and seek immediate help."
    )
