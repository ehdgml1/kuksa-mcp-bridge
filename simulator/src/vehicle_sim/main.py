"""Main entry point for the vehicle simulator.

Connects to Eclipse Kuksa Databroker via gRPC and publishes
simulated vehicle signals at a configurable interval. Supports
graceful shutdown and automatic reconnection with exponential
backoff.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Any

from kuksa_client.grpc import DataEntry, DataType, Datapoint, EntryUpdate, Field
from kuksa_client.grpc.aio import VSSClient

from vehicle_sim.hvac import VSS_HVAC_DRIVER_TEMP
from vehicle_sim.scenarios import ScenarioManager, ScenarioMode

logger = logging.getLogger(__name__)

# --- Configuration Defaults ---
DEFAULT_KUKSA_HOST = "localhost"
DEFAULT_KUKSA_PORT = 55555
DEFAULT_SIM_MODE = "normal_driving"
DEFAULT_UPDATE_INTERVAL_MS = 500
DEFAULT_LOG_LEVEL = "INFO"

# --- Retry Constants ---
MAX_CONNECT_RETRIES = 10
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2.0


def _load_config() -> dict[str, Any]:
    """Load configuration from environment variables.

    Returns:
        Dictionary with keys: host, port, sim_mode,
        update_interval_ms, log_level.
    """
    return {
        "host": os.getenv("KUKSA_DATABROKER_HOST", DEFAULT_KUKSA_HOST),
        "port": int(os.getenv("KUKSA_DATABROKER_PORT", str(DEFAULT_KUKSA_PORT))),
        "sim_mode": os.getenv("SIM_MODE", DEFAULT_SIM_MODE),
        "update_interval_ms": int(
            os.getenv("SIM_UPDATE_INTERVAL_MS", str(DEFAULT_UPDATE_INTERVAL_MS))
        ),
        "log_level": os.getenv("SIM_LOG_LEVEL", DEFAULT_LOG_LEVEL),
    }


def _setup_logging(level_name: str) -> None:
    """Configure root logger with structured format.

    Args:
        level_name: Logging level string (e.g., ``"INFO"``, ``"DEBUG"``).
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def _resolve_scenario_mode(mode_str: str) -> ScenarioMode:
    """Convert a string to a ScenarioMode enum value.

    Args:
        mode_str: Scenario mode as string (e.g., ``"normal_driving"``).

    Returns:
        Corresponding ScenarioMode enum member.

    Raises:
        ValueError: If the mode string is not a valid scenario.
    """
    try:
        return ScenarioMode(mode_str)
    except ValueError:
        valid = [m.value for m in ScenarioMode]
        raise ValueError(
            "Invalid SIM_MODE '%s'. Valid modes: %s" % (mode_str, valid)
        ) from None


