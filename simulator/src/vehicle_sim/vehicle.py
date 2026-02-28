"""Vehicle dynamics signal simulator.

Generates realistic speed and cumulative traveled distance
signals with scenario-dependent driving patterns.
"""

import logging
import math
import random

logger = logging.getLogger(__name__)

# --- VSS Paths ---
VSS_VEHICLE_SPEED = "Vehicle.Speed"
VSS_TRAVELED_DISTANCE = "Vehicle.TraveledDistance"

# --- Speed Constants (km/h) ---
NORMAL_SPEED_BASE = 60.0
NORMAL_SPEED_AMPLITUDE = 20.0
NORMAL_SPEED_FREQUENCY = 0.03
NORMAL_SPEED_NOISE_STDDEV = 2.0
NORMAL_SPEED_MIN = 40.0
NORMAL_SPEED_MAX = 80.0

WARNING_SPEED_START = 60.0
WARNING_SPEED_DECAY_RATE = 0.1
WARNING_SPEED_NOISE_STDDEV = 1.5
WARNING_SPEED_MIN = 20.0

BATTERY_LOW_SPEED_START = 50.0
BATTERY_LOW_SPEED_DECAY_RATE = 0.08
BATTERY_LOW_SPEED_NOISE_STDDEV = 1.0
BATTERY_LOW_SPEED_MIN = 10.0

# --- Distance Constants ---
SECONDS_PER_HOUR = 3600.0


class VehicleSimulator:
    """Simulates vehicle speed and cumulative traveled distance.

    Speed follows scenario-dependent patterns with sine wave
    modulation for normal driving and gradual decay for
    degraded scenarios. Distance accumulates based on
    instantaneous speed integrated over time.

    Attributes:
        _tick: Internal counter for smooth time-varying signals.
        _speed: Current vehicle speed in km/h.
        _distance_km: Cumulative traveled distance in km.
        _warning_speed: Decaying speed for engine warning scenario.
        _battery_low_speed: Decaying speed for battery low scenario.
    """

    def __init__(self) -> None:
        """Initialize vehicle simulator with zero speed and distance."""
        self._tick: int = 0
        self._speed: float = 0.0
        self._distance_km: float = 0.0
        self._warning_speed: float = WARNING_SPEED_START
        self._battery_low_speed: float = BATTERY_LOW_SPEED_START

    def generate(self, scenario: str, elapsed_seconds: float) -> dict[str, float]:
        """Generate vehicle speed and update traveled distance.

        Args:
            scenario: Active scenario mode. One of
                ``"normal_driving"``, ``"engine_warning"``,
                or ``"battery_low"``.
            elapsed_seconds: Time delta since last call in seconds,
                used to integrate distance from speed.

        Returns:
            Dictionary mapping VSS paths to float values.
            Keys: ``Vehicle.Speed``, ``Vehicle.TraveledDistance``.
        """
        if scenario == "engine_warning":
            self._speed = self._generate_engine_warning()
        elif scenario == "battery_low":
            self._speed = self._generate_battery_low()
        else:
            self._speed = self._generate_normal_driving()

        self._accumulate_distance(elapsed_seconds)
        self._tick += 1

        logger.debug(
            "Vehicle signals: speed=%.1f km/h, distance=%.3f km "
            "(scenario=%s, tick=%d)",
            self._speed, self._distance_km, scenario, self._tick,
        )

        return {
            VSS_VEHICLE_SPEED: round(self._speed, 1),
            VSS_TRAVELED_DISTANCE: round(self._distance_km, 3),
        }

    def reset(self) -> None:
        """Reset simulator state to initial values."""
        self._tick = 0
        self._speed = 0.0
        self._distance_km = 0.0
        self._warning_speed = WARNING_SPEED_START
        self._battery_low_speed = BATTERY_LOW_SPEED_START

    def _generate_normal_driving(self) -> float:
        """Generate oscillating speed for normal driving.

        Returns:
            Speed in km/h within the normal operating range.
        """
        speed_raw = (
            NORMAL_SPEED_BASE
            + NORMAL_SPEED_AMPLITUDE * math.sin(self._tick * NORMAL_SPEED_FREQUENCY)
            + random.gauss(0, NORMAL_SPEED_NOISE_STDDEV)
        )
        return max(NORMAL_SPEED_MIN, min(NORMAL_SPEED_MAX, speed_raw))

    def _generate_engine_warning(self) -> float:
        """Generate gradually decreasing speed for engine warning.

        Returns:
            Decaying speed in km/h, bottoming at the warning minimum.
        """
        candidate = self._warning_speed - WARNING_SPEED_DECAY_RATE + random.gauss(0, WARNING_SPEED_NOISE_STDDEV)
        self._warning_speed = min(self._warning_speed, max(WARNING_SPEED_MIN, candidate))
        return self._warning_speed

    def _generate_battery_low(self) -> float:
        """Generate gradually decreasing speed for battery-low scenario.

        Returns:
            Decaying speed in km/h, bottoming at the battery-low minimum.
        """
        candidate = self._battery_low_speed - BATTERY_LOW_SPEED_DECAY_RATE + random.gauss(0, BATTERY_LOW_SPEED_NOISE_STDDEV)
        self._battery_low_speed = min(self._battery_low_speed, max(BATTERY_LOW_SPEED_MIN, candidate))
        return self._battery_low_speed

    def _accumulate_distance(self, elapsed_seconds: float) -> None:
        """Add distance traveled during the elapsed time interval.

        Uses trapezoidal approximation: distance = speed * time.

        Args:
            elapsed_seconds: Time interval in seconds since last update.
        """
        distance_increment = (self._speed / SECONDS_PER_HOUR) * elapsed_seconds
        self._distance_km += max(0.0, distance_increment)
