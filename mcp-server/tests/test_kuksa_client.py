"""Unit tests for KuksaClientWrapper.

Tests the client wrapper, Pydantic response models, custom exceptions,
and helper functions with mocked gRPC dependencies -- no real
Databroker connection required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kuksa_mcp.kuksa_client import (
    DEFAULT_SUBSCRIBE_DURATION_SECONDS,
    DatabrokerConnectionError,
    KuksaClientWrapper,
    MAX_RECONNECT_ATTEMPTS,
    SignalInfo,
    SignalMetadata,
    SignalNotFoundError,
    SignalValue,
    _classify_vss_error,
    _extract_value,
    _format_timestamp,
    _infer_data_type,
)

# ---------------------------------------------------------------------------
# Module path for patching VSSClient in the kuksa_client module
# ---------------------------------------------------------------------------
_VSS_CLIENT_PATCH = "kuksa_mcp.kuksa_client.VSSClient"
_DATAPOINT_PATCH = "kuksa_mcp.kuksa_client.Datapoint"


# ===================================================================
# Custom Exceptions
# ===================================================================
class TestSignalNotFoundError:
    """Tests for ``SignalNotFoundError``."""

    def test_stores_path(self) -> None:
        """Exception retains the VSS path that was not found."""
        exc = SignalNotFoundError("Vehicle.Speed")
        assert exc.path == "Vehicle.Speed"

    def test_message_contains_path(self) -> None:
        """String representation includes the missing path."""
        exc = SignalNotFoundError("Vehicle.Invalid.Path")
        assert "Vehicle.Invalid.Path" in str(exc)

    def test_inherits_from_exception(self) -> None:
        """Exception is a subclass of built-in Exception."""
        exc = SignalNotFoundError("Vehicle.Speed")
        assert isinstance(exc, Exception)


class TestDatabrokerConnectionError:
    """Tests for ``DatabrokerConnectionError``."""

    def test_stores_detail(self) -> None:
        """Exception retains the connection error detail."""
        exc = DatabrokerConnectionError("Connection refused")
        assert exc.detail == "Connection refused"

    def test_default_detail(self) -> None:
        """Default detail message is applied when none given."""
        exc = DatabrokerConnectionError()
        assert exc.detail == "Databroker unreachable"

    def test_message_matches_detail(self) -> None:
        """String representation matches the detail."""
        exc = DatabrokerConnectionError("timeout")
        assert str(exc) == "timeout"

    def test_inherits_from_exception(self) -> None:
        """Exception is a subclass of built-in Exception."""
        exc = DatabrokerConnectionError("err")
        assert isinstance(exc, Exception)


# ===================================================================
# Helper Functions
# ===================================================================
class TestExtractValue:
    """Tests for ``_extract_value`` helper."""

    def test_none_input_returns_none(self) -> None:
        """None datapoint produces None."""
        assert _extract_value(None) is None

    def test_datapoint_with_float(self) -> None:
        """Float value is correctly extracted."""
        dp = MagicMock()
        dp.value = 42.5
        assert _extract_value(dp) == 42.5

    def test_datapoint_with_string(self) -> None:
        """String value is correctly extracted."""
        dp = MagicMock()
        dp.value = "P0301"
        assert _extract_value(dp) == "P0301"

    def test_datapoint_with_bool(self) -> None:
        """Boolean value is correctly extracted."""
        dp = MagicMock()
        dp.value = True
        assert _extract_value(dp) is True

    def test_datapoint_with_zero(self) -> None:
        """Zero is a valid value, not confused with None."""
        dp = MagicMock()
        dp.value = 0
        assert _extract_value(dp) == 0

    def test_datapoint_with_list_str(self) -> None:
        """list[str] value (e.g. DTC codes) is correctly extracted."""
        dp = MagicMock()
        dp.value = ["P0301", "P0420"]
        assert _extract_value(dp) == ["P0301", "P0420"]

    def test_datapoint_with_protobuf_string_array(self) -> None:
        """Protobuf StringArray wrapper (has .values) is unwrapped to list."""
        dp = MagicMock()
        string_array = MagicMock(spec=["values"])
        string_array.values = ["P0301", "P0420"]
        dp.value = string_array
        result = _extract_value(dp)
        assert result == ["P0301", "P0420"]


class TestFormatTimestamp:
    """Tests for ``_format_timestamp`` helper."""

    def test_none_input_returns_current_utc(self) -> None:
        """None datapoint falls back to current UTC timestamp."""
        ts = _format_timestamp(None)
        assert isinstance(ts, str)
        assert len(ts) > 0
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_datapoint_with_none_timestamp(self) -> None:
        """Datapoint with None timestamp falls back to current UTC."""
        dp = MagicMock()
        dp.timestamp = None
        ts = _format_timestamp(dp)
        assert isinstance(ts, str)
        assert len(ts) > 0

    def test_datapoint_with_valid_timestamp(self) -> None:
        """Datapoint with a real timestamp uses its isoformat."""
        dp = MagicMock()
        dp.timestamp = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _format_timestamp(dp)
        assert "2026-01-15" in result


class TestClassifyVssError:
    """Tests for ``_classify_vss_error`` helper."""

    def test_not_found_raises_signal_not_found(self) -> None:
        """gRPC NOT_FOUND maps to SignalNotFoundError."""
        import grpc
        from kuksa_client.grpc import VSSClientError

        exc = VSSClientError(
            {"code": grpc.StatusCode.NOT_FOUND.value[0]}, [],
        )
        with pytest.raises(SignalNotFoundError) as exc_info:
            _classify_vss_error(exc, "Vehicle.Bad")
        assert exc_info.value.path == "Vehicle.Bad"

    def test_other_code_raises_connection_error(self) -> None:
        """Non-NOT_FOUND gRPC codes map to DatabrokerConnectionError."""
        from kuksa_client.grpc import VSSClientError

        exc = VSSClientError(
            {"code": 999, "message": "internal error"}, [],
        )
        with pytest.raises(DatabrokerConnectionError):
            _classify_vss_error(exc, "Vehicle.Speed")

    def test_missing_message_key(self) -> None:
        """Error dict without 'message' still raises with str(exc)."""
        from kuksa_client.grpc import VSSClientError

        exc = VSSClientError({"code": 999}, [])
        with pytest.raises(DatabrokerConnectionError):
            _classify_vss_error(exc, "Vehicle.Speed")


# ===================================================================
# Pydantic Response Models
# ===================================================================
class TestSignalValue:
    """Tests for the ``SignalValue`` Pydantic model."""

    def test_full_creation(self) -> None:
        """All fields populate correctly."""
        sv = SignalValue(
            path="Vehicle.Speed",
            value=65.0,
            timestamp="2026-01-01T00:00:00+00:00",
            unit="km/h",
        )
        assert sv.path == "Vehicle.Speed"
        assert sv.value == 65.0
        assert sv.timestamp == "2026-01-01T00:00:00+00:00"
        assert sv.unit == "km/h"

    def test_optional_value_defaults_to_none(self) -> None:
        """Value defaults to None when not provided."""
        sv = SignalValue(path="Vehicle.Speed")
        assert sv.value is None

    def test_optional_unit_defaults_to_empty(self) -> None:
        """Unit defaults to empty string when not provided."""
        sv = SignalValue(path="Vehicle.Speed")
        assert sv.unit == ""

    def test_model_dump(self) -> None:
        """model_dump returns a serialisable dict."""
        sv = SignalValue(path="Vehicle.Speed", value=10.0)
        dumped = sv.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["path"] == "Vehicle.Speed"

    def test_string_value(self) -> None:
        """String values are accepted."""
        sv = SignalValue(path="Vehicle.OBD.DTCList", value="P0301,P0420")
        assert sv.value == "P0301,P0420"

    def test_bool_value(self) -> None:
        """Boolean values are accepted."""
        sv = SignalValue(path="Vehicle.IsMoving", value=True)
        assert sv.value is True

    def test_list_str_value(self) -> None:
        """list[str] values are accepted for STRING_ARRAY signals like DTCList."""
        sv = SignalValue(path="Vehicle.OBD.DTCList", value=["P0301", "P0420"])
        assert sv.value == ["P0301", "P0420"]

    def test_empty_list_value(self) -> None:
        """Empty list is a valid value for STRING_ARRAY signals."""
        sv = SignalValue(path="Vehicle.OBD.DTCList", value=[])
        assert sv.value == []


class TestSignalMetadata:
    """Tests for the ``SignalMetadata`` Pydantic model."""

    def test_full_creation(self) -> None:
        """All fields populate correctly."""
        sm = SignalMetadata(
            path="Vehicle.Speed",
            data_type="FLOAT",
            description="Vehicle speed",
            unit="km/h",
            entry_type="SENSOR",
        )
        assert sm.path == "Vehicle.Speed"
        assert sm.data_type == "FLOAT"
        assert sm.description == "Vehicle speed"
        assert sm.unit == "km/h"
        assert sm.entry_type == "SENSOR"

    def test_defaults(self) -> None:
        """Optional fields use proper defaults."""
        sm = SignalMetadata(path="Vehicle.Speed")
        assert sm.data_type == "UNSPECIFIED"
        assert sm.description == ""
        assert sm.unit == ""
        assert sm.entry_type == "UNSPECIFIED"


class TestSignalInfo:
    """Tests for the ``SignalInfo`` Pydantic model."""

    def test_full_creation(self) -> None:
        """All fields populate correctly."""
        si = SignalInfo(
            path="Vehicle.Speed",
            data_type="FLOAT",
            description="Vehicle speed",
        )
        assert si.path == "Vehicle.Speed"
        assert si.data_type == "FLOAT"
        assert si.description == "Vehicle speed"

    def test_defaults(self) -> None:
        """Optional fields use proper defaults."""
        si = SignalInfo(path="Vehicle.Speed")
        assert si.data_type == "UNSPECIFIED"
        assert si.description == ""


# ===================================================================
# KuksaClientWrapper
# ===================================================================
class TestKuksaClientWrapperInit:
    """Tests for ``KuksaClientWrapper.__init__``."""

    def test_stores_host_and_port(self) -> None:
        """Constructor stores host and port attributes."""
        client = KuksaClientWrapper(host="broker.local", port=12345)
        assert client._host == "broker.local"
        assert client._port == 12345

    def test_initial_client_is_none(self) -> None:
        """Internal VSSClient is None before connect."""
        client = KuksaClientWrapper(host="localhost", port=55555)
        assert client._client is None

    def test_metadata_cache_initially_empty(self) -> None:
        """Metadata cache starts empty."""
        client = KuksaClientWrapper(host="localhost", port=55555)
        assert client._metadata_cache == {}


class TestKuksaClientWrapperConnect:
    """Tests for ``connect`` and ``disconnect``."""

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Successful connection sets the internal client."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            MockVSSClient.assert_called_once_with(
                host="localhost",
                port=55555,
                ensure_startup_connection=False,
            )
            mock_instance.connect.assert_awaited_once()
            assert client._client is mock_instance

    @pytest.mark.asyncio
    async def test_connect_failure_raises_connection_error(self) -> None:
        """Failed connection raises DatabrokerConnectionError."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connect.side_effect = Exception("Connection refused")
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            with pytest.raises(DatabrokerConnectionError) as exc_info:
                await client.connect()
            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_failure_clears_client(self) -> None:
        """Failed connection sets internal client to None."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connect.side_effect = Exception("fail")
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            with pytest.raises(DatabrokerConnectionError):
                await client.connect()
            assert client._client is None

    @pytest.mark.asyncio
    async def test_disconnect_success(self) -> None:
        """Disconnect calls the underlying client and clears reference."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            await client.disconnect()

            mock_instance.disconnect.assert_awaited_once()
            assert client._client is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self) -> None:
        """Disconnect on an unconnected client does not raise."""
        client = KuksaClientWrapper("localhost", 55555)
        await client.disconnect()  # Should not raise
        assert client._client is None

    @pytest.mark.asyncio
    async def test_disconnect_ignores_underlying_error(self) -> None:
        """Disconnect swallows errors from the underlying client."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.disconnect.side_effect = RuntimeError("oops")
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            await client.disconnect()  # Should not raise

            assert client._client is None


class TestEnsureConnected:
    """Tests for the lazy reconnection logic."""

    @pytest.mark.asyncio
    async def test_returns_existing_connected_client(self) -> None:
        """If already connected, returns the existing client immediately."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            result = await client._ensure_connected()
            assert result is mock_instance
            # connect was called once (initial), not again
            assert mock_instance.connect.await_count == 1

    @pytest.mark.asyncio
    async def test_reconnects_when_disconnected(self) -> None:
        """If not connected, attempts to reconnect."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            # First call: not connected; after connect(): connected
            mock_instance.connected = True
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            # Don't call connect() first -- simulate lazy start
            result = await client._ensure_connected()
            assert result is not None

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """Raises DatabrokerConnectionError after exhausting retries."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connect.side_effect = Exception("down")
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            with pytest.raises(DatabrokerConnectionError) as exc_info:
                await client._ensure_connected()
            assert f"{MAX_RECONNECT_ATTEMPTS}" in str(exc_info.value)


