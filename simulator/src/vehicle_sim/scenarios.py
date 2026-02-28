"""Scenario management for vehicle simulation.

Coordinates all sub-simulators (engine, vehicle, HVAC, battery, DTC)
and provides unified signal generation under configurable
driving scenarios.
"""

import logging
from enum import Enum
from typing import Any

from vehicle_sim.battery import BatterySimulator
from vehicle_sim.dtc import DtcSimulator
from vehicle_sim.engine import EngineSimulator
from vehicle_sim.hvac import HvacSimulator
from vehicle_sim.vehicle import VehicleSimulator

logger = logging.getLogger(__name__)


class ScenarioMode(str, Enum):
    """Available driving scenario modes.

    Each mode produces distinct signal behaviors across all
    simulator subsystems:

    - ``NORMAL_DRIVING``: Stable operation, smooth signals.
    - ``ENGINE_WARNING``: Erratic engine with rising temperature and DTCs.
    - ``BATTERY_LOW``: Rapidly depleting battery with reduced performance.
    """

    NORMAL_DRIVING = "normal_driving"
    ENGINE_WARNING = "engine_warning"
    BATTERY_LOW = "battery_low"


class ScenarioManager:
    """Orchestrates all simulator subsystems under a unified scenario.

    Creates and manages instances of all signal simulators,
    delegates signal generation to each, and merges results
    into a single dictionary of VSS path-value pairs.

    Attributes:
        _mode: Currently active scenario mode.
        _engine: Engine RPM and ECT simulator.
        _vehicle: Speed and distance simulator.
        _hvac: HVAC temperature simulator.
        _battery: Traction battery simulator.
        _dtc: Diagnostic trouble code simulator.
    """

    def __init__(self) -> None:
        """Initialize scenario manager with all sub-simulators."""
        self._mode: ScenarioMode = ScenarioMode.NORMAL_DRIVING
        self._engine = EngineSimulator()
        self._vehicle = VehicleSimulator()
        self._hvac = HvacSimulator()
        self._battery = BatterySimulator()
        self._dtc = DtcSimulator()

        logger.info("ScenarioManager initialized with mode: %s", self._mode.value)

    @property
    def mode(self) -> ScenarioMode:
        """Currently active scenario mode."""
        return self._mode

    @property
    def hvac_target_temp(self) -> float:
        """Current HVAC target temperature from the HVAC simulator."""
        return self._hvac.target_temp

    @hvac_target_temp.setter
    def hvac_target_temp(self, value: float) -> None:
        """Update HVAC target temperature (e.g., from external actuator command).

        Args:
            value: Desired temperature in Celsius.  Clamped to valid
                range by the underlying HvacSimulator.
        """
        self._hvac.target_temp = value

    def set_scenario(self, mode: ScenarioMode) -> None:
        """Change the active driving scenario.

        Resets all sub-simulator states to ensure clean
        transitions between scenarios.

        Args:
            mode: The new scenario mode to activate.
        """
        previous = self._mode
        self._mode = mode
        self.reset()
        logger.info(
            "Scenario changed: %s -> %s",
            previous.value, mode.value,
        )

    def generate_all(self, elapsed_seconds: float) -> dict[str, Any]:
        """Generate all signal values from every sub-simulator.

        Delegates to each subsystem's ``generate()`` method and
        merges results into a single dictionary keyed by full
        VSS signal paths.

        Args:
            elapsed_seconds: Time delta since last call in seconds.
                Used by the vehicle simulator for distance integration.

        Returns:
            Dictionary mapping VSS paths to signal values.
            Float values for numeric signals, string for DTC list.
        """
        scenario = self._mode.value
        signals: dict[str, Any] = {}

        signals.update(self._engine.generate(scenario))
        signals.update(self._vehicle.generate(scenario, elapsed_seconds))
        signals.update(self._hvac.generate(scenario))
        signals.update(self._battery.generate(scenario))
        signals.update(self._dtc.generate(scenario))

        logger.debug(
            "Generated %d signals for scenario '%s'",
            len(signals), scenario,
        )

        return signals

    def reset(self) -> None:
        """Reset all sub-simulators to their initial state."""
        self._engine.reset()
        self._vehicle.reset()
        self._hvac.reset()
        self._battery.reset()
        self._dtc.reset()

        logger.info("All simulators reset to initial state")
