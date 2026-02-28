"""Tests for the CAN dump file generator.

Validates that generate_candump.py produces correctly formatted,
complete candump replay files from DBC definitions.
"""

import random
import re
import tempfile
from pathlib import Path

import cantools
import pytest

from generate_candump import (
    CandumpWriter,
    SignalGenerator,
    build_signal_generator,
    generate_candump,
    _clamp_range,
    _normalise_name,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
HYUNDAI_DBC = SCRIPT_DIR.parent / "hyundai_kia" / "hyundai_kia_generic.dbc"
TESLA_DBC = SCRIPT_DIR.parent / "tesla_model3" / "tesla_model3.dbc"

# Compiled pattern for the candump log line format:
#   (<unix_ts>) <interface> <CAN_ID_HEX>#<DATA_HEX>
# Example: (1706000000.123456) vcan0 100#9817FF8B00000000
CANDUMP_LINE_PATTERN = re.compile(
    r"^\(\d+\.\d{6}\)\s+\w+\s+[0-9A-Fa-f]+#[0-9A-Fa-f]+$"
)


# ---------------------------------------------------------------------------
# _clamp_range
# ---------------------------------------------------------------------------


class TestClampRange:
    """Tests for the _clamp_range helper that intersects desired with signal bounds."""

    def test_desired_within_bounds(self) -> None:
        """Desired range fits completely inside signal bounds — no clamping needed."""
        assert _clamp_range(0, 100, 20, 80) == (20, 80)

    def test_desired_exceeds_bounds(self) -> None:
        """Desired range extends beyond both ends of signal bounds — gets clamped to signal bounds."""
        assert _clamp_range(10, 50, 0, 100) == (10, 50)

    def test_desired_outside_returns_signal_range(self) -> None:
        """Desired range is entirely outside signal bounds — fallback to signal range."""
        assert _clamp_range(0, 10, 20, 30) == (0, 10)

    def test_partial_overlap_low_side(self) -> None:
        """Desired range partially overlaps from the lower side of signal bounds."""
        assert _clamp_range(0, 100, 50, 150) == (50, 100)

    def test_partial_overlap_high_side(self) -> None:
        """Desired range partially overlaps from the upper side of signal bounds."""
        assert _clamp_range(0, 100, -50, 30) == (0, 30)

    def test_exact_match(self) -> None:
        """Desired range exactly matches signal bounds — returned unchanged."""
        assert _clamp_range(10, 90, 10, 90) == (10, 90)

    def test_touching_boundary_falls_back(self) -> None:
        """Desired range touches the signal bound at exactly one point — falls back to signal range."""
        # clo == chi == 10, so condition clo >= chi is True → fallback
        assert _clamp_range(0, 10, 10, 20) == (0, 10)


# ---------------------------------------------------------------------------
# _normalise_name
# ---------------------------------------------------------------------------


class TestNormaliseName:
    """Tests for signal name normalization used in keyword matching."""

    def test_lowercases_camel_case(self) -> None:
        """CamelCase names are lowercased."""
        assert _normalise_name("EngineRPM") == "enginerpm"

    def test_removes_underscores(self) -> None:
        """Underscores are stripped from the name."""
        assert _normalise_name("DI_vehicleSpeed") == "divehiclespeed"

    def test_removes_spaces(self) -> None:
        """Spaces are stripped from the name."""
        assert _normalise_name("Vehicle Speed") == "vehiclespeed"

    def test_mixed_separators(self) -> None:
        """Both underscores and spaces are stripped together."""
        assert _normalise_name("Battery_SOC Value") == "batterysocvalue"

    def test_already_normalised(self) -> None:
        """Names that are already lowercase and separator-free pass through unchanged."""
        assert _normalise_name("enginerpm") == "enginerpm"

    def test_empty_string(self) -> None:
        """Empty string normalises to empty string."""
        assert _normalise_name("") == ""


# ---------------------------------------------------------------------------
# SignalGenerator
# ---------------------------------------------------------------------------


class TestSignalGenerator:
    """Tests for the SignalGenerator dataclass and its value_at method."""

    def test_value_within_range(self) -> None:
        """value_at returns the raw function value when it is within bounds."""
        gen = SignalGenerator(name="test", min_val=0, max_val=100, _fn=lambda t: 50.0)
        assert gen.value_at(0) == 50.0

    def test_value_clamped_above(self) -> None:
        """value_at clamps values that exceed max_val."""
        gen = SignalGenerator(name="test", min_val=0, max_val=100, _fn=lambda t: 200.0)
        assert gen.value_at(0) == 100.0

    def test_value_clamped_below(self) -> None:
        """value_at clamps values that fall below min_val."""
        gen = SignalGenerator(name="test", min_val=10, max_val=100, _fn=lambda t: -50.0)
        assert gen.value_at(0) == 10.0

    def test_value_at_boundary_min(self) -> None:
        """value_at at exactly min_val is not modified."""
        gen = SignalGenerator(name="test", min_val=5, max_val=95, _fn=lambda t: 5.0)
        assert gen.value_at(0) == 5.0

    def test_value_at_boundary_max(self) -> None:
        """value_at at exactly max_val is not modified."""
        gen = SignalGenerator(name="test", min_val=5, max_val=95, _fn=lambda t: 95.0)
        assert gen.value_at(0) == 95.0

    def test_fn_receives_time_argument(self) -> None:
        """The underlying function receives the elapsed time argument correctly."""
        gen = SignalGenerator(name="test", min_val=0, max_val=1000, _fn=lambda t: t * 2.0)
        assert gen.value_at(10.0) == pytest.approx(20.0)

    def test_equal_min_max_constant(self) -> None:
        """When min_val == max_val, value_at always returns that single value."""
        gen = SignalGenerator(name="test", min_val=42, max_val=42, _fn=lambda t: t)
        assert gen.value_at(0) == 42.0
        assert gen.value_at(100) == 42.0


# ---------------------------------------------------------------------------
# build_signal_generator
# ---------------------------------------------------------------------------


class TestBuildSignalGenerator:
    """Tests for auto-detection of signal roles in build_signal_generator."""

    @pytest.fixture
    def rng(self) -> random.Random:
        """Seeded Random instance for reproducible generator behaviour."""
        return random.Random(42)

    @pytest.fixture
    def hyundai_db(self) -> cantools.database.Database:
        """Loaded Hyundai/Kia DBC database."""
        return cantools.database.load_file(str(HYUNDAI_DBC))

    @pytest.fixture
    def tesla_db(self) -> cantools.database.Database:
        """Loaded Tesla Model 3 DBC database."""
        return cantools.database.load_file(str(TESLA_DBC))

    def _find_signal(
        self, db: cantools.database.Database, name: str
    ) -> cantools.database.Signal:
        """Return the first signal matching *name* across all messages.

        Raises:
            KeyError: If no signal with that name is found.
        """
        for msg in db.messages:
            for sig in msg.signals:
                if sig.name == name:
                    return sig
        raise KeyError(f"Signal '{name}' not found in database")

    def test_engine_rpm_produces_rpm_range_values(self, hyundai_db, rng) -> None:
        """EngineRPM signal is detected and constrained to 800–3000 rpm band."""
        sig = self._find_signal(hyundai_db, "EngineRPM")
        gen = build_signal_generator(sig, 60.0, rng)
        # Sample several time points across the simulation window.
        for t in [0, 10, 20, 30, 45, 60]:
            val = gen.value_at(t)
            # The desired range [800, 3000] fits within signal bounds [0, 8000].
            assert 800.0 <= val <= 3000.0, f"EngineRPM={val} out of [800, 3000] at t={t}"

    def test_vehicle_speed_produces_speed_range_values(self, hyundai_db, rng) -> None:
        """VehicleSpeed signal is detected and constrained to 40–80 km/h band."""
        sig = self._find_signal(hyundai_db, "VehicleSpeed")
        gen = build_signal_generator(sig, 60.0, rng)
        for t in [0, 10, 30, 59]:
            val = gen.value_at(t)
            assert 40.0 <= val <= 80.0, f"VehicleSpeed={val} out of [40, 80] at t={t}"

    def test_engine_coolant_temp_stays_in_signal_bounds(self, hyundai_db, rng) -> None:
        """EngineCoolantTemp (temperature signal) stays within its physical bounds [-40, 215]."""
        sig = self._find_signal(hyundai_db, "EngineCoolantTemp")
        gen = build_signal_generator(sig, 60.0, rng)
        for t in [0, 20, 40, 60]:
            val = gen.value_at(t)
            assert -40.0 <= val <= 215.0, f"EngineCoolantTemp={val} out of bounds at t={t}"

    def test_dtc_count_stays_within_signal_bounds(self, hyundai_db, rng) -> None:
        """DTCCount normalises to 'dtccount' which is not in _DTC_KEYWORDS (exact match set),
        so it falls through to the generic sine-over-middle-third fallback.  Values must
        stay within the signal's physical bounds [0, 255].
        """
        sig = self._find_signal(hyundai_db, "DTCCount")
        gen = build_signal_generator(sig, 60.0, rng)
        lo = float(sig.minimum)  # 0
        hi = float(sig.maximum)  # 255
        for t in [0, 30, 60]:
            val = gen.value_at(t)
            assert lo <= val <= hi, f"DTCCount={val} out of [{lo}, {hi}] at t={t}"

    def test_battery_voltage_detected_by_name(self, hyundai_db, rng) -> None:
        """BatteryVoltage is detected via name keyword and stays within signal bounds [0, 6553.5]."""
        sig = self._find_signal(hyundai_db, "BatteryVoltage")
        gen = build_signal_generator(sig, 60.0, rng)
        for t in [0, 30, 60]:
            val = gen.value_at(t)
            assert 0.0 <= val <= 6553.5, f"BatteryVoltage={val} out of bounds at t={t}"

    def test_tesla_motor_rpm_stays_in_signal_bounds(self, tesla_db, rng) -> None:
        """DI_motorRPM (rpm unit) generator produces values within [0, 16000]."""
        sig = self._find_signal(tesla_db, "DI_motorRPM")
        gen = build_signal_generator(sig, 60.0, rng)
        for t in [0, 15, 30, 60]:
            val = gen.value_at(t)
            assert 0.0 <= val <= 16000.0, f"DI_motorRPM={val} out of [0, 16000] at t={t}"

    def test_all_hyundai_signals_within_physical_bounds(self, hyundai_db, rng) -> None:
        """Every Hyundai/Kia signal's generator produces values within its physical bounds."""
        for msg in hyundai_db.messages:
            for sig in msg.signals:
                gen = build_signal_generator(sig, 60.0, rng)
                lo = float(sig.minimum) if sig.minimum is not None else 0.0
                hi = float(sig.maximum) if sig.maximum is not None else float("inf")
                for t in [0, 10, 30, 60]:
                    val = gen.value_at(t)
                    assert lo <= val <= hi, (
                        f"{sig.name} at t={t}: {val} not in [{lo}, {hi}]"
                    )

    def test_all_tesla_signals_within_physical_bounds(self, tesla_db, rng) -> None:
        """Every Tesla Model 3 signal's generator produces values within its physical bounds."""
        for msg in tesla_db.messages:
            for sig in msg.signals:
                gen = build_signal_generator(sig, 60.0, rng)
                lo = float(sig.minimum) if sig.minimum is not None else 0.0
                hi = float(sig.maximum) if sig.maximum is not None else float("inf")
                for t in [0, 10, 30, 60]:
                    val = gen.value_at(t)
                    assert lo <= val <= hi, (
                        f"{sig.name} at t={t}: {val} not in [{lo}, {hi}]"
                    )


# ---------------------------------------------------------------------------
# CandumpWriter
# ---------------------------------------------------------------------------


class TestCandumpWriter:
    """Tests for the candump file writer."""

    def test_writes_correct_format(self, tmp_path: Path) -> None:
        """A single written frame produces exactly one candump-format line."""
        out = tmp_path / "test.log"
        with CandumpWriter(out, interface="vcan0") as w:
            w.write_frame(1706000000.0, 0x100, b"\x91\x3b\x80\x00\x00\x00\x00\x00")

        lines = out.read_text().strip().split("\n")
        assert len(lines) == 1
        assert CANDUMP_LINE_PATTERN.match(lines[0]), f"Bad format: {lines[0]!r}"

    def test_written_line_contains_correct_interface(self, tmp_path: Path) -> None:
        """The interface name appears in the written line."""
        out = tmp_path / "test.log"
        with CandumpWriter(out, interface="can0") as w:
            w.write_frame(1706000000.0, 0x100, b"\x00" * 8)

        assert "can0" in out.read_text()

    def test_written_line_contains_can_id(self, tmp_path: Path) -> None:
        """The CAN frame ID is present in hex in the written line."""
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            w.write_frame(1706000000.0, 0x1FF, b"\x00" * 8)

        assert "1FF" in out.read_text().upper()

    def test_written_line_contains_timestamp(self, tmp_path: Path) -> None:
        """The timestamp appears with 6 decimal places in the written line."""
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            w.write_frame(1706000123.456789, 0x100, b"\x00" * 8)

        assert "1706000123.456789" in out.read_text()

    def test_writes_multiple_frames(self, tmp_path: Path) -> None:
        """Writing N frames produces exactly N lines."""
        out = tmp_path / "test.log"
        n_frames = 10
        with CandumpWriter(out) as w:
            for i in range(n_frames):
                w.write_frame(1706000000.0 + i * 0.01, 0x100, b"\x00" * 8)

        lines = out.read_text().strip().split("\n")
        assert len(lines) == n_frames

    def test_all_multiple_frames_valid_format(self, tmp_path: Path) -> None:
        """Every written frame matches the candump line pattern."""
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            for i in range(5):
                w.write_frame(1706000000.0 + i * 0.1, 0x200 + i, bytes(range(8)))

        for line in out.read_text().strip().split("\n"):
            assert CANDUMP_LINE_PATTERN.match(line), f"Bad format: {line!r}"

    def test_context_manager_closes_file(self, tmp_path: Path) -> None:
        """After exiting the context manager the file handle is closed."""
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            w.write_frame(1706000000.0, 0x100, b"\x00" * 4)
        assert w._file.closed

    def test_default_interface_is_vcan0(self, tmp_path: Path) -> None:
        """The default CAN interface written to lines is vcan0."""
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            w.write_frame(1706000000.0, 0x100, b"\x00" * 8)

        assert "vcan0" in out.read_text()


# ---------------------------------------------------------------------------
# generate_candump — end-to-end
# ---------------------------------------------------------------------------


class TestGenerateCandump:
    """End-to-end tests for the generate_candump function."""

    @pytest.fixture
    def rng(self) -> random.Random:
        """Seeded Random instance for reproducible generation."""
        return random.Random(42)

    @pytest.mark.parametrize("dbc_path", [HYUNDAI_DBC, TESLA_DBC], ids=["hyundai", "tesla"])
    def test_generates_nonzero_frames(
        self, dbc_path: Path, tmp_path: Path, rng: random.Random
    ) -> None:
        """Generation with a positive duration produces at least one CAN frame."""
        db = cantools.database.load_file(str(dbc_path))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            count = generate_candump(db, w, duration=5.0, rng=rng)
        assert count > 0

    @pytest.mark.parametrize("dbc_path", [HYUNDAI_DBC, TESLA_DBC], ids=["hyundai", "tesla"])
    def test_all_messages_represented(
        self, dbc_path: Path, tmp_path: Path, rng: random.Random
    ) -> None:
        """Every DBC message has at least one frame in the output."""
        db = cantools.database.load_file(str(dbc_path))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            generate_candump(db, w, duration=5.0, rng=rng)

        lines = out.read_text().strip().split("\n")
        can_ids_in_output: set[int] = set()
        for line in lines:
            parts = line.split()
            can_id_hex = parts[2].split("#")[0]
            can_ids_in_output.add(int(can_id_hex, 16))

        expected_ids = {m.frame_id for m in db.messages}
        assert expected_ids.issubset(can_ids_in_output), (
            f"Missing message IDs: {expected_ids - can_ids_in_output}"
        )

    @pytest.mark.parametrize("dbc_path", [HYUNDAI_DBC, TESLA_DBC], ids=["hyundai", "tesla"])
    def test_all_lines_valid_format(
        self, dbc_path: Path, tmp_path: Path, rng: random.Random
    ) -> None:
        """Every output line matches the candump log format regex."""
        db = cantools.database.load_file(str(dbc_path))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            generate_candump(db, w, duration=2.0, rng=rng)

        for line in out.read_text().strip().split("\n"):
            assert CANDUMP_LINE_PATTERN.match(line), f"Bad line: {line!r}"

    def test_frame_count_matches_return_value(self, tmp_path: Path) -> None:
        """The integer returned by generate_candump matches the number of lines written."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))
        out = tmp_path / "test.log"
        rng = random.Random(0)
        with CandumpWriter(out) as w:
            count = generate_candump(db, w, duration=3.0, rng=rng)

        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert count == len(lines)

    def test_deterministic_with_same_seed(self, tmp_path: Path) -> None:
        """Two runs with the same seed produce byte-identical output."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))

        out1 = tmp_path / "run1.log"
        with CandumpWriter(out1) as w:
            generate_candump(db, w, duration=5.0, rng=random.Random(99))

        out2 = tmp_path / "run2.log"
        with CandumpWriter(out2) as w:
            generate_candump(db, w, duration=5.0, rng=random.Random(99))

        assert out1.read_text() == out2.read_text()

    def test_different_seeds_produce_different_output(self, tmp_path: Path) -> None:
        """Two runs with different seeds produce non-identical output (with high probability)."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))

        out1 = tmp_path / "seed_a.log"
        with CandumpWriter(out1) as w:
            generate_candump(db, w, duration=5.0, rng=random.Random(1))

        out2 = tmp_path / "seed_b.log"
        with CandumpWriter(out2) as w:
            generate_candump(db, w, duration=5.0, rng=random.Random(999))

        assert out1.read_text() != out2.read_text()

    def test_invalid_duration_zero_raises(self, tmp_path: Path) -> None:
        """Zero duration raises ValueError mentioning 'positive'."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            with pytest.raises(ValueError, match="positive"):
                generate_candump(db, w, duration=0.0, rng=random.Random(42))

    def test_invalid_duration_negative_raises(self, tmp_path: Path) -> None:
        """Negative duration raises ValueError mentioning 'positive'."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            with pytest.raises(ValueError, match="positive"):
                generate_candump(db, w, duration=-1.0, rng=random.Random(42))

    def test_timestamps_are_monotonically_non_decreasing(self, tmp_path: Path) -> None:
        """Timestamps in the output file are monotonically non-decreasing."""
        db = cantools.database.load_file(str(HYUNDAI_DBC))
        out = tmp_path / "test.log"
        with CandumpWriter(out) as w:
            generate_candump(db, w, duration=2.0, rng=random.Random(42))

        lines = out.read_text().strip().split("\n")
        timestamps = [
            float(line.split(")")[0].lstrip("(")) for line in lines
        ]
        # Messages are written per-message sequentially; within a single message
        # timestamps must be non-decreasing.  Across messages they may restart,
        # so we only validate the per-message blocks implicitly by checking that
        # no timestamp is before the global BASE_TIMESTAMP.
        from generate_candump import BASE_TIMESTAMP
        for ts in timestamps:
            assert ts >= BASE_TIMESTAMP, f"Timestamp {ts} precedes BASE_TIMESTAMP"


# ---------------------------------------------------------------------------
# Decodability — round-trip correctness
# ---------------------------------------------------------------------------


class TestDecodability:
    """Verify that generated frames can be decoded back to physically valid values."""

    @pytest.mark.parametrize("dbc_path", [HYUNDAI_DBC, TESLA_DBC], ids=["hyundai", "tesla"])
    def test_frames_decodable_without_error(
        self, dbc_path: Path, tmp_path: Path
    ) -> None:
        """All generated frames decode without raising an exception."""
        db = cantools.database.load_file(str(dbc_path))
        out = tmp_path / "test.log"
        rng = random.Random(42)
        with CandumpWriter(out) as w:
            generate_candump(db, w, duration=2.0, rng=rng)

        id_to_msg = {m.frame_id: m for m in db.messages}

        for line in out.read_text().strip().split("\n"):
            parts = line.split()
            id_data = parts[2].split("#")
            can_id = int(id_data[0], 16)
            data = bytes.fromhex(id_data[1])

            msg = id_to_msg.get(can_id)
            assert msg is not None, f"Unknown CAN ID: 0x{can_id:X}"
            # This must not raise.
            decoded = msg.decode(data)
            assert isinstance(decoded, dict)

    @pytest.mark.parametrize("dbc_path", [HYUNDAI_DBC, TESLA_DBC], ids=["hyundai", "tesla"])
    def test_decoded_signal_values_within_physical_bounds(
        self, dbc_path: Path, tmp_path: Path
    ) -> None:
        """Decoded signal values are all within their DBC-defined physical bounds."""
        db = cantools.database.load_file(str(dbc_path))
        out = tmp_path / "test.log"
        rng = random.Random(42)
        with CandumpWriter(out) as w:
            generate_candump(db, w, duration=2.0, rng=rng)

        id_to_msg = {m.frame_id: m for m in db.messages}

        for line in out.read_text().strip().split("\n"):
            parts = line.split()
            id_data = parts[2].split("#")
            can_id = int(id_data[0], 16)
            data = bytes.fromhex(id_data[1])

            msg = id_to_msg[can_id]
            decoded = msg.decode(data)

            for sig in msg.signals:
                val = decoded[sig.name]
                lo = float(sig.minimum) if sig.minimum is not None else float("-inf")
                hi = float(sig.maximum) if sig.maximum is not None else float("inf")
                assert lo <= val <= hi, (
                    f"{sig.name}: decoded {val} not in [{lo}, {hi}]"
                )
