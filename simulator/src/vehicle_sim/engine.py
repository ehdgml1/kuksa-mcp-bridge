"""Engine signal simulator for combustion engine parameters.

Generates realistic RPM and engine coolant temperature (ECT)
signals with scenario-dependent behavior using sine wave
modulation and Gaussian noise.
"""

import logging
import math
import random

logger = logging.getLogger(__name__)

# --- VSS Paths ---
VSS_ENGINE_SPEED = "Vehicle.Powertrain.CombustionEngine.Speed"
VSS_ENGINE_ECT = "Vehicle.Powertrain.CombustionEngine.ECT"

# --- RPM Constants ---
NORMAL_RPM_BASE = 1500.0
NORMAL_RPM_AMPLITUDE = 700.0
NORMAL_RPM_FREQUENCY = 0.05
NORMAL_RPM_NOISE_STDDEV = 30.0
NORMAL_RPM_MIN = 800.0
NORMAL_RPM_MAX = 3000.0

WARNING_RPM_BASE = 2500.0
WARNING_RPM_AMPLITUDE = 2000.0
WARNING_RPM_FREQUENCY = 0.12
WARNING_RPM_NOISE_STDDEV = 200.0
WARNING_RPM_MIN = 500.0
WARNING_RPM_MAX = 5000.0

BATTERY_LOW_RPM_BASE = 1200.0
BATTERY_LOW_RPM_AMPLITUDE = 400.0
BATTERY_LOW_RPM_FREQUENCY = 0.04
BATTERY_LOW_RPM_NOISE_STDDEV = 20.0
BATTERY_LOW_RPM_MIN = 800.0
BATTERY_LOW_RPM_MAX = 2000.0

# --- ECT Constants (degrees Celsius) ---
NORMAL_ECT_BASE = 90.0
NORMAL_ECT_AMPLITUDE = 5.0
NORMAL_ECT_FREQUENCY = 0.02
NORMAL_ECT_NOISE_STDDEV = 0.5
NORMAL_ECT_MIN = 85.0
NORMAL_ECT_MAX = 95.0

WARNING_ECT_START = 95.0
WARNING_ECT_RISE_RATE = 0.05
WARNING_ECT_NOISE_STDDEV = 1.0
WARNING_ECT_MAX = 115.0

BATTERY_LOW_ECT_BASE = 88.0
BATTERY_LOW_ECT_AMPLITUDE = 3.0
BATTERY_LOW_ECT_FREQUENCY = 0.02
BATTERY_LOW_ECT_NOISE_STDDEV = 0.3
BATTERY_LOW_ECT_MIN = 82.0
BATTERY_LOW_ECT_MAX = 93.0


class EngineSimulator:
    """Simulates combustion engine RPM and coolant temperature.

    Produces time-varying signals using sine wave oscillation
    combined with Gaussian noise for realism. Different scenarios
    produce distinct signal behaviors (e.g., irregular spikes
    during engine warnings).

    Attributes:
        _tick: Internal counter for smooth time-varying signals.
        _ect_warning: Accumulated ECT value during warning scenario.
    """

    def __init__(self) -> None:
        """Initialize engine simulator with default state."""
        self._tick: int = 0
        self._ect_warning: float = WARNING_ECT_START

    def generate(self, scenario: str) -> dict[str, float]:
        """Generate engine signal values for the current tick.

        Args:
            scenario: Active scenario mode. One of
                ``"normal_driving"``, ``"engine_warning"``,
                or ``"battery_low"``.

        Returns:
            Dictionary mapping VSS paths to their float values.
            Keys: ``Vehicle.Powertrain.CombustionEngine.Speed``,
            ``Vehicle.Powertrain.CombustionEngine.ECT``.
        """
        if scenario == "engine_warning":
            rpm, ect = self._generate_engine_warning()
        elif scenario == "battery_low":
            rpm, ect = self._generate_battery_low()
        else:
            rpm, ect = self._generate_normal_driving()

        self._tick += 1

        logger.debug(
            "Engine signals: RPM=%.1f, ECT=%.1f (scenario=%s, tick=%d)",
            rpm, ect, scenario, self._tick,
        )

        return {
            VSS_ENGINE_SPEED: rpm,
            VSS_ENGINE_ECT: ect,
        }

    def reset(self) -> None:
        """Reset simulator state to initial values."""
        self._tick = 0
        self._ect_warning = WARNING_ECT_START

    def _generate_normal_driving(self) -> tuple[float, float]:
        """Generate smooth RPM and stable ECT for normal driving.

        Returns:
            Tuple of (rpm, ect) values within normal operating range.
        """
        rpm_raw = (
            NORMAL_RPM_BASE
            + NORMAL_RPM_AMPLITUDE * math.sin(self._tick * NORMAL_RPM_FREQUENCY)
            + random.gauss(0, NORMAL_RPM_NOISE_STDDEV)
        )
        rpm = max(NORMAL_RPM_MIN, min(NORMAL_RPM_MAX, rpm_raw))

        ect_raw = (
            NORMAL_ECT_BASE
            + NORMAL_ECT_AMPLITUDE * math.sin(self._tick * NORMAL_ECT_FREQUENCY)
            + random.gauss(0, NORMAL_ECT_NOISE_STDDEV)
        )
        ect = max(NORMAL_ECT_MIN, min(NORMAL_ECT_MAX, ect_raw))

        return rpm, ect

    def _generate_engine_warning(self) -> tuple[float, float]:
        """Generate irregular RPM spikes and rising ECT.

        Returns:
            Tuple of (rpm, ect) with erratic RPM and climbing temperature.
        """
        rpm_raw = (
            WARNING_RPM_BASE
            + WARNING_RPM_AMPLITUDE * math.sin(self._tick * WARNING_RPM_FREQUENCY)
            + random.gauss(0, WARNING_RPM_NOISE_STDDEV)
        )
        rpm = max(WARNING_RPM_MIN, min(WARNING_RPM_MAX, rpm_raw))

        candidate = self._ect_warning + WARNING_ECT_RISE_RATE + random.gauss(0, WARNING_ECT_NOISE_STDDEV)
        self._ect_warning = max(self._ect_warning, min(WARNING_ECT_MAX, candidate))
        ect = self._ect_warning

        return rpm, ect

    def _generate_battery_low(self) -> tuple[float, float]:
        """Generate reduced RPM and moderate ECT for battery-low scenario.

        Returns:
            Tuple of (rpm, ect) with lower-than-normal operating values.
        """
        rpm_raw = (
            BATTERY_LOW_RPM_BASE
            + BATTERY_LOW_RPM_AMPLITUDE * math.sin(self._tick * BATTERY_LOW_RPM_FREQUENCY)
            + random.gauss(0, BATTERY_LOW_RPM_NOISE_STDDEV)
        )
        rpm = max(BATTERY_LOW_RPM_MIN, min(BATTERY_LOW_RPM_MAX, rpm_raw))

        ect_raw = (
            BATTERY_LOW_ECT_BASE
            + BATTERY_LOW_ECT_AMPLITUDE * math.sin(self._tick * BATTERY_LOW_ECT_FREQUENCY)
            + random.gauss(0, BATTERY_LOW_ECT_NOISE_STDDEV)
        )
        ect = max(BATTERY_LOW_ECT_MIN, min(BATTERY_LOW_ECT_MAX, ect_raw))

        return rpm, ect
