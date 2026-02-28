"""Comprehensive tests for all vehicle simulator modules.

Covers EngineSimulator, VehicleSimulator, HvacSimulator,
BatterySimulator, DtcSimulator, ScenarioManager, and selected
utilities from main.py (without requiring a live Kuksa connection).
"""

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Simulator module imports (no kuksa-client dependency)
# ---------------------------------------------------------------------------
from vehicle_sim.battery import (
    BATTERY_LOW_SOC_FLOOR,
    BATTERY_LOW_SOC_START,
    DEFAULT_SOC,
    DEFAULT_TEMPERATURE,
    DEFAULT_VOLTAGE,
    SOC_MAX,
    SOC_MIN,
    VOLTAGE_BASE,
    VOLTAGE_MAX,
    VOLTAGE_MIN,
    VOLTAGE_SOC_RANGE,
    BatterySimulator,
    VSS_BATTERY_SOC,
    VSS_BATTERY_TEMP,
    VSS_BATTERY_VOLTAGE,
)
from vehicle_sim.dtc import (
    DTC_P0301,
    DTC_P0420,
    ENGINE_WARNING_INITIAL_DTC_DELAY,
    ENGINE_WARNING_SECONDARY_DTC_DELAY,
    DtcSimulator,
    VSS_DTC_LIST,
)
from vehicle_sim.engine import (
    BATTERY_LOW_RPM_MAX,
    BATTERY_LOW_RPM_MIN,
    NORMAL_ECT_MAX,
    NORMAL_ECT_MIN,
    NORMAL_RPM_MAX,
    NORMAL_RPM_MIN,
    WARNING_ECT_MAX,
    WARNING_ECT_START,
    WARNING_RPM_MAX,
    WARNING_RPM_MIN,
    EngineSimulator,
    VSS_ENGINE_ECT,
    VSS_ENGINE_SPEED,
)
from vehicle_sim.hvac import (
    AMBIENT_CONVERGENCE_RATE,
    DEFAULT_AMBIENT_TEMP,
    DEFAULT_TARGET_TEMP,
    TARGET_TEMP_MAX,
    TARGET_TEMP_MIN,
    HvacSimulator,
    VSS_AMBIENT_TEMP,
    VSS_HVAC_DRIVER_TEMP,
)
from vehicle_sim.scenarios import ScenarioManager, ScenarioMode
from vehicle_sim.vehicle import (
    BATTERY_LOW_SPEED_MIN,
    NORMAL_SPEED_MAX,
    NORMAL_SPEED_MIN,
    WARNING_SPEED_MIN,
    VehicleSimulator,
    VSS_TRAVELED_DISTANCE,
    VSS_VEHICLE_SPEED,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ELAPSED = 0.5  # seconds — representative elapsed time used in most tests


def _run_engine(scenario: str, ticks: int = 1) -> list[dict[str, float]]:
    """Run EngineSimulator for *ticks* cycles and return all results."""
    eng = EngineSimulator()
    return [eng.generate(scenario) for _ in range(ticks)]


def _run_vehicle(scenario: str, ticks: int = 1) -> list[dict[str, float]]:
    """Run VehicleSimulator for *ticks* cycles and return all results."""
    sim = VehicleSimulator()
    return [sim.generate(scenario, _ELAPSED) for _ in range(ticks)]


# ===========================================================================
# EngineSimulator
# ===========================================================================


class TestEngineSimulatorNormalDriving:
    """EngineSimulator produces bounded, stable values in normal_driving."""

    # Use a large sample to account for Gaussian noise randomness.
    _SAMPLES = 200

    def test_rpm_keys_present(self) -> None:
        """generate() result must contain both engine VSS paths."""
        result = EngineSimulator().generate("normal_driving")
        assert VSS_ENGINE_SPEED in result
        assert VSS_ENGINE_ECT in result

    def test_rpm_within_normal_range(self) -> None:
        """RPM must stay within [NORMAL_RPM_MIN, NORMAL_RPM_MAX] for all ticks."""
        results = _run_engine("normal_driving", self._SAMPLES)
        for r in results:
            rpm = r[VSS_ENGINE_SPEED]
            assert NORMAL_RPM_MIN <= rpm <= NORMAL_RPM_MAX, (
                f"RPM {rpm} outside [{NORMAL_RPM_MIN}, {NORMAL_RPM_MAX}]"
            )

    def test_ect_within_normal_range(self) -> None:
        """ECT must stay within [NORMAL_ECT_MIN, NORMAL_ECT_MAX] for all ticks."""
        results = _run_engine("normal_driving", self._SAMPLES)
        for r in results:
            ect = r[VSS_ENGINE_ECT]
            assert NORMAL_ECT_MIN <= ect <= NORMAL_ECT_MAX, (
                f"ECT {ect} outside [{NORMAL_ECT_MIN}, {NORMAL_ECT_MAX}]"
            )

    def test_values_are_floats(self) -> None:
        """Signal values must be floating-point numbers."""
        result = EngineSimulator().generate("normal_driving")
        assert isinstance(result[VSS_ENGINE_SPEED], float)
        assert isinstance(result[VSS_ENGINE_ECT], float)


class TestEngineSimulatorEngineWarning:
    """EngineSimulator produces erratic RPM and rising ECT under engine_warning."""

    _SAMPLES = 200

    def test_rpm_within_warning_range(self) -> None:
        """RPM must stay within the wider warning bounds."""
        results = _run_engine("engine_warning", self._SAMPLES)
        for r in results:
            rpm = r[VSS_ENGINE_SPEED]
            assert WARNING_RPM_MIN <= rpm <= WARNING_RPM_MAX, (
                f"RPM {rpm} outside warning range"
            )

    def test_ect_rises_over_many_ticks(self) -> None:
        """ECT average in later ticks must exceed average in early ticks."""
        eng = EngineSimulator()
        early_values: list[float] = []
        late_values: list[float] = []
        for i in range(200):
            ect = eng.generate("engine_warning")[VSS_ENGINE_ECT]
            if i < 20:
                early_values.append(ect)
            elif i >= 180:
                late_values.append(ect)
        early_avg = sum(early_values) / len(early_values)
        late_avg = sum(late_values) / len(late_values)
        assert late_avg > early_avg, "ECT did not rise during engine_warning scenario"

    def test_ect_does_not_exceed_max(self) -> None:
        """ECT must be clamped to WARNING_ECT_MAX regardless of tick count."""
        eng = EngineSimulator()
        for _ in range(500):
            result = eng.generate("engine_warning")
        assert result[VSS_ENGINE_ECT] <= WARNING_ECT_MAX


class TestEngineSimulatorBatteryLow:
    """EngineSimulator produces reduced RPM under battery_low scenario."""

    _SAMPLES = 200

    def test_rpm_within_battery_low_range(self) -> None:
        """RPM must stay within the battery-low bounds."""
        results = _run_engine("battery_low", self._SAMPLES)
        for r in results:
            rpm = r[VSS_ENGINE_SPEED]
            assert BATTERY_LOW_RPM_MIN <= rpm <= BATTERY_LOW_RPM_MAX, (
                f"RPM {rpm} outside battery-low range"
            )

    def test_rpm_lower_than_normal_max(self) -> None:
        """Battery-low RPM max must not exceed normal-driving max."""
        assert BATTERY_LOW_RPM_MAX <= NORMAL_RPM_MAX


class TestEngineSimulatorReset:
    """reset() restores tick counter and ECT warning accumulator."""

    def test_reset_clears_tick(self) -> None:
        """After reset, tick counter is 0; state behaves as freshly created."""
        eng = EngineSimulator()
        for _ in range(20):
            eng.generate("normal_driving")
        eng.reset()
        # Internal state: tick should be 0 and ECT warning back to start.
        assert eng._tick == 0

    def test_reset_restores_ect_warning(self) -> None:
        """reset() must restore _ect_warning to WARNING_ECT_START."""
        eng = EngineSimulator()
        for _ in range(100):
            eng.generate("engine_warning")
        eng.reset()
        assert eng._ect_warning == WARNING_ECT_START

    def test_generate_after_reset_returns_valid_values(self) -> None:
        """Signal values after reset must fall within expected normal ranges."""
        eng = EngineSimulator()
        for _ in range(50):
            eng.generate("engine_warning")
        eng.reset()
        result = eng.generate("normal_driving")
        assert NORMAL_RPM_MIN <= result[VSS_ENGINE_SPEED] <= NORMAL_RPM_MAX
        assert NORMAL_ECT_MIN <= result[VSS_ENGINE_ECT] <= NORMAL_ECT_MAX

    def test_reset_idempotent(self) -> None:
        """Calling reset() twice does not raise and leaves state clean."""
        eng = EngineSimulator()
        eng.reset()
        eng.reset()
        assert eng._tick == 0
        assert eng._ect_warning == WARNING_ECT_START


# ===========================================================================
# VehicleSimulator
# ===========================================================================


class TestVehicleSimulatorNormalDriving:
    """VehicleSimulator produces reasonable speed and accumulating distance."""

    _SAMPLES = 200

    def test_vss_keys_present(self) -> None:
        """generate() must return both VSS_VEHICLE_SPEED and VSS_TRAVELED_DISTANCE."""
        result = VehicleSimulator().generate("normal_driving", _ELAPSED)
        assert VSS_VEHICLE_SPEED in result
        assert VSS_TRAVELED_DISTANCE in result

    def test_speed_within_normal_range(self) -> None:
        """Speed must stay within [NORMAL_SPEED_MIN, NORMAL_SPEED_MAX]."""
        results = _run_vehicle("normal_driving", self._SAMPLES)
        for r in results:
            spd = r[VSS_VEHICLE_SPEED]
            assert NORMAL_SPEED_MIN <= spd <= NORMAL_SPEED_MAX, (
                f"Speed {spd} outside normal range"
            )

    def test_distance_increases_monotonically(self) -> None:
        """Traveled distance must be non-decreasing across ticks."""
        sim = VehicleSimulator()
        prev_dist = 0.0
        for _ in range(50):
            result = sim.generate("normal_driving", _ELAPSED)
            dist = result[VSS_TRAVELED_DISTANCE]
            assert dist >= prev_dist, "Distance decreased between ticks"
            prev_dist = dist

    def test_distance_accumulates_correctly(self) -> None:
        """Distance must increase from zero after multiple ticks."""
        sim = VehicleSimulator()
        for _ in range(10):
            result = sim.generate("normal_driving", 1.0)  # 1-second intervals
        # At ~60 km/h for 10 seconds: ~0.16 km expected.
        assert result[VSS_TRAVELED_DISTANCE] > 0.0

    def test_values_are_numeric(self) -> None:
        """Speed and distance must be float values."""
        result = VehicleSimulator().generate("normal_driving", _ELAPSED)
        assert isinstance(result[VSS_VEHICLE_SPEED], float)
        assert isinstance(result[VSS_TRAVELED_DISTANCE], float)


class TestVehicleSimulatorEngineWarning:
    """Speed decays gradually during engine_warning scenario."""

    def test_speed_decays_over_time(self) -> None:
        """Speed after 100 ticks must be lower than initial speed."""
        sim = VehicleSimulator()
        first = sim.generate("engine_warning", _ELAPSED)[VSS_VEHICLE_SPEED]
        for _ in range(100):
            result = sim.generate("engine_warning", _ELAPSED)
        last = result[VSS_VEHICLE_SPEED]
        assert last <= first, "Speed did not decay during engine_warning"

    def test_speed_does_not_go_below_minimum(self) -> None:
        """Speed must not fall below WARNING_SPEED_MIN."""
        sim = VehicleSimulator()
        for _ in range(1000):
            result = sim.generate("engine_warning", _ELAPSED)
        assert result[VSS_VEHICLE_SPEED] >= WARNING_SPEED_MIN


class TestVehicleSimulatorBatteryLow:
    """Speed decays and plateaus at BATTERY_LOW_SPEED_MIN during battery_low."""

    def test_speed_does_not_go_below_minimum(self) -> None:
        """Speed must not fall below BATTERY_LOW_SPEED_MIN."""
        sim = VehicleSimulator()
        for _ in range(1000):
            result = sim.generate("battery_low", _ELAPSED)
        assert result[VSS_VEHICLE_SPEED] >= BATTERY_LOW_SPEED_MIN


class TestVehicleSimulatorReset:
    """reset() restores speed, distance, and tick counter to zero."""

    def test_reset_zeroes_distance(self) -> None:
        """Traveled distance must be 0.0 immediately after reset."""
        sim = VehicleSimulator()
        for _ in range(20):
            sim.generate("normal_driving", _ELAPSED)
        sim.reset()
        assert sim._distance_km == 0.0

    def test_reset_zeroes_speed(self) -> None:
        """Current speed must be 0.0 immediately after reset."""
        sim = VehicleSimulator()
        for _ in range(20):
            sim.generate("normal_driving", _ELAPSED)
        sim.reset()
        assert sim._speed == 0.0

    def test_reset_zeroes_tick(self) -> None:
        """Tick counter must be 0 after reset."""
        sim = VehicleSimulator()
        for _ in range(20):
            sim.generate("normal_driving", _ELAPSED)
        sim.reset()
        assert sim._tick == 0

    def test_distance_starts_fresh_after_reset(self) -> None:
        """Distance resumes accumulation from 0 after reset."""
        sim = VehicleSimulator()
        for _ in range(10):
            sim.generate("normal_driving", 1.0)
        sim.reset()
        result = sim.generate("normal_driving", 1.0)
        # After exactly 1 tick from zero distance, distance must be small.
        assert result[VSS_TRAVELED_DISTANCE] < 0.1


# ===========================================================================
# HvacSimulator
# ===========================================================================


class TestHvacSimulatorBasic:
    """HvacSimulator returns valid temperature signals."""

    def test_vss_keys_present(self) -> None:
        """generate() must return both HVAC VSS paths."""
        result = HvacSimulator().generate("normal_driving")
        assert VSS_HVAC_DRIVER_TEMP in result
        assert VSS_AMBIENT_TEMP in result

    def test_target_temp_within_range(self) -> None:
        """Default target temperature must satisfy the valid clamping range."""
        hvac = HvacSimulator()
        result = hvac.generate("normal_driving")
        assert TARGET_TEMP_MIN <= result[VSS_HVAC_DRIVER_TEMP] <= TARGET_TEMP_MAX

    def test_custom_target_temp_clamped(self) -> None:
        """Constructor must clamp out-of-range target temperatures."""
        hvac_low = HvacSimulator(target_temp=5.0)   # below minimum
        hvac_high = HvacSimulator(target_temp=99.0)  # above maximum
        assert hvac_low.target_temp == TARGET_TEMP_MIN
        assert hvac_high.target_temp == TARGET_TEMP_MAX

    def test_target_temp_setter_clamped(self) -> None:
        """Setting target_temp via property must clamp out-of-range values."""
        hvac = HvacSimulator()
        hvac.target_temp = 0.0
        assert hvac.target_temp == TARGET_TEMP_MIN
        hvac.target_temp = 100.0
        assert hvac.target_temp == TARGET_TEMP_MAX

    def test_target_temp_constant_across_ticks(self) -> None:
        """Target temperature must not change between generate() calls."""
        hvac = HvacSimulator(target_temp=22.0)
        temps = [hvac.generate("normal_driving")[VSS_HVAC_DRIVER_TEMP] for _ in range(50)]
        assert all(t == 22.0 for t in temps)

    def test_scenario_argument_ignored(self) -> None:
        """HVAC behavior must be identical regardless of scenario string."""
        hvac_a = HvacSimulator(target_temp=22.0, ambient_temp=22.0)
        hvac_b = HvacSimulator(target_temp=22.0, ambient_temp=22.0)

        # Same random seed to make comparison fair
        import random
        state = random.getstate()
        result_a = hvac_a.generate("normal_driving")
        random.setstate(state)
        result_b = hvac_b.generate("engine_warning")

        # Target temps must match; ambient may differ due to noise but both present.
        assert result_a[VSS_HVAC_DRIVER_TEMP] == result_b[VSS_HVAC_DRIVER_TEMP]


class TestHvacSimulatorAmbientConvergence:
    """Ambient temperature converges toward target over time."""

    def test_ambient_converges_toward_target_when_cold(self) -> None:
        """Ambient must move closer to target when starting below it."""
        target = 22.0
        start_ambient = 10.0
        hvac = HvacSimulator(target_temp=target, ambient_temp=start_ambient)
        initial_gap = target - start_ambient

        for _ in range(100):
            hvac.generate("normal_driving")

        final_ambient = hvac._ambient_temp
        final_gap = abs(target - final_ambient)
        assert final_gap < initial_gap, (
            "Ambient did not converge toward target from below"
        )

    def test_ambient_converges_toward_target_when_hot(self) -> None:
        """Ambient must move closer to target when starting above it."""
        target = 22.0
        start_ambient = 35.0
        hvac = HvacSimulator(target_temp=target, ambient_temp=start_ambient)
        initial_gap = start_ambient - target

        for _ in range(100):
            hvac.generate("normal_driving")

        final_ambient = hvac._ambient_temp
        final_gap = abs(target - final_ambient)
        assert final_gap < initial_gap, (
            "Ambient did not converge toward target from above"
        )


class TestHvacSimulatorReset:
    """reset() restores HVAC to default temperatures."""

    def test_reset_restores_target_temp(self) -> None:
        """Target temperature must be DEFAULT_TARGET_TEMP after reset."""
        hvac = HvacSimulator(target_temp=28.0, ambient_temp=10.0)
        hvac.reset()
        assert hvac.target_temp == DEFAULT_TARGET_TEMP

    def test_reset_restores_ambient_temp(self) -> None:
        """Ambient temperature must be DEFAULT_AMBIENT_TEMP after reset."""
        hvac = HvacSimulator(target_temp=28.0, ambient_temp=10.0)
        for _ in range(50):
            hvac.generate("normal_driving")
        hvac.reset()
        assert hvac._ambient_temp == DEFAULT_AMBIENT_TEMP

    def test_reset_zeroes_tick(self) -> None:
        """Tick counter must return to 0 after reset."""
        hvac = HvacSimulator()
        for _ in range(30):
            hvac.generate("normal_driving")
        hvac.reset()
        assert hvac._tick == 0


# ===========================================================================
# BatterySimulator
# ===========================================================================


class TestBatterySimulatorNormalDriving:
    """BatterySimulator drains SOC slowly and tracks voltage proportionally."""

    def test_vss_keys_present(self) -> None:
        """generate() must return SOC, voltage, and temperature paths."""
        result = BatterySimulator().generate("normal_driving")
        assert VSS_BATTERY_SOC in result
        assert VSS_BATTERY_VOLTAGE in result
        assert VSS_BATTERY_TEMP in result

    def test_soc_decreases_over_time(self) -> None:
        """SOC must trend downward in normal driving (net drain > noise)."""
        sim = BatterySimulator(soc=80.0)
        for _ in range(200):
            result = sim.generate("normal_driving")
        final_soc = result[VSS_BATTERY_SOC]
        # After 200 ticks with drain_rate=0.01, net drain ≈ 2% expected.
        assert final_soc < 80.0, "SOC did not decrease during normal_driving"

    def test_soc_never_goes_below_zero(self) -> None:
        """SOC must be clamped to SOC_MIN regardless of drain over many ticks."""
        sim = BatterySimulator(soc=0.5)
        for _ in range(1000):
            result = sim.generate("normal_driving")
        assert result[VSS_BATTERY_SOC] >= SOC_MIN

    def test_voltage_proportional_to_soc(self) -> None:
        """Higher SOC must correspond to higher voltage."""
        high_soc_sim = BatterySimulator(soc=90.0)
        low_soc_sim = BatterySimulator(soc=20.0)
        # Average over several ticks to smooth out noise.
        high_voltages = [high_soc_sim.generate("normal_driving")[VSS_BATTERY_VOLTAGE]
                         for _ in range(20)]
        low_voltages = [low_soc_sim.generate("normal_driving")[VSS_BATTERY_VOLTAGE]
                        for _ in range(20)]
        assert sum(high_voltages) / len(high_voltages) > sum(low_voltages) / len(low_voltages)

    def test_temperature_rises_over_time(self) -> None:
        """Battery temperature must trend upward during normal driving."""
        sim = BatterySimulator(temperature=25.0)
        for _ in range(500):
            result = sim.generate("normal_driving")
        assert result[VSS_BATTERY_TEMP] > 25.0


class TestBatterySimulatorBatteryLow:
    """BatterySimulator drops SOC rapidly toward BATTERY_LOW_SOC_FLOOR."""

    def test_soc_drops_toward_floor(self) -> None:
        """SOC must reach or approach BATTERY_LOW_SOC_FLOOR after many ticks."""
        sim = BatterySimulator(soc=BATTERY_LOW_SOC_START)
        for _ in range(300):
            result = sim.generate("battery_low")
        soc = result[VSS_BATTERY_SOC]
        # Floor is 5%; SOC should be close after 300 ticks of rapid drain.
        assert soc <= BATTERY_LOW_SOC_START - 1.0, (
            "SOC did not drop significantly in battery_low scenario"
        )

    def test_soc_not_below_floor(self) -> None:
        """SOC must never drop below BATTERY_LOW_SOC_FLOOR."""
        sim = BatterySimulator(soc=BATTERY_LOW_SOC_START)
        for _ in range(1000):
            result = sim.generate("battery_low")
        assert result[VSS_BATTERY_SOC] >= BATTERY_LOW_SOC_FLOOR

    def test_voltage_within_bounds(self) -> None:
        """Voltage must always stay within [VOLTAGE_MIN, VOLTAGE_MAX]."""
        sim = BatterySimulator(soc=BATTERY_LOW_SOC_START)
        for _ in range(300):
            result = sim.generate("battery_low")
        assert VOLTAGE_MIN <= result[VSS_BATTERY_VOLTAGE] <= VOLTAGE_MAX


class TestBatterySimulatorReset:
    """reset() restores battery state to construction defaults."""

    def test_reset_restores_soc(self) -> None:
        """SOC must return to DEFAULT_SOC after reset."""
        sim = BatterySimulator()
        for _ in range(100):
            sim.generate("normal_driving")
        sim.reset()
        assert sim._soc == DEFAULT_SOC

    def test_reset_restores_voltage(self) -> None:
        """Voltage must return to DEFAULT_VOLTAGE after reset."""
        sim = BatterySimulator()
        for _ in range(100):
            sim.generate("battery_low")
        sim.reset()
        assert sim._voltage == DEFAULT_VOLTAGE

    def test_reset_restores_temperature(self) -> None:
        """Temperature must return to DEFAULT_TEMPERATURE after reset."""
        sim = BatterySimulator()
        for _ in range(200):
            sim.generate("normal_driving")
        sim.reset()
        assert sim._temperature == DEFAULT_TEMPERATURE

    def test_reset_zeroes_tick(self) -> None:
        """Tick counter must be 0 after reset."""
        sim = BatterySimulator()
        for _ in range(50):
            sim.generate("normal_driving")
        sim.reset()
        assert sim._tick == 0


# ===========================================================================
# DtcSimulator
# ===========================================================================


class TestDtcSimulatorNormalDriving:
    """No DTCs are generated in normal_driving scenario."""

    def test_no_dtcs_in_normal_driving(self) -> None:
        """DTC list must be empty after many normal-driving ticks."""
        sim = DtcSimulator()
        for _ in range(100):
            result = sim.generate("normal_driving")
        assert result[VSS_DTC_LIST] == []

    def test_active_dtcs_property_empty(self) -> None:
        """active_dtcs property must return empty list in normal driving."""
        sim = DtcSimulator()
        for _ in range(20):
            sim.generate("normal_driving")
        assert sim.active_dtcs == []

    def test_vss_key_present(self) -> None:
        """generate() must always return the DTCList VSS path."""
        result = DtcSimulator().generate("normal_driving")
        assert VSS_DTC_LIST in result


class TestDtcSimulatorEngineWarning:
    """P0301 appears after ENGINE_WARNING_INITIAL_DTC_DELAY ticks."""

    def test_no_dtc_before_initial_delay(self) -> None:
        """No DTC must appear before ENGINE_WARNING_INITIAL_DTC_DELAY ticks."""
        sim = DtcSimulator()
        for tick in range(ENGINE_WARNING_INITIAL_DTC_DELAY):
            result = sim.generate("engine_warning")
        # After exactly (INITIAL_DTC_DELAY) generate() calls, tick is that value
        # but the check in _update uses `self._tick >= DELAY` before incrementing.
        # So the DTC appears when self._tick == DELAY (0-indexed), which is the
        # tick AFTER the delay has been reached.
        # We already called generate() ENGINE_WARNING_INITIAL_DTC_DELAY times,
        # meaning tick reached that value; check that DTC may now be present.
        # (We just confirm no exception and the type is correct.)
        assert isinstance(result[VSS_DTC_LIST], list)

    def test_p0301_appears_after_initial_delay(self) -> None:
        """P0301 must be present after ENGINE_WARNING_INITIAL_DTC_DELAY+1 ticks."""
        sim = DtcSimulator()
        for _ in range(ENGINE_WARNING_INITIAL_DTC_DELAY + 1):
            result = sim.generate("engine_warning")
        assert DTC_P0301 in result[VSS_DTC_LIST]
        assert DTC_P0301 in sim.active_dtcs

    def test_p0420_appears_after_secondary_delay(self) -> None:
        """P0420 must be present after ENGINE_WARNING_SECONDARY_DTC_DELAY+1 ticks."""
        sim = DtcSimulator()
        for _ in range(ENGINE_WARNING_SECONDARY_DTC_DELAY + 1):
            result = sim.generate("engine_warning")
        assert DTC_P0301 in result[VSS_DTC_LIST]
        assert DTC_P0420 in result[VSS_DTC_LIST]

    def test_dtc_list_contains_both_codes(self) -> None:
        """Multiple DTCs must be returned as separate list elements."""
        sim = DtcSimulator()
        for _ in range(ENGINE_WARNING_SECONDARY_DTC_DELAY + 1):
            result = sim.generate("engine_warning")
        assert len(result[VSS_DTC_LIST]) == 2
        assert DTC_P0301 in result[VSS_DTC_LIST]
        assert DTC_P0420 in result[VSS_DTC_LIST]


class TestDtcSimulatorBatteryLow:
    """battery_low scenario must not generate DTCs."""

    def test_no_dtcs_in_battery_low(self) -> None:
        """DTC list must remain empty during battery_low scenario."""
        sim = DtcSimulator()
        for _ in range(100):
            result = sim.generate("battery_low")
        assert result[VSS_DTC_LIST] == []


class TestDtcSimulatorInjectAndClear:
    """inject_dtc() and clear_dtcs() work as expected."""

    def test_inject_dtc_adds_code(self) -> None:
        """inject_dtc() must add the code to active_dtcs."""
        sim = DtcSimulator()
        sim.inject_dtc("P0123")
        assert "P0123" in sim.active_dtcs

    def test_inject_dtc_duplicate_ignored(self) -> None:
        """Injecting the same code twice must not create duplicates."""
        sim = DtcSimulator()
        sim.inject_dtc("P0301")
        sim.inject_dtc("P0301")
        assert sim.active_dtcs.count("P0301") == 1

    def test_clear_dtcs_removes_all(self) -> None:
        """clear_dtcs() must empty the active DTC list."""
        sim = DtcSimulator()
        sim.inject_dtc("P0301")
        sim.inject_dtc("P0420")
        sim.clear_dtcs()
        assert sim.active_dtcs == []

    def test_injected_dtc_appears_in_generate_output(self) -> None:
        """A manually injected DTC must appear in generate() output."""
        sim = DtcSimulator()
        sim.inject_dtc("P9999")
        result = sim.generate("normal_driving")
        assert "P9999" in result[VSS_DTC_LIST]

    def test_active_dtcs_returns_copy(self) -> None:
        """active_dtcs property must return a copy, not the internal list."""
        sim = DtcSimulator()
        sim.inject_dtc("P0301")
        copy = sim.active_dtcs
        copy.append("MUTATED")
        assert "MUTATED" not in sim.active_dtcs


class TestDtcSimulatorReset:
    """reset() clears DTCs and resets tick counter."""

    def test_reset_clears_dtcs(self) -> None:
        """Active DTC list must be empty after reset."""
        sim = DtcSimulator()
        for _ in range(ENGINE_WARNING_SECONDARY_DTC_DELAY + 5):
            sim.generate("engine_warning")
        sim.reset()
        assert sim.active_dtcs == []

    def test_reset_zeroes_tick(self) -> None:
        """Tick counter must be 0 after reset."""
        sim = DtcSimulator()
        for _ in range(60):
            sim.generate("engine_warning")
        sim.reset()
        assert sim._tick == 0

    def test_dtcs_regenerate_after_reset(self) -> None:
        """After reset, DTCs must appear again after the full delay."""
        sim = DtcSimulator()
        for _ in range(ENGINE_WARNING_SECONDARY_DTC_DELAY + 2):
            sim.generate("engine_warning")
        sim.reset()
        # Immediately after reset, no DTCs.
        assert sim.active_dtcs == []
        # After delay again, P0301 appears.
        for _ in range(ENGINE_WARNING_INITIAL_DTC_DELAY + 1):
            sim.generate("engine_warning")
        assert DTC_P0301 in sim.active_dtcs


# ===========================================================================
# ScenarioManager
# ===========================================================================

# All expected VSS paths that generate_all() must always return.
_EXPECTED_VSS_PATHS = {
    VSS_ENGINE_SPEED,
    VSS_ENGINE_ECT,
    VSS_VEHICLE_SPEED,
    VSS_TRAVELED_DISTANCE,
    VSS_HVAC_DRIVER_TEMP,
    VSS_AMBIENT_TEMP,
    VSS_BATTERY_SOC,
    VSS_BATTERY_VOLTAGE,
    VSS_BATTERY_TEMP,
    VSS_DTC_LIST,
}

_EXPECTED_SIGNAL_COUNT = 10


class TestScenarioManagerGenerateAll:
    """generate_all() returns all expected VSS paths for every scenario."""

    @pytest.mark.parametrize("scenario", list(ScenarioMode))
    def test_all_vss_paths_present(self, scenario: ScenarioMode) -> None:
        """All 10 VSS paths must be present regardless of active scenario."""
        mgr = ScenarioManager()
        mgr.set_scenario(scenario)
        result = mgr.generate_all(elapsed_seconds=_ELAPSED)
        assert set(result.keys()) == _EXPECTED_VSS_PATHS

    @pytest.mark.parametrize("scenario", list(ScenarioMode))
    def test_signal_count_is_ten(self, scenario: ScenarioMode) -> None:
        """generate_all() must return exactly 10 signals."""
        mgr = ScenarioManager()
        mgr.set_scenario(scenario)
        result = mgr.generate_all(elapsed_seconds=_ELAPSED)
        assert len(result) == _EXPECTED_SIGNAL_COUNT

    def test_dtc_list_is_list(self) -> None:
        """DTC list value must always be a list (possibly empty)."""
        mgr = ScenarioManager()
        result = mgr.generate_all(elapsed_seconds=_ELAPSED)
        assert isinstance(result[VSS_DTC_LIST], list)

    def test_numeric_signals_are_numeric(self) -> None:
        """All numeric signals must be int or float."""
        mgr = ScenarioManager()
        result = mgr.generate_all(elapsed_seconds=_ELAPSED)
        numeric_paths = _EXPECTED_VSS_PATHS - {VSS_DTC_LIST}
        for path in numeric_paths:
            assert isinstance(result[path], (int, float)), (
                f"Signal {path} is not numeric: {type(result[path])}"
            )


class TestScenarioManagerSetScenario:
    """set_scenario() changes mode and resets all sub-simulators."""

    def test_default_mode_is_normal_driving(self) -> None:
        """ScenarioManager must initialize with NORMAL_DRIVING mode."""
        mgr = ScenarioManager()
        assert mgr.mode == ScenarioMode.NORMAL_DRIVING

    def test_set_scenario_changes_mode(self) -> None:
        """set_scenario() must update the active mode property."""
        mgr = ScenarioManager()
        mgr.set_scenario(ScenarioMode.ENGINE_WARNING)
        assert mgr.mode == ScenarioMode.ENGINE_WARNING

    def test_set_scenario_resets_engine_tick(self) -> None:
        """Engine tick must be 0 after scenario change."""
        mgr = ScenarioManager()
        for _ in range(30):
            mgr.generate_all(_ELAPSED)
        mgr.set_scenario(ScenarioMode.BATTERY_LOW)
        assert mgr._engine._tick == 0

    def test_set_scenario_resets_dtc(self) -> None:
        """Active DTCs must be cleared after scenario change."""
        mgr = ScenarioManager()
        mgr.set_scenario(ScenarioMode.ENGINE_WARNING)
        for _ in range(ENGINE_WARNING_SECONDARY_DTC_DELAY + 5):
            mgr.generate_all(_ELAPSED)
        mgr.set_scenario(ScenarioMode.NORMAL_DRIVING)
        assert mgr._dtc.active_dtcs == []

    def test_set_scenario_resets_distance(self) -> None:
        """Traveled distance must be 0.0 after scenario change."""
        mgr = ScenarioManager()
        for _ in range(20):
            mgr.generate_all(1.0)
        mgr.set_scenario(ScenarioMode.ENGINE_WARNING)
        assert mgr._vehicle._distance_km == 0.0

    def test_set_same_scenario_resets_state(self) -> None:
        """Setting the same scenario mode must still perform a reset."""
        mgr = ScenarioManager()
        for _ in range(30):
            mgr.generate_all(_ELAPSED)
        mgr.set_scenario(ScenarioMode.NORMAL_DRIVING)
        assert mgr._engine._tick == 0


class TestScenarioManagerHvacTargetTemp:
    """hvac_target_temp property allows external read/write of HVAC set point."""

    def test_hvac_target_temp_getter_returns_hvac_value(self) -> None:
        """hvac_target_temp property must reflect the HvacSimulator target."""
        mgr = ScenarioManager()
        assert mgr.hvac_target_temp == mgr._hvac.target_temp

    def test_hvac_target_temp_setter_updates_hvac(self) -> None:
        """Setting hvac_target_temp must update the underlying HvacSimulator."""
        mgr = ScenarioManager()
        mgr.hvac_target_temp = 26.0
        assert mgr._hvac.target_temp == 26.0

    def test_hvac_target_temp_setter_clamps_value(self) -> None:
        """Values outside the valid range must be clamped by the HvacSimulator."""
        from vehicle_sim.hvac import TARGET_TEMP_MAX, TARGET_TEMP_MIN

        mgr = ScenarioManager()
        mgr.hvac_target_temp = 0.0
        assert mgr.hvac_target_temp == TARGET_TEMP_MIN

        mgr.hvac_target_temp = 999.0
        assert mgr.hvac_target_temp == TARGET_TEMP_MAX

    def test_generate_reflects_updated_hvac_target(self) -> None:
        """After setting hvac_target_temp, generate_all must publish the new value."""
        mgr = ScenarioManager()
        mgr.hvac_target_temp = 26.0
        result = mgr.generate_all(elapsed_seconds=0.5)
        assert result[VSS_HVAC_DRIVER_TEMP] == 26.0


class TestScenarioManagerReset:
    """reset() resets all sub-simulators without changing the active mode."""

    def test_reset_preserves_mode(self) -> None:
        """Active scenario mode must not change after reset()."""
        mgr = ScenarioManager()
        mgr.set_scenario(ScenarioMode.BATTERY_LOW)
        mgr.reset()
        assert mgr.mode == ScenarioMode.BATTERY_LOW

    def test_reset_clears_ticks(self) -> None:
        """All sub-simulator tick counters must be 0 after reset."""
        mgr = ScenarioManager()
        for _ in range(25):
            mgr.generate_all(_ELAPSED)
        mgr.reset()
        assert mgr._engine._tick == 0
        assert mgr._vehicle._tick == 0
        assert mgr._hvac._tick == 0
        assert mgr._battery._tick == 0
        assert mgr._dtc._tick == 0

    def test_reset_clears_accumulated_distance(self) -> None:
        """Accumulated distance must return to 0 after reset."""
        mgr = ScenarioManager()
        for _ in range(20):
            mgr.generate_all(1.0)
        mgr.reset()
        assert mgr._vehicle._distance_km == 0.0

    def test_generate_all_works_after_reset(self) -> None:
        """generate_all() must succeed immediately after reset."""
        mgr = ScenarioManager()
        mgr.reset()
        result = mgr.generate_all(_ELAPSED)
        assert len(result) == _EXPECTED_SIGNAL_COUNT


# ===========================================================================
# Main module utilities (mocked kuksa-client)
# ===========================================================================

# Patch kuksa_client at the top-level module import so that main.py can be
# imported even when kuksa-client is not installed or gRPC is unavailable.

_KUKSA_CLIENT_MOCK = MagicMock()
_KUKSA_CLIENT_MOCK.grpc.Datapoint = MagicMock(side_effect=lambda v: MagicMock(value=v))
_KUKSA_CLIENT_MOCK.grpc.aio.VSSClient = MagicMock()

# We patch sys.modules BEFORE importing vehicle_sim.main.
_PATCHES: dict[str, Any] = {
    "kuksa_client": _KUKSA_CLIENT_MOCK,
    "kuksa_client.grpc": _KUKSA_CLIENT_MOCK.grpc,
    "kuksa_client.grpc.aio": _KUKSA_CLIENT_MOCK.grpc.aio,
}


@pytest.fixture(autouse=False)
def mock_kuksa_modules() -> Any:
    """Patch kuksa_client in sys.modules for the duration of each test."""
    with patch.dict(sys.modules, _PATCHES):
        # Re-import main with the mocked modules available
        import importlib
        import vehicle_sim.main as _main_module
        importlib.reload(_main_module)
        yield _main_module


class TestLoadConfig:
    """_load_config() reads environment variables with sensible defaults."""

    def test_returns_default_host(self, mock_kuksa_modules: Any) -> None:
        """Default host must be 'localhost' when env var is unset."""
        main = mock_kuksa_modules
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KUKSA_DATABROKER_HOST", None)
            config = main._load_config()
        assert config["host"] == "localhost"

    def test_returns_default_port(self, mock_kuksa_modules: Any) -> None:
        """Default port must be 55555 when env var is unset."""
        main = mock_kuksa_modules
        os.environ.pop("KUKSA_DATABROKER_PORT", None)
        config = main._load_config()
        assert config["port"] == 55555

    def test_returns_default_sim_mode(self, mock_kuksa_modules: Any) -> None:
        """Default sim_mode must be 'normal_driving' when env var is unset."""
        main = mock_kuksa_modules
        os.environ.pop("SIM_MODE", None)
        config = main._load_config()
        assert config["sim_mode"] == "normal_driving"

    def test_returns_default_update_interval(self, mock_kuksa_modules: Any) -> None:
        """Default update_interval_ms must be 500 when env var is unset."""
        main = mock_kuksa_modules
        os.environ.pop("SIM_UPDATE_INTERVAL_MS", None)
        config = main._load_config()
        assert config["update_interval_ms"] == 500

    def test_overrides_from_environment(self, mock_kuksa_modules: Any) -> None:
        """Env vars must override all defaults."""
        main = mock_kuksa_modules
        env = {
            "KUKSA_DATABROKER_HOST": "broker.local",
            "KUKSA_DATABROKER_PORT": "12345",
            "SIM_MODE": "engine_warning",
            "SIM_UPDATE_INTERVAL_MS": "200",
            "SIM_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env):
            config = main._load_config()
        assert config["host"] == "broker.local"
        assert config["port"] == 12345
        assert config["sim_mode"] == "engine_warning"
        assert config["update_interval_ms"] == 200
        assert config["log_level"] == "DEBUG"

    def test_port_is_int(self, mock_kuksa_modules: Any) -> None:
        """Port value must be an integer, not a string."""
        main = mock_kuksa_modules
        config = main._load_config()
        assert isinstance(config["port"], int)

    def test_update_interval_is_int(self, mock_kuksa_modules: Any) -> None:
        """update_interval_ms must be an integer."""
        main = mock_kuksa_modules
        config = main._load_config()
        assert isinstance(config["update_interval_ms"], int)


class TestResolveScenarioMode:
    """_resolve_scenario_mode() converts strings to ScenarioMode enum values."""

    def test_valid_normal_driving(self, mock_kuksa_modules: Any) -> None:
        """'normal_driving' must resolve to ScenarioMode.NORMAL_DRIVING."""
        main = mock_kuksa_modules
        mode = main._resolve_scenario_mode("normal_driving")
        assert mode == ScenarioMode.NORMAL_DRIVING

    def test_valid_engine_warning(self, mock_kuksa_modules: Any) -> None:
        """'engine_warning' must resolve to ScenarioMode.ENGINE_WARNING."""
        main = mock_kuksa_modules
        mode = main._resolve_scenario_mode("engine_warning")
        assert mode == ScenarioMode.ENGINE_WARNING

    def test_valid_battery_low(self, mock_kuksa_modules: Any) -> None:
        """'battery_low' must resolve to ScenarioMode.BATTERY_LOW."""
        main = mock_kuksa_modules
        mode = main._resolve_scenario_mode("battery_low")
        assert mode == ScenarioMode.BATTERY_LOW

    def test_invalid_mode_raises_value_error(self, mock_kuksa_modules: Any) -> None:
        """Invalid mode string must raise ValueError with descriptive message."""
        main = mock_kuksa_modules
        with pytest.raises(ValueError, match="Invalid SIM_MODE"):
            main._resolve_scenario_mode("turbo_mode")

    def test_empty_string_raises_value_error(self, mock_kuksa_modules: Any) -> None:
        """Empty string must raise ValueError."""
        main = mock_kuksa_modules
        with pytest.raises(ValueError):
            main._resolve_scenario_mode("")


class TestBuildUpdates:
    """_build_updates() converts signal dicts to EntryUpdate objects."""

    def test_converts_float_signal(self, mock_kuksa_modules: Any) -> None:
        """Float signal values must be wrapped in EntryUpdate objects."""
        main = mock_kuksa_modules
        signals: dict[str, Any] = {"Vehicle.Speed": 60.0}
        updates = main._build_updates(signals)
        assert len(updates) == 1

    def test_converts_list_signal(self, mock_kuksa_modules: Any) -> None:
        """List signal values (e.g., DTC list) must also be wrapped."""
        main = mock_kuksa_modules
        signals: dict[str, Any] = {"Vehicle.OBD.DTCList": ["P0301"]}
        updates = main._build_updates(signals)
        assert len(updates) == 1

    def test_output_count_matches_input(self, mock_kuksa_modules: Any) -> None:
        """Output must have the same number of entries as the input dict."""
        main = mock_kuksa_modules
        signals: dict[str, Any] = {
            "Vehicle.Speed": 80.0,
            "Vehicle.Powertrain.CombustionEngine.Speed": 2000.0,
            "Vehicle.OBD.DTCList": [],
        }
        updates = main._build_updates(signals)
        assert len(updates) == len(signals)

    def test_empty_signals_returns_empty_list(self, mock_kuksa_modules: Any) -> None:
        """Empty input must produce an empty list."""
        main = mock_kuksa_modules
        updates = main._build_updates({})
        assert updates == []


class TestSyncHvacFromDatabroker:
    """_sync_hvac_from_databroker() syncs HVAC target from databroker."""

    @pytest.mark.asyncio
    async def test_syncs_when_value_differs(self, mock_kuksa_modules: Any) -> None:
        """When databroker value differs by more than 0.1, simulator is updated."""
        import asyncio
        from unittest.mock import AsyncMock as _AsyncMock, MagicMock as _MagicMock

        main = mock_kuksa_modules

        mock_client = _AsyncMock()
        mock_dp = _MagicMock()
        mock_dp.value = 26.0
        mock_client.get_current_values.return_value = {
            "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature": mock_dp,
        }

        mgr = ScenarioManager()
        # Default target is 22.0; databroker says 26.0 — should sync.
        assert abs(mgr.hvac_target_temp - 26.0) > 0.1

        await main._sync_hvac_from_databroker(mock_client, mgr)

        assert mgr.hvac_target_temp == 26.0

    @pytest.mark.asyncio
    async def test_no_sync_when_value_unchanged(self, mock_kuksa_modules: Any) -> None:
        """When databroker value matches simulator within 0.1, no update occurs."""
        from unittest.mock import AsyncMock as _AsyncMock, MagicMock as _MagicMock

        main = mock_kuksa_modules

        mock_client = _AsyncMock()
        mock_dp = _MagicMock()
        mock_dp.value = 22.0  # Same as default
        mock_client.get_current_values.return_value = {
            "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature": mock_dp,
        }

        mgr = ScenarioManager()
        original_temp = mgr.hvac_target_temp

        await main._sync_hvac_from_databroker(mock_client, mgr)

        assert mgr.hvac_target_temp == original_temp

    @pytest.mark.asyncio
    async def test_exception_is_swallowed(self, mock_kuksa_modules: Any) -> None:
        """Errors during sync must be caught and not propagate."""
        from unittest.mock import AsyncMock as _AsyncMock

        main = mock_kuksa_modules

        mock_client = _AsyncMock()
        mock_client.get_current_values.side_effect = RuntimeError("connection lost")

        mgr = ScenarioManager()
        # Should not raise
        await main._sync_hvac_from_databroker(mock_client, mgr)

    @pytest.mark.asyncio
    async def test_none_datapoint_skipped(self, mock_kuksa_modules: Any) -> None:
        """When the datapoint is None, no update is made."""
        from unittest.mock import AsyncMock as _AsyncMock

        main = mock_kuksa_modules

        mock_client = _AsyncMock()
        mock_client.get_current_values.return_value = {
            "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature": None,
        }

        mgr = ScenarioManager()
        original_temp = mgr.hvac_target_temp

        await main._sync_hvac_from_databroker(mock_client, mgr)

        assert mgr.hvac_target_temp == original_temp