class TestGetSignal:
    """Tests for ``get_signal``."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Successful query returns a populated SignalValue."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_dp = MagicMock()
            mock_dp.value = 65.0
            mock_dp.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
            mock_instance.get_current_values.return_value = {
                "Vehicle.Speed": mock_dp,
            }

            # Metadata for unit lookup
            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "Vehicle speed"
            mock_meta.unit = "km/h"
            mock_meta.entry_type = MagicMock()
            mock_meta.entry_type.name = "SENSOR"
            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            result = await client.get_signal("Vehicle.Speed")

            assert isinstance(result, SignalValue)
            assert result.path == "Vehicle.Speed"
            assert result.value == 65.0
            assert result.unit == "km/h"

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        """VSSClientError with NOT_FOUND code raises SignalNotFoundError."""
        from kuksa_client.grpc import VSSClientError

        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            import grpc

            mock_instance.get_current_values.side_effect = VSSClientError(
                {"code": grpc.StatusCode.NOT_FOUND.value[0], "message": "not found"},
                [],
            )

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            with pytest.raises(SignalNotFoundError):
                await client.get_signal("Vehicle.Bad.Path")


class TestGetSignals:
    """Tests for ``get_signals``."""

    @pytest.mark.asyncio
    async def test_success_returns_dict(self) -> None:
        """Successful batch query returns dict of SignalValues."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_dp1 = MagicMock()
            mock_dp1.value = 65.0
            mock_dp1.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

            mock_dp2 = MagicMock()
            mock_dp2.value = 1500.0
            mock_dp2.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

            mock_instance.get_current_values.return_value = {
                "Vehicle.Speed": mock_dp1,
                "Vehicle.Powertrain.CombustionEngine.Speed": mock_dp2,
            }

            # Metadata stub
            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "signal"
            mock_meta.unit = "km/h"
            mock_meta.entry_type = MagicMock()
            mock_meta.entry_type.name = "SENSOR"
            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            paths = [
                "Vehicle.Speed",
                "Vehicle.Powertrain.CombustionEngine.Speed",
            ]
            result = await client.get_signals(paths)

            assert len(result) == 2
            assert "Vehicle.Speed" in result
            assert isinstance(result["Vehicle.Speed"], SignalValue)
            assert result["Vehicle.Speed"].value == 65.0