async def connect_with_retry(
    host: str,
    port: int,
    max_retries: int = MAX_CONNECT_RETRIES,
) -> VSSClient:
    """Connect to Kuksa Databroker with exponential backoff retry.

    Args:
        host: Databroker hostname or IP address.
        port: Databroker gRPC port number.
        max_retries: Maximum number of connection attempts.

    Returns:
        Connected VSSClient instance.

    Raises:
        ConnectionError: If all retry attempts are exhausted.
    """
    backoff = INITIAL_BACKOFF_SECONDS

    for attempt in range(1, max_retries + 1):
        try:
            client = VSSClient(host=host, port=port)
            await client.connect()
            logger.info(
                "Connected to Kuksa Databroker at %s:%d (attempt %d/%d)",
                host, port, attempt, max_retries,
            )
            return client
        except Exception as exc:
            logger.warning(
                "Connection attempt %d/%d failed: %s",
                attempt, max_retries, exc,
            )
            if attempt == max_retries:
                raise ConnectionError(
                    "Failed to connect to Kuksa Databroker at %s:%d "
                    "after %d attempts" % (host, port, max_retries)
                ) from exc
            logger.info("Retrying in %.1f seconds...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

    # Unreachable, but satisfies type checker
    raise ConnectionError("Exhausted retries connecting to %s:%d" % (host, port))


def _build_updates(signals: dict[str, Any]) -> list[EntryUpdate]:
    """Convert signal values to Kuksa EntryUpdate objects with explicit DataType.

    kuksa-client 0.5.1+ requires an explicit ``value_type`` on ``DataEntry``
    so the gRPC layer knows which protobuf oneof field to populate.  Inferring
    the type from the Python value is safe for the signal types this simulator
    produces (bool, int, float, str, list[str]).

    Args:
        signals: Dictionary mapping VSS paths to signal values.

    Returns:
        List of EntryUpdate instances ready for ``VSSClient.set``.
    """
    updates: list[EntryUpdate] = []
    for path, value in signals.items():
        if isinstance(value, bool):
            vtype = DataType.BOOLEAN
        elif isinstance(value, int):
            vtype = DataType.INT32
        elif isinstance(value, float):
            vtype = DataType.FLOAT
        elif isinstance(value, list):
            vtype = DataType.STRING_ARRAY
            # kuksa-client expects STRING_ARRAY values as a bracketed
            # string (e.g. "[P0301, P0420]"), not a native Python list.
            value = "[" + ", ".join(str(v) for v in value) + "]"
        else:
            vtype = DataType.STRING
            value = str(value)

        entry = DataEntry(path, value=Datapoint(value), value_type=vtype)
        updates.append(EntryUpdate(entry, (Field.VALUE,)))
    return updates


async def _sync_hvac_from_databroker(
    client: VSSClient,
    scenario_manager: ScenarioManager,
) -> None:
    """Read the HVAC target temperature from the databroker and sync to the simulator.

    If an external agent has changed the value via ``set_actuator`` since the
    last publish cycle, the simulator's internal target will be updated so the
    next cycle publishes the externally-commanded value instead of the default.

    Args:
        client: Connected VSSClient used to read the current signal value.
        scenario_manager: ScenarioManager whose ``hvac_target_temp`` will be
            updated when a difference is detected.
    """
    try:
        result = await client.get_current_values([VSS_HVAC_DRIVER_TEMP])
        dp = result.get(VSS_HVAC_DRIVER_TEMP)
        if dp is not None and dp.value is not None:
            db_value = float(dp.value)
            if abs(db_value - scenario_manager.hvac_target_temp) > 0.1:
                scenario_manager.hvac_target_temp = db_value
                logger.info(
                    "HVAC target synced from databroker: %.1f°C", db_value
                )
    except Exception as exc:
        logger.debug("HVAC sync skipped: %s", exc)


async def _publish_one_cycle(
    client: VSSClient,
    scenario_manager: ScenarioManager,
    interval_seconds: float,
    cycle_count: int,
) -> None:
    """Generate and publish one cycle of vehicle signals.

    Args:
        client: Connected VSSClient for publishing values.
        scenario_manager: Configured ScenarioManager instance.
        interval_seconds: Elapsed time in seconds for distance integration.
        cycle_count: Current cycle number for periodic logging.
    """
    await _sync_hvac_from_databroker(client, scenario_manager)
    signals = scenario_manager.generate_all(elapsed_seconds=interval_seconds)
    updates = _build_updates(signals)
    await client.set(updates=updates)

    if cycle_count % 10 == 0:
        logger.info("Published %d cycles | signals: %s", cycle_count, signals)


async def publish_loop(
    client: VSSClient,
    scenario_manager: ScenarioManager,
    interval_ms: int,
) -> None:
    """Continuously generate and publish vehicle signals.

    Runs until cancelled, delegating each cycle to
    ``_publish_one_cycle``.

    Args:
        client: Connected VSSClient for publishing values.
        scenario_manager: Configured ScenarioManager instance.
        interval_ms: Publish interval in milliseconds.
    """
    interval_seconds = interval_ms / 1000.0
    cycle_count = 0

    logger.info(
        "Starting publish loop: interval=%dms, scenario=%s",
        interval_ms, scenario_manager.mode.value,
    )

    while True:
        try:
            cycle_count += 1
            await _publish_one_cycle(
                client, scenario_manager, interval_seconds, cycle_count,
            )
        except asyncio.CancelledError:
            logger.info("Publish loop cancelled after %d cycles", cycle_count)
            raise
        except Exception as exc:
            logger.error("Error publishing signals (cycle %d): %s", cycle_count, exc)
            raise

        await asyncio.sleep(interval_seconds)


def _log_startup_banner(config: dict[str, Any]) -> None:
    """Log startup configuration banner.

    Args:
        config: Configuration dictionary with host, port, sim_mode, interval.
    """
    logger.info("=" * 60)
    logger.info("Vehicle Simulator starting")
    logger.info("  Databroker: %s:%d", config["host"], config["port"])
    logger.info("  Scenario:   %s", config["sim_mode"])
    logger.info("  Interval:   %dms", config["update_interval_ms"])
    logger.info("=" * 60)


def _register_shutdown_handler(shutdown_event: asyncio.Event) -> None:
    """Register OS signal handlers for graceful shutdown.

    Args:
        shutdown_event: Event to set when shutdown signal is received.
    """
    def _on_signal(sig: signal.Signals) -> None:
        """Handle OS shutdown signal.

        Args:
            sig: The received signal.
        """
        logger.info("Received signal %s, initiating shutdown...", sig.name)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal, sig)


async def _run_until_shutdown(
    client: VSSClient,
    scenario_manager: ScenarioManager,
    interval_ms: int,
    shutdown_event: asyncio.Event,
) -> None:
    """Run publish loop until shutdown event fires.

    Args:
        client: Connected VSSClient instance.
        scenario_manager: Configured ScenarioManager.
        interval_ms: Publish interval in milliseconds.
        shutdown_event: Event that signals shutdown.
    """
    publish_task = asyncio.create_task(
        publish_loop(client, scenario_manager, interval_ms)
    )
    shutdown_wait = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        {publish_task, shutdown_wait},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    for task in done:
        if task is not shutdown_wait and task.exception():
            raise task.exception()  # type: ignore[misc]


async def _disconnect_safely(client: VSSClient | None) -> None:
    """Disconnect from Kuksa Databroker, suppressing errors.

    Args:
        client: VSSClient to disconnect, or None if not connected.
    """
    if client is None:
        return
    try:
        await client.disconnect()
        logger.info("Disconnected from Kuksa Databroker")
    except Exception as exc:
        logger.warning("Error during disconnect: %s", exc)


async def main() -> None:
    """Main async entry point for the vehicle simulator.

    Loads configuration, connects to Kuksa Databroker,
    and runs the publish loop with graceful shutdown handling.
    """
    config = _load_config()
    _setup_logging(config["log_level"])
    _log_startup_banner(config)

    scenario_mode = _resolve_scenario_mode(config["sim_mode"])
    scenario_manager = ScenarioManager()
    scenario_manager.set_scenario(scenario_mode)

    shutdown_event = asyncio.Event()
    _register_shutdown_handler(shutdown_event)

    client: VSSClient | None = None
    try:
        client = await connect_with_retry(config["host"], config["port"])
        await _run_until_shutdown(
            client, scenario_manager, config["update_interval_ms"], shutdown_event,
        )
    except ConnectionError as exc:
        logger.error("Fatal connection error: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await _disconnect_safely(client)

    logger.info("Vehicle Simulator stopped")


if __name__ == "__main__":
    asyncio.run(main())
