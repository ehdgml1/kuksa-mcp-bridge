"""Diagnostic Trouble Code (DTC) simulator.

Simulates OBD-II DTC generation and clearing based on active
driving scenarios. Provides realistic fault injection timing.
"""

import logging

logger = logging.getLogger(__name__)

# --- VSS Path ---
VSS_DTC_LIST = "Vehicle.OBD.DTCList"

# --- DTC Codes ---
DTC_P0301 = "P0301"  # Cylinder 1 misfire
DTC_P0128 = "P0128"  # Thermostat coolant temp below threshold
DTC_P0420 = "P0420"  # Catalyst system efficiency below threshold

# --- Timing Constants (in ticks) ---
ENGINE_WARNING_INITIAL_DTC_DELAY = 10
ENGINE_WARNING_SECONDARY_DTC_DELAY = 50

# --- Separator ---
DTC_SEPARATOR = ","


class DtcSimulator:
    """Simulates OBD-II Diagnostic Trouble Code generation.

    Manages a list of active DTCs that change based on the
    active driving scenario. Engine warning scenarios trigger
    DTCs after configurable delays to simulate realistic
    fault detection behavior.

    Attributes:
        _active_dtcs: Currently active DTC codes.
        _tick: Internal counter for timed DTC injection.
    """

    def __init__(self) -> None:
        """Initialize DTC simulator with no active codes."""
        self._active_dtcs: list[str] = []
        self._tick: int = 0

    @property
    def active_dtcs(self) -> list[str]:
        """Currently active DTC codes (read-only copy)."""
        return list(self._active_dtcs)

    def generate(self, scenario: str) -> dict[str, list[str]]:
        """Generate DTC list signal based on active scenario.

        Args:
            scenario: Active scenario mode. One of
                ``"normal_driving"``, ``"engine_warning"``,
                or ``"battery_low"``.

        Returns:
            Dictionary with ``Vehicle.OBD.DTCList`` key mapped
            to a list of active DTC code strings, matching the
            VSS ``STRING_ARRAY`` data type.
        """
        if scenario == "engine_warning":
            self._update_engine_warning()
        elif scenario == "normal_driving":
            self._update_normal_driving()
        else:
            self._update_battery_low()

        self._tick += 1
        dtc_list = list(self._active_dtcs)

        logger.debug(
            "DTC signals: active_dtcs=%s (scenario=%s, tick=%d)",
            dtc_list or "(none)", scenario, self._tick,
        )

        return {VSS_DTC_LIST: dtc_list}

    def inject_dtc(self, code: str) -> None:
        """Manually inject a DTC code into the active list.

        Args:
            code: OBD-II DTC code string (e.g., ``"P0301"``).
                Ignored if already active.
        """
        if code not in self._active_dtcs:
            self._active_dtcs.append(code)
            logger.info("DTC injected: %s (total active: %d)", code, len(self._active_dtcs))

    def clear_dtcs(self) -> None:
        """Clear all active DTC codes."""
        count = len(self._active_dtcs)
        self._active_dtcs.clear()
        logger.info("DTCs cleared (removed %d codes)", count)

    def reset(self) -> None:
        """Reset simulator state to initial values."""
        self._active_dtcs.clear()
        self._tick = 0

    def _update_normal_driving(self) -> None:
        """Normal driving produces no DTCs."""
        # DTCs are not auto-cleared; they persist until explicitly cleared.
        # In a real vehicle, DTCs require a scan tool to clear.

    def _update_engine_warning(self) -> None:
        """Inject DTCs progressively during engine warning scenario.

        P0301 (cylinder misfire) appears first after a short delay,
        followed by P0420 (catalyst efficiency) after a longer delay.
        """
        if (
            self._tick >= ENGINE_WARNING_INITIAL_DTC_DELAY
            and DTC_P0301 not in self._active_dtcs
        ):
            self.inject_dtc(DTC_P0301)

        if (
            self._tick >= ENGINE_WARNING_SECONDARY_DTC_DELAY
            and DTC_P0420 not in self._active_dtcs
        ):
            self.inject_dtc(DTC_P0420)

    def _update_battery_low(self) -> None:
        """Battery-low scenario produces no DTCs."""
