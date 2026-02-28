"""CAN dump file generator for DBC-based vehicle profiles.

Generates candump-format replay files by encoding realistic vehicle signal
values into CAN frames using DBC definitions.  The output can be fed directly
to ``kuksa-can-provider`` (replay mode) so that the full DBC → Kuksa Databroker
pipeline works on macOS / environments without a vcan0 kernel module.

Typical usage::

    python generate_candump.py \\
        --dbc ../hyundai_kia/hyundai_kia_generic.dbc \\
        --output /tmp/hyundai_replay.log \\
        --duration 60 \\
        --seed 42
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cantools
import cantools.database

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default CAN interface name written into each candump line.
DEFAULT_INTERFACE: str = "vcan0"

# Base generation rate when no message-specific cycle time is found (Hz).
DEFAULT_RATE_HZ: float = 20.0

# Minimum and maximum physical-value generation rates (Hz).
MIN_RATE_HZ: float = 1.0
MAX_RATE_HZ: float = 100.0

# Simulation start timestamp (Unix epoch).  Using a fixed recent value keeps
# replay files deterministic when --seed is supplied.
BASE_TIMESTAMP: float = 1_706_000_000.0

# Pattern-matching keywords used to auto-detect signal roles.
_RPM_KEYWORDS: frozenset[str] = frozenset({"rpm", "enginespeed", "enginerpm"})
_SPEED_KEYWORDS: frozenset[str] = frozenset({"speed", "velocity", "vspd"})
_TEMP_KEYWORDS: frozenset[str] = frozenset({"temp", "temperature", "ect", "coolant"})
_SOC_KEYWORDS: frozenset[str] = frozenset({"soc", "stateofcharge", "batterysoc"})
_VOLTAGE_KEYWORDS: frozenset[str] = frozenset({"voltage", "volt", "batteryvoltage"})
_DISTANCE_KEYWORDS: frozenset[str] = frozenset({"distance", "odometer", "traveled"})
_DTC_KEYWORDS: frozenset[str] = frozenset({"dtc", "dtccount", "fault", "code"})

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal value generators
# ---------------------------------------------------------------------------


@dataclass
class SignalGenerator:
    """Stateful generator that produces a physical value for a single signal.

    The generator is called once per time step and returns a value that stays
    within the signal's physical min/max bounds.
    """

    name: str
    min_val: float
    max_val: float
    _fn: Callable[[float], float] = field(repr=False, default=lambda t: 0.0)

    def value_at(self, t: float) -> float:
        """Return the physical value for elapsed time *t* (seconds).

        The result is clamped to [min_val, max_val].

        Args:
            t: Elapsed simulation time in seconds.

        Returns:
            Clamped physical value.
        """
        raw = self._fn(t)
        return max(self.min_val, min(self.max_val, raw))


def _sine_generator(
    name: str,
    min_val: float,
    max_val: float,
    freq: float,
    noise_scale: float = 0.0,
    rng: random.Random | None = None,
) -> SignalGenerator:
    """Build a sine-wave SignalGenerator with optional white noise.

    Args:
        name: Signal name (for logging only).
        min_val: Physical lower bound.
        max_val: Physical upper bound.
        freq: Oscillation frequency in Hz.
        noise_scale: Peak-to-peak noise amplitude as fraction of range.
        rng: Optional seeded Random for reproducibility.

    Returns:
        Configured SignalGenerator.
    """
    mid = (min_val + max_val) / 2.0
    amp = (max_val - min_val) / 2.0
    noise_amp = noise_scale * (max_val - min_val)
    _rng = rng or random.Random()

    def fn(t: float) -> float:
        return mid + amp * math.sin(2.0 * math.pi * freq * t) + _rng.uniform(-noise_amp, noise_amp)

    return SignalGenerator(name=name, min_val=min_val, max_val=max_val, _fn=fn)


def _ramp_generator(
    name: str,
    min_val: float,
    max_val: float,
    duration: float,
    noise_scale: float = 0.02,
    rng: random.Random | None = None,
) -> SignalGenerator:
    """Build a linear-ramp SignalGenerator that spans [min_val, max_val] over *duration* seconds.

    After *duration* the value holds at max_val (clamp applies).

    Args:
        name: Signal name.
        min_val: Starting physical value.
        max_val: Ending physical value.
        duration: Seconds until max_val is reached.
        noise_scale: Noise amplitude as fraction of total range.
        rng: Optional seeded Random.

    Returns:
        Configured SignalGenerator.
    """
    noise_amp = noise_scale * (max_val - min_val)
    _rng = rng or random.Random()

    def fn(t: float) -> float:
        progress = min(1.0, t / max(duration, 1e-9))
        return min_val + progress * (max_val - min_val) + _rng.uniform(-noise_amp, noise_amp)

    return SignalGenerator(name=name, min_val=min_val, max_val=max_val, _fn=fn)


def _constant_generator(name: str, value: float) -> SignalGenerator:
    """Build a constant-value SignalGenerator (e.g., for set-temperature).

    Args:
        name: Signal name.
        value: Fixed physical value.

    Returns:
        Configured SignalGenerator.
    """
    return SignalGenerator(name=name, min_val=value, max_val=value, _fn=lambda _t: value)


# ---------------------------------------------------------------------------
# Auto-detection of signal role → generator factory
# ---------------------------------------------------------------------------


def _normalise_name(raw: str) -> str:
    """Return lower-cased signal name with underscores and spaces removed."""
    return raw.lower().replace("_", "").replace(" ", "")


def _clamp_range(
    lo: float, hi: float, desired_lo: float, desired_hi: float
) -> tuple[float, float]:
    """Return a (lo, hi) range that fits within the signal's physical bounds.

    If the desired range falls entirely outside the signal bounds the signal
    bounds are returned unchanged.

    Args:
        lo: Signal physical minimum.
        hi: Signal physical maximum.
        desired_lo: Desired lower bound of generation range.
        desired_hi: Desired upper bound of generation range.

    Returns:
        Tuple of (clamped_lo, clamped_hi).
    """
    clo = max(lo, desired_lo)
    chi = min(hi, desired_hi)
    if clo >= chi:
        return lo, hi
    return clo, chi


def build_signal_generator(
    signal: cantools.database.Signal,
    duration: float,
    rng: random.Random,
) -> SignalGenerator:
    """Create an appropriate SignalGenerator for *signal* by inspecting its name and unit.

    Pattern priority (first match wins):
    1. RPM-like  → sine 800–3000 rpm, freq 0.05 Hz
    2. Speed-like → sine 40–80 km/h, freq 0.03 Hz
    3. Temperature-like → ramp with noise (lower bound → lower+7 degC)
    4. SOC       → slow linear decrease (75 % → 70 %)
    5. Voltage   → correlated ramp (380 V range)
    6. Distance  → monotonic increase
    7. DTC count → constant 0 (no faults default)
    8. Fallback  → sine over full physical range

    Args:
        signal: cantools Signal object.
        duration: Total simulation duration in seconds.
        rng: Seeded Random instance.

    Returns:
        SignalGenerator appropriate for the signal.
    """
    name_key = _normalise_name(signal.name)
    unit_key = (signal.unit or "").lower().strip()
    lo = float(signal.minimum) if signal.minimum is not None else 0.0
    hi = float(signal.maximum) if signal.maximum is not None else 1.0

    logger.debug("Building generator for signal '%s' (unit=%r, lo=%s, hi=%s)", signal.name, signal.unit, lo, hi)

    if name_key in _RPM_KEYWORDS or unit_key == "rpm":
        clo, chi = _clamp_range(lo, hi, 800.0, 3000.0)
        return _sine_generator(signal.name, clo, chi, freq=0.05, noise_scale=0.01, rng=rng)

    if name_key in _SPEED_KEYWORDS or unit_key == "km/h":
        clo, chi = _clamp_range(lo, hi, 40.0, 80.0)
        return _sine_generator(signal.name, clo, chi, freq=0.03, noise_scale=0.005, rng=rng)

    if name_key in _TEMP_KEYWORDS or unit_key in ("degc", "°c"):
        clo, chi = _clamp_range(lo, hi, 88.0, 95.0)
        return _ramp_generator(signal.name, clo, chi, duration=duration * 0.6, noise_scale=0.02, rng=rng)

    if name_key in _SOC_KEYWORDS or (unit_key == "%" and "soc" in name_key):
        clo, chi = _clamp_range(lo, hi, 70.0, 75.0)
        return _ramp_generator(signal.name, chi, clo, duration=duration, noise_scale=0.005, rng=rng)

    if name_key in _VOLTAGE_KEYWORDS or unit_key in ("v", "volt"):
        clo, chi = _clamp_range(lo, hi, 375.0, 385.0)
        return _ramp_generator(signal.name, chi, clo, duration=duration, noise_scale=0.003, rng=rng)

    if name_key in _DISTANCE_KEYWORDS or unit_key == "km":
        # Start at an arbitrary odometer value, increase at ~50 km/h pace.
        start = max(lo, 12_345.0)
        end = min(hi, start + 50.0 * (duration / 3600.0))
        return _ramp_generator(signal.name, start, end, duration=duration, noise_scale=0.0, rng=rng)

    if name_key in _DTC_KEYWORDS:
        return _constant_generator(signal.name, max(lo, 0.0))

    # Generic fallback: sine over middle third of physical range.
    mid = (lo + hi) / 2.0
    spread = (hi - lo) / 6.0
    return _sine_generator(signal.name, mid - spread, mid + spread, freq=0.02, noise_scale=0.01, rng=rng)


# ---------------------------------------------------------------------------
# candump file writer
# ---------------------------------------------------------------------------


class CandumpWriter:
    """Writes CAN frames in candump log format.

    Each line has the form::

        (<timestamp>) <interface> <CAN_ID_HEX>#<DATA_HEX>

    Example::

        (1706000000.123456) vcan0 100#9817FF8B00000000
    """

    def __init__(self, path: Path, interface: str = DEFAULT_INTERFACE) -> None:
        """Open *path* for writing.

        Args:
            path: Destination file path.  Parent directories must exist.
            interface: CAN interface name embedded in every log line.

        Raises:
            OSError: If the file cannot be opened for writing.
        """
        self._interface = interface
        self._file = path.open("w", encoding="ascii")
        logger.info("Opened candump output file: %s", path)

    def write_frame(self, timestamp: float, can_id: int, data: bytes) -> None:
        """Append a single CAN frame line to the output file.

        Args:
            timestamp: Unix epoch timestamp (fractional seconds).
            can_id: 11-bit or 29-bit CAN message identifier.
            data: Up to 8 bytes of CAN payload.
        """
        hex_id = f"{can_id:X}"
        hex_data = data.hex().upper()
        self._file.write(f"({timestamp:.6f}) {self._interface} {hex_id}#{hex_data}\n")

    def close(self) -> None:
        """Flush and close the output file."""
        self._file.flush()
        self._file.close()
        logger.info("Closed candump output file.")

    def __enter__(self) -> "CandumpWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Message schedule — per-message generation rate
# ---------------------------------------------------------------------------


def _message_rate_hz(msg: cantools.database.Message) -> float:
    """Return the generation rate in Hz for *msg*.

    Uses the message's ``cycle_time`` attribute (milliseconds) when available;
    otherwise falls back to DEFAULT_RATE_HZ.

    Args:
        msg: cantools Message object.

    Returns:
        Generation rate in Hz, clamped to [MIN_RATE_HZ, MAX_RATE_HZ].
    """
    cycle_ms: int | None = getattr(msg, "cycle_time", None)
    if cycle_ms and cycle_ms > 0:
        rate = 1000.0 / cycle_ms
    else:
        rate = DEFAULT_RATE_HZ
    return max(MIN_RATE_HZ, min(MAX_RATE_HZ, rate))


# ---------------------------------------------------------------------------
# Core generation logic
# ---------------------------------------------------------------------------


def generate_candump(
    db: cantools.database.Database,
    writer: CandumpWriter,
    duration: float,
    rng: random.Random,
) -> int:
    """Generate candump frames for all messages in *db* and write to *writer*.

    For each message the function creates one SignalGenerator per signal, then
    advances time in steps of ``1 / rate_hz`` and writes an encoded CAN frame
    at every step.

    Args:
        db: Parsed cantools database.
        writer: Open CandumpWriter to receive frames.
        duration: Simulation duration in seconds (must be > 0).
        rng: Seeded Random instance for reproducible noise.

    Returns:
        Total number of CAN frames written.

    Raises:
        ValueError: If *duration* is not positive.
    """
    if duration <= 0:
        raise ValueError(f"duration must be positive, got {duration}")

    total_frames = 0

    for msg in db.messages:
        logger.debug("Scheduling message 0x%X (%s), %d signal(s)", msg.frame_id, msg.name, len(msg.signals))

        rate_hz = _message_rate_hz(msg)
        step_s = 1.0 / rate_hz

        generators: dict[str, SignalGenerator] = {
            sig.name: build_signal_generator(sig, duration, rng)
            for sig in msg.signals
        }

        t = 0.0
        while t <= duration:
            signal_values = {name: gen.value_at(t) for name, gen in generators.items()}

            try:
                encoded: bytes = msg.encode(signal_values)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Encoding failed for message '%s' at t=%.3f: %s", msg.name, t, exc)
                t += step_s
                continue

            timestamp = BASE_TIMESTAMP + t
            writer.write_frame(timestamp, msg.frame_id, encoded)
            total_frames += 1
            t += step_s

    logger.info("Generated %d CAN frames across %d message(s).", total_frames, len(db.messages))
    return total_frames


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="generate_candump",
        description=(
            "Generate a candump-format CAN replay file from a DBC database. "
            "The output can be used with kuksa-can-provider in replay mode."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dbc",
        required=True,
        metavar="PATH",
        help="Path to the DBC file to load.",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Destination path for the generated candump log file.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Total simulation duration in seconds.",
    )
    parser.add_argument(
        "--interface",
        default=DEFAULT_INTERFACE,
        metavar="IFACE",
        help="CAN interface name written into each log line (e.g. vcan0).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="Random seed for reproducible output.  Omit for non-deterministic generation.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser


def _configure_logging(level: str) -> None:
    """Configure root logger to *level* with a human-readable format.

    Args:
        level: One of 'DEBUG', 'INFO', 'WARNING', 'ERROR'.
    """
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """Entry point: parse CLI arguments, load DBC, and generate candump log.

    Exits with code 1 on any fatal error (missing file, invalid DBC, etc.).
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    _configure_logging(args.log_level)

    dbc_path = Path(args.dbc)
    if not dbc_path.is_file():
        logger.error("DBC file not found: %s", dbc_path)
        raise SystemExit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading DBC: %s", dbc_path)
    try:
        db: cantools.database.Database = cantools.database.load_file(str(dbc_path))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse DBC file '%s': %s", dbc_path, exc)
        raise SystemExit(1) from exc

    logger.info(
        "Loaded %d message(s) from '%s'.",
        len(db.messages),
        dbc_path.name,
    )

    seed = args.seed
    if seed is not None:
        logger.info("Using random seed: %d", seed)
    rng = random.Random(seed)

    start_wall = time.monotonic()
    with CandumpWriter(output_path, interface=args.interface) as writer:
        frame_count = generate_candump(
            db=db,
            writer=writer,
            duration=args.duration,
            rng=rng,
        )
    elapsed = time.monotonic() - start_wall

    logger.info(
        "Done. Wrote %d frames to '%s' in %.2f s (simulated %.0f s of CAN traffic).",
        frame_count,
        output_path,
        elapsed,
        args.duration,
    )


if __name__ == "__main__":
    main()
