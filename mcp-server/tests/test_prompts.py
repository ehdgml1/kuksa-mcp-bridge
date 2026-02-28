"""Unit tests for MCP Prompt definitions.

Tests the three prompts registered by ``register_prompts``:
vehicle_health_check, driving_analysis, and diagnose_symptom.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP

from kuksa_mcp.prompts import (
    DRIVING_ANALYSIS_SIGNALS,
    HEALTH_CHECK_SIGNALS,
    _build_driving_analysis_text,
    _build_health_check_text,
    _build_symptom_diagnosis_text,
    register_prompts,
)


# ===================================================================
# Prompt registration
# ===================================================================
class TestRegisterPrompts:
    """Tests for the ``register_prompts`` function."""

    def test_all_three_prompts_registered(self) -> None:
        """All three prompts are registered on the FastMCP instance."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        prompts = mcp._prompt_manager._prompts
        expected = {
            "vehicle_health_check",
            "driving_analysis",
            "diagnose_symptom",
        }
        assert set(prompts.keys()) == expected


# ===================================================================
# vehicle_health_check prompt
# ===================================================================
class TestVehicleHealthCheckPrompt:
    """Tests for the ``vehicle_health_check`` prompt."""

    def test_returns_string(self) -> None:
        """Prompt function returns a non-empty string."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        prompt = mcp._prompt_manager._prompts["vehicle_health_check"]
        result = prompt.fn()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_step_numbers(self) -> None:
        """Prompt includes numbered steps for the AI workflow."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["vehicle_health_check"].fn()
        assert "1." in result
        assert "2." in result
        assert "3." in result
        assert "4." in result

    def test_references_health_signals(self) -> None:
        """Prompt references the configured health check signals."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["vehicle_health_check"].fn()
        for signal in HEALTH_CHECK_SIGNALS:
            assert signal in result

    def test_references_dtc_tool(self) -> None:
        """Prompt references the diagnose_dtc tool."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["vehicle_health_check"].fn()
        assert "diagnose_dtc" in result


# ===================================================================
# driving_analysis prompt
# ===================================================================
class TestDrivingAnalysisPrompt:
    """Tests for the ``driving_analysis`` prompt."""

    def test_returns_string(self) -> None:
        """Prompt function returns a non-empty string."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["driving_analysis"].fn()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_references_driving_signals(self) -> None:
        """Prompt references the configured driving analysis signals."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["driving_analysis"].fn()
        for signal in DRIVING_ANALYSIS_SIGNALS:
            assert signal in result

    def test_references_subscribe_tool(self) -> None:
        """Prompt references the subscribe_signals tool."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["driving_analysis"].fn()
        assert "subscribe_signals" in result


# ===================================================================
# diagnose_symptom prompt
# ===================================================================
class TestDiagnoseSymptomPrompt:
    """Tests for the ``diagnose_symptom`` prompt."""

    def test_includes_symptom_text(self) -> None:
        """Prompt includes the user-supplied symptom description."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        prompt = mcp._prompt_manager._prompts["diagnose_symptom"]
        result = prompt.fn(symptom="engine noise at high RPM")
        assert "engine noise at high RPM" in result

    def test_references_dtc_tool(self) -> None:
        """Prompt instructs the AI to run diagnose_dtc."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["diagnose_symptom"].fn(
            symptom="vibration",
        )
        assert "diagnose_dtc" in result

    def test_references_search_tool(self) -> None:
        """Prompt instructs the AI to use search_vss_tree."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["diagnose_symptom"].fn(
            symptom="vibration",
        )
        assert "search_vss_tree" in result

    def test_contains_severity_assessment(self) -> None:
        """Prompt requests a severity assessment in the diagnosis."""
        mcp = FastMCP(name="test")
        register_prompts(mcp)

        result = mcp._prompt_manager._prompts["diagnose_symptom"].fn(
            symptom="overheating",
        )
        assert "Severity" in result or "severity" in result


# ===================================================================
# Prompt text builder helpers
# ===================================================================
class TestBuildHealthCheckText:
    """Tests for ``_build_health_check_text``."""

    def test_includes_signal_list(self) -> None:
        """Built text includes the provided signal list."""
        text = _build_health_check_text("  - Vehicle.Speed")
        assert "Vehicle.Speed" in text

    def test_includes_temperature_range(self) -> None:
        """Built text mentions the normal engine temperature range."""
        text = _build_health_check_text("")
        assert "80" in text or "105" in text


class TestBuildDrivingAnalysisText:
    """Tests for ``_build_driving_analysis_text``."""

    def test_includes_signal_list(self) -> None:
        """Built text includes the provided signal list."""
        text = _build_driving_analysis_text("  - Vehicle.Speed")
        assert "Vehicle.Speed" in text

    def test_includes_efficiency_score(self) -> None:
        """Built text mentions an efficiency score."""
        text = _build_driving_analysis_text("")
        assert "efficiency" in text.lower()


class TestBuildSymptomDiagnosisText:
    """Tests for ``_build_symptom_diagnosis_text``."""

    def test_includes_symptom(self) -> None:
        """Built text includes the symptom verbatim."""
        text = _build_symptom_diagnosis_text("brakes squealing")
        assert "brakes squealing" in text

    def test_includes_root_cause_step(self) -> None:
        """Built text includes root-cause analysis step."""
        text = _build_symptom_diagnosis_text("noise")
        assert "root cause" in text.lower() or "most likely" in text.lower()

    def test_includes_safety_warning(self) -> None:
        """Built text includes a safety advisory."""
        text = _build_symptom_diagnosis_text("overheating")
        assert "dangerous" in text.lower() or "stop" in text.lower()
