"""HVAC (Heating, Ventilation, and Air Conditioning) signal simulator.

Generates realistic cabin temperature signals including
driver-set target temperature and ambient air temperature
that converges toward the set point over time.
"""

import logging
import random

logger = logging.getLogger(__name__)

# --- VSS Paths ---
VSS_HVAC_DRIVER_TEMP = "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
VSS_AMBIENT_TEMP = "Vehicle.Cabin.HVAC.AmbientAirTemperature"

# --- Temperature Constants (degrees Celsius) ---
DEFAULT_TARGET_TEMP = 22.0
DEFAULT_AMBIENT_TEMP = 25.0

TARGET_TEMP_MIN = 16.0
TARGET_TEMP_MAX = 30.0

AMBIENT_CONVERGENCE_RATE = 0.02
AMBIENT_NOISE_STDDEV = 0.1


class HvacSimulator:
    """Simulates HVAC driver target temperature and ambient cabin temperature.

    The target temperature remains at the configured set point.
    The ambient temperature gradually converges toward the target
    using exponential smoothing with small Gaussian noise for realism.

    Attributes:
        _target_temp: Driver-set target temperature in Celsius.
        _ambient_temp: Current ambient cabin temperature in Celsius.
        _tick: Internal counter for signal generation.
    """

    def __init__(
        self,
        target_temp: float = DEFAULT_TARGET_TEMP,
        ambient_temp: float = DEFAULT_AMBIENT_TEMP,
    ) -> None:
        """Initialize HVAC simulator with target and ambient temperatures.

        Args:
            target_temp: Initial driver-set target temperature in Celsius.
                Must be between 16 and 30 inclusive.
            ambient_temp: Initial ambient cabin temperature in Celsius.
        """
        self._target_temp: float = max(
            TARGET_TEMP_MIN, min(TARGET_TEMP_MAX, target_temp)
        )
        self._ambient_temp: float = ambient_temp
        self._tick: int = 0

    @property
    def target_temp(self) -> float:
        """Current driver-set target temperature in Celsius."""
        return self._target_temp

    @target_temp.setter
    def target_temp(self, value: float) -> None:
        """Set driver target temperature, clamped to valid range.

        Args:
            value: Desired temperature in Celsius (16~30).
        """
        self._target_temp = max(TARGET_TEMP_MIN, min(TARGET_TEMP_MAX, value))
        logger.info("HVAC target temperature set to %.1f C", self._target_temp)

    def generate(self, scenario: str) -> dict[str, float]:
        """Generate HVAC signal values for the current tick.

        The target temperature stays constant at the set point.
        The ambient temperature converges toward the target
        regardless of scenario, simulating HVAC climate control.

        Args:
            scenario: Active scenario mode. Accepted for interface
                consistency but does not alter HVAC behavior.

        Returns:
            Dictionary mapping VSS paths to float values.
            Keys: driver target temp path, ambient temp path.
        """
        self._update_ambient_temp()
        self._tick += 1

        logger.debug(
            "HVAC signals: target=%.1f C, ambient=%.1f C "
            "(scenario=%s, tick=%d)",
            self._target_temp, self._ambient_temp, scenario, self._tick,
        )

        return {
            VSS_HVAC_DRIVER_TEMP: round(self._target_temp, 1),
            VSS_AMBIENT_TEMP: round(self._ambient_temp, 1),
        }

    def reset(self) -> None:
        """Reset simulator state to initial values."""
        self._target_temp = DEFAULT_TARGET_TEMP
        self._ambient_temp = DEFAULT_AMBIENT_TEMP
        self._tick = 0

    def _update_ambient_temp(self) -> None:
        """Move ambient temperature toward target via exponential smoothing.

        Uses first-order exponential convergence:
        ``ambient += rate * (target - ambient) + noise``
        """
        delta = self._target_temp - self._ambient_temp
        adjustment = (
            AMBIENT_CONVERGENCE_RATE * delta
            + random.gauss(0, AMBIENT_NOISE_STDDEV)
        )
        self._ambient_temp += adjustment
