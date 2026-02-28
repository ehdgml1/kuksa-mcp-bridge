"""Integration tests for DBC feeder vehicle profiles.

Validates that DBC files, VSS-DBC mappings, and candump replay files
are consistent across all vehicle profiles. These tests run without
Docker or Kuksa Databroker — they verify the static data pipeline
configuration is correct.

Run with:
    pytest tests/test_dbc_feeder.py -v
"""

import json
import re
from pathlib import Path
from typing import Any

import cantools
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DBC_ROOT: Path = Path(__file__).resolve().parent.parent / "dbc"

EXPECTED_VSS_PATHS: frozenset[str] = frozenset(
    {
        "Vehicle.Speed",
        "Vehicle.TraveledDistance",
        "Vehicle.Powertrain.CombustionEngine.Speed",
        "Vehicle.Powertrain.CombustionEngine.ECT",
        "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
        "Vehicle.Powertrain.TractionBattery.CurrentVoltage",
        "Vehicle.Powertrain.TractionBattery.Temperature",
        "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature",
        "Vehicle.Cabin.HVAC.AmbientAirTemperature",
    }
)

# Candump lines must follow: (timestamp) interface CANID#HEXDATA
CANDUMP_LINE_RE: re.Pattern[str] = re.compile(
    r"^\(\d+\.\d{6}\)\s+\w+\s+[0-9A-Fa-f]+#[0-9A-Fa-f]+$"
)

