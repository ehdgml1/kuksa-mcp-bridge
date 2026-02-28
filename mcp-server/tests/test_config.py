"""Unit tests for configuration management.

Tests that KuksaMcpConfig loads defaults correctly and honours
environment variable overrides.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from kuksa_mcp.config import KuksaMcpConfig, get_config


# ===================================================================
# KuksaMcpConfig
# ===================================================================
class TestKuksaMcpConfig:
    """Tests for the ``KuksaMcpConfig`` settings model."""

    def test_default_values(self) -> None:
        """All fields have sensible defaults when no env vars are set."""
        config = KuksaMcpConfig(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert config.kuksa_databroker_host == "localhost"
        assert config.kuksa_databroker_port == 55555
        assert config.mcp_server_name == "kuksa-vehicle-bridge"
        assert config.mcp_log_level == "INFO"
        assert config.sim_mode == "normal_driving"
        assert config.sim_update_interval_ms == 500

    def test_env_override_host(self) -> None:
        """KUKSA_DATABROKER_HOST environment variable overrides default."""
        with patch.dict(
            os.environ,
            {"KUKSA_DATABROKER_HOST": "broker.example.com"},
        ):
            config = KuksaMcpConfig(_env_file=None)  # type: ignore[call-arg]
            assert config.kuksa_databroker_host == "broker.example.com"

    def test_env_override_port(self) -> None:
        """KUKSA_DATABROKER_PORT environment variable overrides default."""
        with patch.dict(
            os.environ,
            {"KUKSA_DATABROKER_PORT": "12345"},
        ):
            config = KuksaMcpConfig(_env_file=None)  # type: ignore[call-arg]
            assert config.kuksa_databroker_port == 12345

    def test_env_override_log_level(self) -> None:
        """MCP_LOG_LEVEL environment variable overrides default."""
        with patch.dict(os.environ, {"MCP_LOG_LEVEL": "DEBUG"}):
            config = KuksaMcpConfig(_env_file=None)  # type: ignore[call-arg]
            assert config.mcp_log_level == "DEBUG"

    def test_env_override_sim_mode(self) -> None:
        """SIM_MODE environment variable overrides default."""
        with patch.dict(os.environ, {"SIM_MODE": "engine_warning"}):
            config = KuksaMcpConfig(_env_file=None)  # type: ignore[call-arg]
            assert config.sim_mode == "engine_warning"


# ===================================================================
# get_config singleton
# ===================================================================
class TestGetConfig:
    """Tests for the ``get_config`` cached singleton."""

    def test_returns_config_instance(self) -> None:
        """get_config returns a KuksaMcpConfig instance."""
        # Clear the lru_cache to avoid pollution from other tests
        get_config.cache_clear()
        config = get_config()
        assert isinstance(config, KuksaMcpConfig)

    def test_returns_same_instance(self) -> None:
        """Subsequent calls return the same cached instance."""
        get_config.cache_clear()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
