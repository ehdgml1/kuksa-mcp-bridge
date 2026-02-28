"""Kuksa Databroker gRPC client wrapper.

Provides an async wrapper around the kuksa-client VSSClient with
automatic reconnection, structured error handling, and Pydantic
response models for type-safe signal access.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import grpc
from kuksa_client.grpc import (
    DataEntry,
    DataType,
    Datapoint,
    EntryUpdate,
    Field,
    Metadata,
    VSSClientError,
)
from kuksa_client.grpc.aio import VSSClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SECONDS = 1.0
DEFAULT_SUBSCRIBE_DURATION_SECONDS = 10
SUBSCRIBE_POLL_INTERVAL_SECONDS = 0.1


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class SignalNotFoundError(Exception):
    """Raised when a requested VSS signal path does not exist."""

    def __init__(self, path: str) -> None:
        """Initialise with the VSS path that was not found.

        Args:
            path: The VSS signal path that could not be resolved.
        """
        self.path = path
        super().__init__(f"VSS signal not found: {path}")


class DatabrokerConnectionError(Exception):
    """Raised when the Kuksa Databroker is unreachable."""

    def __init__(self, detail: str = "Databroker unreachable") -> None:
        """Initialise with a human-readable error detail.

        Args:
            detail: Description of the connection failure.
        """
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------
class SignalValue(BaseModel):
    """Represents a current value reading for a VSS signal.

    Attributes:
        path: Fully qualified VSS path (e.g. ``Vehicle.Speed``).
        value: Current value; may be ``None`` if not yet set.
            Accepts ``list[str]`` for VSS ``STRING_ARRAY`` signals
            such as ``Vehicle.OBD.DTCList``.
        timestamp: ISO-8601 timestamp of the reading.
        unit: Engineering unit string (e.g. ``km/h``).
    """

    path: str
    value: float | str | bool | list[str] | None = None
    timestamp: str = ""
    unit: str = ""


class SignalMetadata(BaseModel):
    """Metadata describing a single VSS signal.

    Attributes:
        path: Fully qualified VSS path.
        data_type: VSS data type name (e.g. ``FLOAT``, ``BOOLEAN``).
        description: Human-readable description.
        unit: Engineering unit string.
        entry_type: Entry type name (e.g. ``SENSOR``, ``ACTUATOR``).
    """

    path: str
    data_type: str = "UNSPECIFIED"
    description: str = ""
    unit: str = ""
    entry_type: str = "UNSPECIFIED"


class SignalInfo(BaseModel):
    """Lightweight signal information returned by tree search.

    Attributes:
        path: Fully qualified VSS path.
        data_type: VSS data type name.
        description: Human-readable description.
    """

    path: str
    data_type: str = "UNSPECIFIED"
    description: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_value(
    datapoint: Datapoint | None,
) -> float | str | bool | list[str] | None:
    """Safely extract the Python value from a Kuksa Datapoint.

    Handles protobuf array wrapper types (e.g. ``StringArray``)
    returned by the Databroker for VSS ``STRING_ARRAY`` signals.

    Args:
        datapoint: A Kuksa ``Datapoint`` instance or ``None``.

    Returns:
        The unwrapped Python value, or ``None`` when unavailable.
    """
    if datapoint is None:
        return None
    val = datapoint.value
    # Protobuf repeated-value wrappers (StringArray, etc.) expose a
    # ``.values`` attribute containing the repeated field elements.
    if hasattr(val, "values") and not isinstance(val, (str, bytes)):
        return list(val.values)
    return val


def _format_timestamp(datapoint: Datapoint | None) -> str:
    """Format a Kuksa Datapoint timestamp as ISO-8601 string.

    Args:
        datapoint: A Kuksa ``Datapoint`` instance or ``None``.

    Returns:
        ISO-8601 timestamp string, or current UTC time if unavailable.
    """
    if datapoint is not None and datapoint.timestamp is not None:
        return datapoint.timestamp.isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _infer_data_type(value: float | str | bool) -> DataType:
    """Infer the appropriate VSS DataType from a Python value.

    Used when writing a signal value so the gRPC layer knows which
    protobuf oneof field to populate.

    Args:
        value: The Python value whose type is to be mapped.

    Returns:
        A ``DataType`` enum member matching the Python type.
    """
    if isinstance(value, bool):
        return DataType.BOOLEAN
    if isinstance(value, int):
        return DataType.INT32
    if isinstance(value, float):
        return DataType.FLOAT
    return DataType.STRING


def _classify_vss_error(exc: VSSClientError, path: str = "") -> None:
    """Translate a ``VSSClientError`` into a domain-specific exception.

    Args:
        exc: The original VSSClientError.
        path: Optional VSS path for context in error messages.

    Raises:
        SignalNotFoundError: When the gRPC status is NOT_FOUND.
        DatabrokerConnectionError: For all other gRPC failures.
    """
    error_code = exc.error.get("code", -1)
    not_found_code = grpc.StatusCode.NOT_FOUND.value[0]
    if error_code == not_found_code:
        raise SignalNotFoundError(path) from exc
    message = exc.error.get("message", str(exc))
    raise DatabrokerConnectionError(
        f"Databroker error for '{path}': {message}"
    ) from exc


# ---------------------------------------------------------------------------
# Client wrapper
# ---------------------------------------------------------------------------
class KuksaClientWrapper:
    """High-level async wrapper around Kuksa VSSClient.

    Provides connection management with lazy reconnection,
    structured responses via Pydantic models, and domain-specific
    exception translation.

    Args:
        host: Kuksa Databroker hostname.
        port: Kuksa Databroker gRPC port.
    """

    def __init__(self, host: str, port: int) -> None:
        """Initialise the wrapper with Databroker connection parameters.

        Args:
            host: Kuksa Databroker hostname or IP address.
            port: Kuksa Databroker gRPC port number.
        """
        self._host = host
        self._port = port
        self._client: VSSClient | None = None
        self._metadata_cache: dict[str, Metadata] = {}

    # -- Connection lifecycle -----------------------------------------------

    async def connect(self) -> None:
        """Establish a gRPC connection to the Kuksa Databroker.

        Raises:
            DatabrokerConnectionError: If the connection cannot be made.
        """
        target = f"{self._host}:{self._port}"
        logger.info("Connecting to Kuksa Databroker at %s", target)
        try:
            self._client = VSSClient(
                host=self._host,
                port=self._port,
                ensure_startup_connection=False,
            )
            await self._client.connect()
            logger.info("Successfully connected to Kuksa Databroker")
        except Exception as exc:
            self._client = None
            raise DatabrokerConnectionError(
                f"Failed to connect to Databroker at {target}: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """Gracefully close the Databroker connection."""
        if self._client is not None:
            try:
                await self._client.disconnect()
                logger.info("Disconnected from Kuksa Databroker")
            except Exception:
                logger.warning("Error during disconnect, ignoring", exc_info=True)
            finally:
                self._client = None

    async def _ensure_connected(self) -> VSSClient:
        """Return a live VSSClient, reconnecting if necessary.

        Implements lazy connection with retry logic so that tools
        can be registered at import time before the broker is up.

        Returns:
            A connected ``VSSClient`` instance.

        Raises:
            DatabrokerConnectionError: After exhausting reconnect attempts.
        """
        if self._client is not None and self._client.connected:
            return self._client

        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            logger.info(
                "Reconnect attempt %s/%s to Databroker",
                attempt,
                MAX_RECONNECT_ATTEMPTS,
            )
            try:
                await self.connect()
                if self._client is not None:
                    return self._client
            except DatabrokerConnectionError:
                if attempt < MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(RECONNECT_DELAY_SECONDS * attempt)

        raise DatabrokerConnectionError(
            f"Failed to connect after {MAX_RECONNECT_ATTEMPTS} attempts"
        )

    # -- Signal reads -------------------------------------------------------

    async def get_signal(self, path: str) -> SignalValue:
        """Query a single VSS signal's current value.

        Args:
            path: Fully qualified VSS path (e.g. ``Vehicle.Speed``).

        Returns:
            A ``SignalValue`` with the current reading.

        Raises:
            SignalNotFoundError: If the path does not exist.
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        try:
            result = await client.get_current_values([path])
        except VSSClientError as exc:
            _classify_vss_error(exc, path)

        datapoint = result.get(path)
        unit = await self._get_unit_cached(path)

        return SignalValue(
            path=path,
            value=_extract_value(datapoint),
            timestamp=_format_timestamp(datapoint),
            unit=unit,
        )

    async def get_signals(self, paths: list[str]) -> dict[str, SignalValue]:
        """Query multiple VSS signals at once.

        Args:
            paths: List of VSS paths to query.

        Returns:
            Mapping of path to ``SignalValue`` for each requested signal.

        Raises:
            SignalNotFoundError: If any path does not exist.
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        try:
            result = await client.get_current_values(paths)
        except VSSClientError as exc:
            _classify_vss_error(exc, ", ".join(paths))

        signals: dict[str, SignalValue] = {}
        for path in paths:
            datapoint = result.get(path)
            unit = await self._get_unit_cached(path)
            signals[path] = SignalValue(
                path=path,
                value=_extract_value(datapoint),
                timestamp=_format_timestamp(datapoint),
                unit=unit,
            )
        return signals

    # -- Actuator control ---------------------------------------------------

    async def set_actuator(self, path: str, value: float | str | bool) -> bool:
        """Set a target value for a VSS actuator.

        Args:
            path: VSS actuator path.
            value: Desired target value.

        Returns:
            ``True`` on success.

        Raises:
            SignalNotFoundError: If the path does not exist.
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        logger.info("Setting actuator %s to %s", path, value)
        try:
            vtype = _infer_data_type(value)
            entry = DataEntry(path, value=Datapoint(value), value_type=vtype)
            await client.set(updates=[EntryUpdate(entry, (Field.VALUE,))])
        except VSSClientError as exc:
            _classify_vss_error(exc, path)
        return True

    # -- Subscriptions ------------------------------------------------------

    async def subscribe(
        self,
        paths: list[str],
        duration_seconds: int = DEFAULT_SUBSCRIBE_DURATION_SECONDS,
    ) -> list[dict[str, Any]]:
        """Subscribe to signal changes and collect updates over a duration.

        Args:
            paths: VSS paths to monitor.
            duration_seconds: How long to collect updates (seconds).

        Returns:
            List of update dicts with keys ``path``, ``value``, ``timestamp``.

        Raises:
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        updates: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + duration_seconds

        logger.info(
            "Subscribing to %s for %ss", paths, duration_seconds
        )

        try:
            async for batch in client.subscribe_current_values(paths):
                for path, datapoint in batch.items():
                    updates.append({
                        "path": path,
                        "value": _extract_value(datapoint),
                        "timestamp": _format_timestamp(datapoint),
                    })
                if asyncio.get_event_loop().time() >= deadline:
                    break
        except VSSClientError as exc:
            _classify_vss_error(exc, ", ".join(paths))

        logger.info("Subscription complete: collected %s updates", len(updates))
        return updates

    # -- Metadata -----------------------------------------------------------

    async def get_metadata(self, path: str) -> SignalMetadata:
        """Retrieve metadata for a specific VSS signal.

        Args:
            path: Fully qualified VSS path.

        Returns:
            ``SignalMetadata`` with type, description, and unit info.

        Raises:
            SignalNotFoundError: If the path does not exist.
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        try:
            result = await client.get_metadata([path])
        except VSSClientError as exc:
            _classify_vss_error(exc, path)

        meta = result.get(path)
        if meta is None:
            raise SignalNotFoundError(path)

        self._metadata_cache[path] = meta

        return SignalMetadata(
            path=path,
            data_type=meta.data_type.name if meta.data_type else "UNSPECIFIED",
            description=meta.description or "",
            unit=meta.unit or "",
            entry_type=meta.entry_type.name if meta.entry_type else "UNSPECIFIED",
        )

    async def search_tree(self, keyword: str) -> list[SignalInfo]:
        """Search the VSS tree for signals matching a keyword.

        Performs a case-insensitive search against signal paths
        and descriptions.  An empty keyword returns all signals.

        Args:
            keyword: Search term (matched against path and description).

        Returns:
            List of ``SignalInfo`` for matching signals.

        Raises:
            DatabrokerConnectionError: If the Databroker is unreachable.
        """
        client = await self._ensure_connected()
        try:
            result = await client.get_metadata(["**"])
        except VSSClientError as exc:
            _classify_vss_error(exc, "**")

        keyword_lower = keyword.lower()
        matches: list[SignalInfo] = []
        for path, meta in result.items():
            description = meta.description or ""
            if keyword_lower in path.lower() or keyword_lower in description.lower():
                matches.append(SignalInfo(
                    path=path,
                    data_type=meta.data_type.name if meta.data_type else "UNSPECIFIED",
                    description=description,
                ))

        logger.info(
            "Tree search for '%s' returned %s results", keyword, len(matches)
        )
        return matches

    # -- Internal helpers ---------------------------------------------------

    async def _get_unit_cached(self, path: str) -> str:
        """Return the unit for *path*, using a local cache when possible.

        Args:
            path: Fully qualified VSS path.

        Returns:
            Unit string, or empty string if unavailable.
        """
        if path in self._metadata_cache:
            return self._metadata_cache[path].unit or ""

        try:
            meta = await self.get_metadata(path)
            return meta.unit
        except (SignalNotFoundError, DatabrokerConnectionError):
            logger.debug("Could not fetch unit for %s", path)
            return ""
