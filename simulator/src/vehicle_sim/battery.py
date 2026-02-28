"""Traction battery signal simulator.

Generates realistic State of Charge (SOC), voltage, and temperature
signals for a high-voltage traction battery with scenario-dependent
discharge behavior.
"""

import logging
import random

logger = logging.getLogger(__name__)

# --- VSS Paths ---
VSS_BATTERY_SOC = "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current"
VSS_BATTERY_VOLTAGE = "Vehicle.Powertrain.TractionBattery.CurrentVoltage"
VSS_BATTERY_TEMP = "Vehicle.Powertrain.TractionBattery.Temperature.Average"

# --- SOC Constants (%) ---
DEFAULT_SOC = 75.0
SOC_MIN = 0.0
SOC_MAX = 100.0

NORMAL_SOC_DRAIN_RATE = 0.01
NORMAL_SOC_NOISE_STDDEV = 0.002

BATTERY_LOW_SOC_START = 15.0
BATTERY_LOW_SOC_DRAIN_RATE = 0.05
BATTERY_LOW_SOC_NOISE_STDDEV = 0.005
BATTERY_LOW_SOC_FLOOR = 5.0

# --- Voltage Constants (V) ---
DEFAULT_VOLTAGE = 380.0
VOLTAGE_MIN = 300.0
VOLTAGE_MAX = 420.0

# Voltage is proportional to SOC: V = base + (SOC/100) * range
VOLTAGE_BASE = 310.0
VOLTAGE_SOC_RANGE = 110.0  # 310V at 0% SOC, 420V at 100% SOC

BATTERY_LOW_VOLTAGE_START = 350.0
BATTERY_LOW_VOLTAGE_FLOOR = 310.0
BATTERY_LOW_VOLTAGE_DECAY_RATE = 0.08
VOLTAGE_NOISE_STDDEV = 0.5

# --- Temperature Constants (Celsius) ---
DEFAULT_TEMPERATURE = 30.0
TEMPERATURE_MIN = 20.0
TEMPERATURE_MAX = 45.0

NORMAL_TEMP_NOISE_STDDEV = 0.2
NORMAL_TEMP_RISE_RATE = 0.005

BATTERY_LOW_TEMP_RISE_RATE = 0.01
BATTERY_LOW_TEMP_NOISE_STDDEV = 0.3


class BatterySimulator:
    """Simulates traction battery SOC, voltage, and temperature.

    In normal driving, SOC drains slowly and voltage tracks SOC
    proportionally. In battery-low scenario, SOC drops rapidly
    from 15% toward 5% with corresponding voltage decline.
    Temperature rises gradually under all scenarios.

    Attributes:
        _soc: Current state of charge in percent.
        _voltage: Current battery voltage in volts.
        _temperature: Current battery temperature in Celsius.
        _tick: Internal counter for signal generation.
    """

    def __init__(
        self,
        soc: float = DEFAULT_SOC,
        voltage: float = DEFAULT_VOLTAGE,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        """Initialize battery simulator with given state.

        Args:
            soc: Initial state of charge (0~100%).
            voltage: Initial battery voltage (300~420V).
            temperature: Initial battery temperature (20~45C).
        """
        self._soc: float = soc
        self._voltage: float = voltage
        self._temperature: float = temperature
        self._tick: int = 0

    def generate(self, scenario: str) -> dict[str, float]:
        """Generate battery signal values for the current tick.

        Args:
            scenario: Active scenario mode. One of
                ``"normal_driving"``, ``"engine_warning"``,
                or ``"battery_low"``.

        Returns:
            Dictionary mapping VSS paths to float values for SOC,
            voltage, and temperature.
        """
        if scenario == "battery_low":
            self._update_battery_low()
        elif scenario == "engine_warning":
            self._update_engine_warning()
        else:
            self._update_normal_driving()

        self._tick += 1

        logger.debug(
            "Battery signals: SOC=%.2f%%, voltage=%.1fV, temp=%.1f C "
            "(scenario=%s, tick=%d)",
            self._soc, self._voltage, self._temperature,
            scenario, self._tick,
        )

        return {
            VSS_BATTERY_SOC: round(self._soc, 2),
            VSS_BATTERY_VOLTAGE: round(self._voltage, 1),
            VSS_BATTERY_TEMP: round(self._temperature, 1),
        }

    def reset(self) -> None:
        """Reset simulator state to initial values."""
        self._soc = DEFAULT_SOC
        self._voltage = DEFAULT_VOLTAGE
        self._temperature = DEFAULT_TEMPERATURE
        self._tick = 0

    def _update_normal_driving(self) -> None:
        """Update battery state for normal driving conditions.

        SOC drains slowly, voltage tracks SOC proportionally,
        temperature rises gradually.
        """
        self._soc = max(
            SOC_MIN,
            self._soc - NORMAL_SOC_DRAIN_RATE + random.gauss(0, NORMAL_SOC_NOISE_STDDEV),
        )
        self._voltage = self._voltage_from_soc()
        temp_candidate = self._temperature + NORMAL_TEMP_RISE_RATE + random.gauss(0, NORMAL_TEMP_NOISE_STDDEV)
        self._temperature = max(self._temperature, min(TEMPERATURE_MAX, temp_candidate))

    def _update_engine_warning(self) -> None:
        """Update battery state for engine warning scenario.

        SOC remains stable; only temperature drifts slightly.
        """
        self._soc += random.gauss(0, NORMAL_SOC_NOISE_STDDEV)
        self._soc = max(SOC_MIN, min(SOC_MAX, self._soc))
        self._voltage = self._voltage_from_soc()
        temp_candidate = self._temperature + NORMAL_TEMP_RISE_RATE + random.gauss(0, NORMAL_TEMP_NOISE_STDDEV)
        self._temperature = max(self._temperature, min(TEMPERATURE_MAX, temp_candidate))

    def _update_battery_low(self) -> None:
        """Update battery state for battery-low critical scenario.

        SOC drops rapidly toward floor, voltage decays correspondingly,
        temperature rises faster due to stress.
        """
        self._soc = max(
            BATTERY_LOW_SOC_FLOOR,
            self._soc - BATTERY_LOW_SOC_DRAIN_RATE
            + random.gauss(0, BATTERY_LOW_SOC_NOISE_STDDEV),
        )

        # Voltage decays toward floor independently for more dramatic effect
        target_voltage = max(
            BATTERY_LOW_VOLTAGE_FLOOR,
            VOLTAGE_BASE + (self._soc / SOC_MAX) * VOLTAGE_SOC_RANGE,
        )
        self._voltage += (target_voltage - self._voltage) * 0.1
        self._voltage += random.gauss(0, VOLTAGE_NOISE_STDDEV)
        self._voltage = max(VOLTAGE_MIN, min(VOLTAGE_MAX, self._voltage))

        temp_candidate = self._temperature + BATTERY_LOW_TEMP_RISE_RATE + random.gauss(0, BATTERY_LOW_TEMP_NOISE_STDDEV)
        self._temperature = max(self._temperature, min(TEMPERATURE_MAX, temp_candidate))

    def _voltage_from_soc(self) -> float:
        """Calculate voltage proportional to SOC with noise.

        Returns:
            Voltage in volts, linearly mapped from SOC percentage.
        """
        base_voltage = VOLTAGE_BASE + (self._soc / SOC_MAX) * VOLTAGE_SOC_RANGE
        noisy_voltage = base_voltage + random.gauss(0, VOLTAGE_NOISE_STDDEV)
        return max(VOLTAGE_MIN, min(VOLTAGE_MAX, noisy_voltage))