MINIMUM_MESSAGES_PER_DBC: int = 4
MINIMUM_CANDUMP_FRAMES: int = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_vss_paths(node: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Recursively extract VSS path → DBC signal name from a nested mapping.

    The vss_dbc.json tree has leaf nodes that carry a ``dbc2vss`` object
    containing the ``signal`` key.  Interior nodes carry a ``children`` dict.

    Args:
        node:   A dict representing one node of the VSS mapping tree.
        prefix: The dot-separated VSS path built up so far.

    Returns:
        Mapping of full VSS path strings to their DBC signal names.
    """
    result: dict[str, str] = {}
    if "dbc2vss" in node:
        result[prefix] = node["dbc2vss"]["signal"]
        return result
    for key, child in node.get("children", {}).items():
        child_prefix = f"{prefix}.{key}" if prefix else key
        result.update(extract_vss_paths(child, child_prefix))
    return result


def load_vss_mapping(profile_dir: Path) -> dict[str, str]:
    """Load and flatten the vss_dbc.json for *profile_dir*.

    Args:
        profile_dir: Directory that contains ``vss_dbc.json``.

    Returns:
        Flat dict of ``{vss_path: dbc_signal_name}``.
    """
    mapping_path = profile_dir / "vss_dbc.json"
    with mapping_path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)
    # The top-level object has metadata keys that start with "_".
    # The actual VSS tree root is the first non-metadata key (e.g. "Vehicle").
    tree_root = {k: v for k, v in raw.items() if not k.startswith("_")}
    paths: dict[str, str] = {}
    for root_key, root_node in tree_root.items():
        paths.update(extract_vss_paths(root_node, root_key))
    return paths


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hyundai_dir() -> Path:
    """Path to the Hyundai/Kia vehicle profile directory."""
    return DBC_ROOT / "hyundai_kia"


@pytest.fixture(scope="module")
def tesla_dir() -> Path:
    """Path to the Tesla Model 3 vehicle profile directory."""
    return DBC_ROOT / "tesla_model3"


@pytest.fixture(scope="module")
def hyundai_db(hyundai_dir: Path) -> cantools.database.Database:
    """Parsed cantools Database for hyundai_kia_generic.dbc."""
    return cantools.database.load_file(str(hyundai_dir / "hyundai_kia_generic.dbc"))


@pytest.fixture(scope="module")
def tesla_db(tesla_dir: Path) -> cantools.database.Database:
    """Parsed cantools Database for tesla_model3.dbc."""
    return cantools.database.load_file(str(tesla_dir / "tesla_model3.dbc"))


@pytest.fixture(scope="module")
def hyundai_mapping(hyundai_dir: Path) -> dict[str, str]:
    """Flat VSS-path → signal-name mapping for the Hyundai/Kia profile."""
    return load_vss_mapping(hyundai_dir)


@pytest.fixture(scope="module")
def tesla_mapping(tesla_dir: Path) -> dict[str, str]:
    """Flat VSS-path → signal-name mapping for the Tesla Model 3 profile."""
    return load_vss_mapping(tesla_dir)


# ---------------------------------------------------------------------------
# TestDBCFileParsing
# ---------------------------------------------------------------------------


class TestDBCFileParsing:
    """Verify DBC files are valid and contain the expected messages."""

    def test_hyundai_dbc_loads(self, hyundai_db: cantools.database.Database) -> None:
        """hyundai_kia_generic.dbc must load without errors."""
        assert hyundai_db is not None

    def test_tesla_dbc_loads(self, tesla_db: cantools.database.Database) -> None:
        """tesla_model3.dbc must load without errors."""
        assert tesla_db is not None

    def test_hyundai_has_minimum_messages(
        self, hyundai_db: cantools.database.Database
    ) -> None:
        """Hyundai DBC must define at least MINIMUM_MESSAGES_PER_DBC messages."""
        assert len(hyundai_db.messages) >= MINIMUM_MESSAGES_PER_DBC, (
            f"Expected >= {MINIMUM_MESSAGES_PER_DBC} messages, "
            f"got {len(hyundai_db.messages)}"
        )

    def test_tesla_has_minimum_messages(
        self, tesla_db: cantools.database.Database
    ) -> None:
        """Tesla DBC must define at least MINIMUM_MESSAGES_PER_DBC messages."""
        assert len(tesla_db.messages) >= MINIMUM_MESSAGES_PER_DBC, (
            f"Expected >= {MINIMUM_MESSAGES_PER_DBC} messages, "
            f"got {len(tesla_db.messages)}"
        )

    @pytest.mark.parametrize("profile", ["hyundai", "tesla"])
    def test_all_signals_have_units(
        self,
        profile: str,
        hyundai_db: cantools.database.Database,
        tesla_db: cantools.database.Database,
        hyundai_mapping: dict[str, str],
        tesla_mapping: dict[str, str],
    ) -> None:
        """VSS-mapped signals in both DBC files must declare a unit string.

        Signals that have no VSS path (e.g. ``DTCCount``, which is a
        dimensionless diagnostic counter explicitly excluded from the mapping)
        are skipped because they intentionally carry an empty unit field.
        """
        db = hyundai_db if profile == "hyundai" else tesla_db
        mapped_signals: set[str] = set(
            (hyundai_mapping if profile == "hyundai" else tesla_mapping).values()
        )
        missing_units: list[str] = []
        for msg in db.messages:
            for sig in msg.signals:
                if sig.name not in mapped_signals:
                    continue  # not a VSS-mapped signal — unit is optional
                if sig.unit is None or sig.unit.strip() == "":
                    missing_units.append(f"{msg.name}.{sig.name}")
        assert not missing_units, (
            f"VSS-mapped signals without units in {profile} DBC: {missing_units}"
        )

    @pytest.mark.parametrize("profile", ["hyundai", "tesla"])
    def test_signal_ranges_are_valid(
        self,
        profile: str,
        hyundai_db: cantools.database.Database,
        tesla_db: cantools.database.Database,
    ) -> None:
        """For every signal that declares a physical range, minimum < maximum."""
        db = hyundai_db if profile == "hyundai" else tesla_db
        invalid: list[str] = []
        for msg in db.messages:
            for sig in msg.signals:
                mn = sig.minimum
                mx = sig.maximum
                if mn is not None and mx is not None and mn >= mx:
                    invalid.append(
                        f"{msg.name}.{sig.name}: min={mn} >= max={mx}"
                    )
        assert not invalid, (
            f"Signals with invalid ranges in {profile} DBC: {invalid}"
        )


# ---------------------------------------------------------------------------
# TestVSSMapping
# ---------------------------------------------------------------------------


class TestVSSMapping:
    """Verify vss_dbc.json files map all required VSS paths."""

    def test_hyundai_mapping_valid_json(self, hyundai_dir: Path) -> None:
        """vss_dbc.json for Hyundai/Kia must be valid, non-empty JSON."""
        mapping_path = hyundai_dir / "vss_dbc.json"
        with mapping_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict) and data, (
            "Hyundai vss_dbc.json is empty or not a JSON object"
        )

    def test_tesla_mapping_valid_json(self, tesla_dir: Path) -> None:
        """vss_dbc.json for Tesla Model 3 must be valid, non-empty JSON."""
        mapping_path = tesla_dir / "vss_dbc.json"
        with mapping_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict) and data, (
            "Tesla vss_dbc.json is empty or not a JSON object"
        )

    def test_hyundai_covers_all_vss_paths(
        self, hyundai_mapping: dict[str, str]
    ) -> None:
        """Hyundai mapping must cover every path in EXPECTED_VSS_PATHS."""
        mapped = frozenset(hyundai_mapping.keys())
        missing = EXPECTED_VSS_PATHS - mapped
        assert not missing, (
            f"Hyundai vss_dbc.json is missing VSS paths: {sorted(missing)}"
        )

    def test_tesla_covers_all_vss_paths(self, tesla_mapping: dict[str, str]) -> None:
        """Tesla mapping must cover every path in EXPECTED_VSS_PATHS."""
        mapped = frozenset(tesla_mapping.keys())
        missing = EXPECTED_VSS_PATHS - mapped
        assert not missing, (
            f"Tesla vss_dbc.json is missing VSS paths: {sorted(missing)}"
        )

    def test_both_profiles_cover_same_paths(
        self,
        hyundai_mapping: dict[str, str],
        tesla_mapping: dict[str, str],
    ) -> None:
        """Both vehicle profiles must expose an identical set of VSS paths.

        This guarantees that swapping the DBC + mapping pair leaves the MCP
        tool surface unchanged — no server-side code changes required.
        """
        hyundai_paths = frozenset(hyundai_mapping.keys())
        tesla_paths = frozenset(tesla_mapping.keys())
        only_hyundai = hyundai_paths - tesla_paths
        only_tesla = tesla_paths - hyundai_paths
        assert not only_hyundai and not only_tesla, (
            f"Path coverage diverges between profiles.\n"
            f"  Only in Hyundai: {sorted(only_hyundai)}\n"
            f"  Only in Tesla:   {sorted(only_tesla)}"
        )


# ---------------------------------------------------------------------------
# TestMappingSignalConsistency
# ---------------------------------------------------------------------------


class TestMappingSignalConsistency:
    """Verify every signal name referenced in vss_dbc.json exists in the DBC."""

    def test_hyundai_signals_match(
        self,
        hyundai_mapping: dict[str, str],
        hyundai_db: cantools.database.Database,
    ) -> None:
        """Every signal name in hyundai vss_dbc.json must appear in the DBC."""
        dbc_signal_names: set[str] = {
            sig.name for msg in hyundai_db.messages for sig in msg.signals
        }
        unknown: list[str] = [
            f"{vss_path} -> '{dbc_sig}'"
            for vss_path, dbc_sig in hyundai_mapping.items()
            if dbc_sig not in dbc_signal_names
        ]
        assert not unknown, (
            f"Hyundai vss_dbc.json references signals not found in DBC: {unknown}"
        )

    def test_tesla_signals_match(
        self,
        tesla_mapping: dict[str, str],
        tesla_db: cantools.database.Database,
    ) -> None:
        """Every signal name in tesla vss_dbc.json must appear in the DBC."""
        dbc_signal_names: set[str] = {
            sig.name for msg in tesla_db.messages for sig in msg.signals
        }
        unknown: list[str] = [
            f"{vss_path} -> '{dbc_sig}'"
            for vss_path, dbc_sig in tesla_mapping.items()
            if dbc_sig not in dbc_signal_names
        ]
        assert not unknown, (
            f"Tesla vss_dbc.json references signals not found in DBC: {unknown}"
        )


# ---------------------------------------------------------------------------
# TestCandumpFiles
# ---------------------------------------------------------------------------


class TestCandumpFiles:
    """Verify candump log files exist and conform to the expected format."""

    def test_hyundai_candump_exists(self, hyundai_dir: Path) -> None:
        """candump.log must exist in the Hyundai/Kia profile directory."""
        assert (hyundai_dir / "candump.log").is_file(), (
            f"candump.log not found in {hyundai_dir}"
        )

    def test_tesla_candump_exists(self, tesla_dir: Path) -> None:
        """candump.log must exist in the Tesla Model 3 profile directory."""
        assert (tesla_dir / "candump.log").is_file(), (
            f"candump.log not found in {tesla_dir}"
        )

    @pytest.mark.parametrize("profile", ["hyundai", "tesla"])
    def test_candump_format(
        self,
        profile: str,
        hyundai_dir: Path,
        tesla_dir: Path,
    ) -> None:
        """Every non-blank line in candump.log must match the candump format.

        Expected format: ``(timestamp) interface CANID#HEXDATA``
        """
        log_path = (hyundai_dir if profile == "hyundai" else tesla_dir) / "candump.log"
        bad_lines: list[tuple[int, str]] = []
        with log_path.open(encoding="utf-8") as fh:
            for lineno, raw_line in enumerate(fh, start=1):
                line = raw_line.rstrip("\n")
                if not line:
                    continue
                if not CANDUMP_LINE_RE.match(line):
                    bad_lines.append((lineno, line))
        assert not bad_lines, (
            f"{profile} candump.log has {len(bad_lines)} malformed line(s). "
            f"First offender at line {bad_lines[0][0]}: {bad_lines[0][1]!r}"
        )

    @pytest.mark.parametrize("profile", ["hyundai", "tesla"])
    def test_candump_has_minimum_frames(
        self,
        profile: str,
        hyundai_dir: Path,
        tesla_dir: Path,
    ) -> None:
        """candump.log must contain at least MINIMUM_CANDUMP_FRAMES CAN frames."""
        log_path = (hyundai_dir if profile == "hyundai" else tesla_dir) / "candump.log"
        frame_count = sum(
            1
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        assert frame_count >= MINIMUM_CANDUMP_FRAMES, (
            f"{profile} candump.log has only {frame_count} frames "
            f"(minimum: {MINIMUM_CANDUMP_FRAMES})"
        )

    @pytest.mark.parametrize("profile", ["hyundai", "tesla"])
    def test_candump_can_ids_match_dbc(
        self,
        profile: str,
        hyundai_dir: Path,
        tesla_dir: Path,
        hyundai_db: cantools.database.Database,
        tesla_db: cantools.database.Database,
    ) -> None:
        """Every CAN frame ID in candump.log must correspond to a DBC message.

        Candump encodes IDs in hexadecimal; DBC stores them in decimal.
        The conversion ``int(hex_id, 16)`` produces the decimal frame ID
        used by cantools.
        """
        if profile == "hyundai":
            log_path = hyundai_dir / "candump.log"
            db = hyundai_db
        else:
            log_path = tesla_dir / "candump.log"
            db = tesla_db

        dbc_frame_ids: set[int] = {msg.frame_id for msg in db.messages}

        unknown_ids: set[int] = set()
        with log_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                # Field 3 is "CANID#HEXDATA"
                frame_id_hex = line.split()[2].split("#")[0]
                frame_id = int(frame_id_hex, 16)
                if frame_id not in dbc_frame_ids:
                    unknown_ids.add(frame_id)

        assert not unknown_ids, (
            f"{profile} candump.log contains CAN IDs not defined in the DBC: "
            f"{sorted(hex(i) for i in unknown_ids)}"
        )


# ---------------------------------------------------------------------------
# TestSignalRoundTrip
# ---------------------------------------------------------------------------


class TestSignalRoundTrip:
    """Verify DBC encode/decode round-trips for representative signal values."""

    def test_hyundai_encode_decode(
        self, hyundai_db: cantools.database.Database
    ) -> None:
        """Hyundai signals must survive an encode → decode round-trip within tolerance.

        Tests the two key messages that cover all 9 VSS paths:
        - EngineStatus  (EngineRPM, EngineCoolantTemp)
        - VehicleMotion (VehicleSpeed, TraveledDistance)
        - BatteryStatus (BatterySOC, BatteryVoltage, BatteryTemp)
        - HVACStatus    (SetTemp, AmbientTemp)
        """
        cases: list[tuple[str, dict[str, float], float]] = [
            (
                "EngineStatus",
                {"EngineRPM": 2500.0, "EngineCoolantTemp": 90.0},
                1.0,  # tolerance: 0.125 rpm/bit → < 1 rpm; 1 °C/bit → 0 °C
            ),
            (
                "VehicleMotion",
                {"VehicleSpeed": 80.0, "TraveledDistance": 12345.0},
                0.5,  # tolerance: 0.01 km/h/bit; 0.1 km/bit
            ),
            (
                "BatteryStatus",
                {"BatterySOC": 75.0, "BatteryVoltage": 380.0, "BatteryTemp": 30.0},
                1.0,
            ),
            (
                "HVACStatus",
                {"SetTemp": 22.0, "AmbientTemp": 24.0},
                0.5,
            ),
        ]

        for msg_name, signal_values, tolerance in cases:
            msg = hyundai_db.get_message_by_name(msg_name)
            encoded: bytes = msg.encode(signal_values)
            decoded: dict[str, Any] = msg.decode(encoded)
            for sig_name, expected in signal_values.items():
                actual = float(decoded[sig_name])
                assert abs(actual - expected) <= tolerance, (
                    f"Hyundai {msg_name}.{sig_name}: encoded {expected}, "
                    f"decoded {actual} (tolerance ±{tolerance})"
                )

    def test_tesla_encode_decode(self, tesla_db: cantools.database.Database) -> None:
        """Tesla signals must survive an encode → decode round-trip within tolerance.

        Tests the four messages that cover all 9 VSS paths:
        - DI_torque2     (DI_vehicleSpeed, DI_odometer)
        - DI_systemStatus (DI_motorRPM, DI_inverterTemp)
        - BMS_energyStatus (BMS_stateOfCharge, BMS_packVoltage, BMS_packTemp)
        - HVAC_status    (HVAC_cabinTemp, HVAC_setpointTemp)
        """
        cases: list[tuple[str, dict[str, float], float]] = [
            (
                "DI_torque2",
                {"DI_vehicleSpeed": 100.0, "DI_odometer": 50000.0},
                0.1,  # 0.1 km/h/bit; 0.001 km/bit
            ),
            (
                "DI_systemStatus",
                {"DI_motorRPM": 5000.0, "DI_inverterTemp": 65.0},
                1.0,  # 1 rpm/bit; 1 °C/bit
            ),
            (
                "BMS_energyStatus",
                {"BMS_stateOfCharge": 80.0, "BMS_packVoltage": 400.0, "BMS_packTemp": 35.0},
                0.5,
            ),
            (
                "HVAC_status",
                {"HVAC_cabinTemp": 22.0, "HVAC_setpointTemp": 20.0},
                0.5,
            ),
        ]

        for msg_name, signal_values, tolerance in cases:
            msg = tesla_db.get_message_by_name(msg_name)
            encoded: bytes = msg.encode(signal_values)
            decoded: dict[str, Any] = msg.decode(encoded)
            for sig_name, expected in signal_values.items():
                actual = float(decoded[sig_name])
                assert abs(actual - expected) <= tolerance, (
                    f"Tesla {msg_name}.{sig_name}: encoded {expected}, "
                    f"decoded {actual} (tolerance ±{tolerance})"
                )