class TestInferDataType:
    """Tests for the ``_infer_data_type`` helper."""

    def test_bool_maps_to_boolean(self) -> None:
        """Python bool maps to DataType.BOOLEAN."""
        from kuksa_client.grpc import DataType

        assert _infer_data_type(True) == DataType.BOOLEAN
        assert _infer_data_type(False) == DataType.BOOLEAN

    def test_int_maps_to_int32(self) -> None:
        """Python int maps to DataType.INT32."""
        from kuksa_client.grpc import DataType

        assert _infer_data_type(42) == DataType.INT32

    def test_float_maps_to_float(self) -> None:
        """Python float maps to DataType.FLOAT."""
        from kuksa_client.grpc import DataType

        assert _infer_data_type(24.5) == DataType.FLOAT

    def test_str_maps_to_string(self) -> None:
        """Python str maps to DataType.STRING."""
        from kuksa_client.grpc import DataType

        assert _infer_data_type("on") == DataType.STRING

    def test_bool_takes_priority_over_int(self) -> None:
        """bool must map to BOOLEAN even though bool is a subclass of int."""
        from kuksa_client.grpc import DataType

        # bool is a subclass of int; isinstance(True, int) == True.
        # The helper must check bool first.
        assert _infer_data_type(True) == DataType.BOOLEAN


class TestSetActuator:
    """Tests for ``set_actuator``."""

    @pytest.mark.asyncio
    async def test_success_returns_true(self) -> None:
        """Successful set returns True; uses client.set() with Field.VALUE."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            path = "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
            result = await client.set_actuator(path, 24.0)

            assert result is True
            mock_instance.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        """VSSClientError for bad path raises SignalNotFoundError."""
        from kuksa_client.grpc import VSSClientError

        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            import grpc

            mock_instance.set.side_effect = VSSClientError(
                {"code": grpc.StatusCode.NOT_FOUND.value[0], "message": "not found"},
                [],
            )

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            with pytest.raises(SignalNotFoundError):
                await client.set_actuator("Vehicle.Bad.Path", 42.0)


class TestSearchTree:
    """Tests for ``search_tree``."""

    @pytest.mark.asyncio
    async def test_keyword_matches_path(self) -> None:
        """Keyword matching against path returns results."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta_speed = MagicMock()
            mock_meta_speed.data_type = MagicMock()
            mock_meta_speed.data_type.name = "FLOAT"
            mock_meta_speed.description = "Vehicle speed"

            mock_meta_rpm = MagicMock()
            mock_meta_rpm.data_type = MagicMock()
            mock_meta_rpm.data_type.name = "FLOAT"
            mock_meta_rpm.description = "Engine RPM"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta_speed,
                "Vehicle.Powertrain.CombustionEngine.Speed": mock_meta_rpm,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            results = await client.search_tree("Speed")

            # Both contain "Speed" in path
            assert len(results) == 2
            paths = [r.path for r in results]
            assert "Vehicle.Speed" in paths

    @pytest.mark.asyncio
    async def test_keyword_matches_description(self) -> None:
        """Keyword matching against description returns results."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "Engine coolant temperature"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Powertrain.CombustionEngine.ECT": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            results = await client.search_tree("coolant")

            assert len(results) == 1
            assert results[0].description == "Engine coolant temperature"

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self) -> None:
        """Search is case-insensitive."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "Vehicle speed"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            # Uppercase keyword should still match lowercase description
            results = await client.search_tree("SPEED")
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_keyword_returns_all(self) -> None:
        """Empty keyword returns every signal."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "Vehicle speed"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            results = await client.search_tree("")
            assert len(results) == 1


class TestGetMetadata:
    """Tests for ``get_metadata``."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Successful metadata query returns SignalMetadata."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "Vehicle speed"
            mock_meta.unit = "km/h"
            mock_meta.entry_type = MagicMock()
            mock_meta.entry_type.name = "SENSOR"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()
            result = await client.get_metadata("Vehicle.Speed")

            assert isinstance(result, SignalMetadata)
            assert result.path == "Vehicle.Speed"
            assert result.data_type == "FLOAT"
            assert result.unit == "km/h"
            assert result.entry_type == "SENSOR"

    @pytest.mark.asyncio
    async def test_not_found_when_result_empty(self) -> None:
        """Empty metadata result raises SignalNotFoundError."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True
            mock_instance.get_metadata.return_value = {}

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            with pytest.raises(SignalNotFoundError):
                await client.get_metadata("Vehicle.Missing")

    @pytest.mark.asyncio
    async def test_caches_metadata(self) -> None:
        """Metadata is cached after first fetch."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True

            mock_meta = MagicMock()
            mock_meta.data_type = MagicMock()
            mock_meta.data_type.name = "FLOAT"
            mock_meta.description = "speed"
            mock_meta.unit = "km/h"
            mock_meta.entry_type = MagicMock()
            mock_meta.entry_type.name = "SENSOR"

            mock_instance.get_metadata.return_value = {
                "Vehicle.Speed": mock_meta,
            }

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            await client.get_metadata("Vehicle.Speed")
            assert "Vehicle.Speed" in client._metadata_cache


class TestGetUnitCached:
    """Tests for ``_get_unit_cached``."""

    @pytest.mark.asyncio
    async def test_returns_cached_unit(self) -> None:
        """Returns unit from cache when available."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True
            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            # Pre-populate cache
            mock_meta = MagicMock()
            mock_meta.unit = "km/h"
            client._metadata_cache["Vehicle.Speed"] = mock_meta

            result = await client._get_unit_cached("Vehicle.Speed")
            assert result == "km/h"

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self) -> None:
        """Returns empty string if metadata lookup fails."""
        with patch(_VSS_CLIENT_PATCH) as MockVSSClient:
            mock_instance = AsyncMock()
            mock_instance.connected = True
            mock_instance.get_metadata.return_value = {}

            MockVSSClient.return_value = mock_instance

            client = KuksaClientWrapper("localhost", 55555)
            await client.connect()

            result = await client._get_unit_cached("Vehicle.Unknown")
            assert result == ""
