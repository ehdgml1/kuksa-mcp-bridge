"""Unit tests for AgentConfig configuration management.

Tests default values, environment variable overrides, edge cases
like empty API key, and the get_config() singleton behaviour.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from vehicle_agent.config import AgentConfig, get_config


# ===================================================================
# AgentConfig defaults
# ===================================================================
class TestAgentConfigDefaults:
    """Tests that AgentConfig loads sensible defaults."""

    def test_default_gemini_model(self) -> None:
        """Default Gemini model is gemini-2.0-flash."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.gemini_model == "gemini-2.0-flash"

    def test_default_kuksa_host(self) -> None:
        """Default Kuksa Databroker host is localhost."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.kuksa_databroker_host == "localhost"

    def test_default_kuksa_port(self) -> None:
        """Default Kuksa Databroker port is 55555."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.kuksa_databroker_port == 55555

    def test_default_mcp_server_command(self) -> None:
        """Default MCP server command is 'python'."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.mcp_server_command == "python"

    def test_default_mcp_server_args(self) -> None:
        """Default MCP server args include module invocation."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.mcp_server_args == ["-m", "kuksa_mcp.server"]

    def test_default_mcp_server_cwd_is_none(self) -> None:
        """Default MCP server working directory is None (inherit)."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.mcp_server_cwd is None

    def test_default_log_level(self) -> None:
        """Default log level is INFO."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.agent_log_level == "INFO"

    def test_default_max_tool_calls(self) -> None:
        """Default max tool calls per turn is 10."""
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.max_tool_calls_per_turn == 10

    def test_default_gemini_api_key_is_empty_string(self) -> None:
        """Default gemini_api_key is empty string — no exception raised."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure GEMINI_API_KEY is not accidentally set in the test env
            env_without_key = {
                k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"
            }
            with patch.dict(os.environ, env_without_key, clear=True):
                config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
                assert config.gemini_api_key == ""


# ===================================================================
# AgentConfig env-var overrides
# ===================================================================
class TestAgentConfigEnvOverrides:
    """Tests that environment variables override AgentConfig defaults."""

    def test_gemini_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_API_KEY environment variable is picked up correctly."""
        monkeypatch.setenv("GEMINI_API_KEY", "my-secret-key-xyz")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.gemini_api_key == "my-secret-key-xyz"

    def test_gemini_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GEMINI_MODEL environment variable overrides default model."""
        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.gemini_model == "gemini-1.5-pro"

    def test_kuksa_host_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KUKSA_DATABROKER_HOST environment variable overrides default."""
        monkeypatch.setenv("KUKSA_DATABROKER_HOST", "broker.vehicle.local")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.kuksa_databroker_host == "broker.vehicle.local"

    def test_kuksa_port_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """KUKSA_DATABROKER_PORT is coerced from string to int."""
        monkeypatch.setenv("KUKSA_DATABROKER_PORT", "9999")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.kuksa_databroker_port == 9999

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AGENT_LOG_LEVEL environment variable overrides default."""
        monkeypatch.setenv("AGENT_LOG_LEVEL", "DEBUG")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.agent_log_level == "DEBUG"

    def test_max_tool_calls_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_TOOL_CALLS_PER_TURN is coerced from string to int."""
        monkeypatch.setenv("MAX_TOOL_CALLS_PER_TURN", "3")
        config = AgentConfig(_env_file=None)  # type: ignore[call-arg]
        assert config.max_tool_calls_per_turn == 3


# ===================================================================
# Empty API key edge case
# ===================================================================
class TestAgentConfigEmptyApiKey:
    """Tests around the empty Gemini API key case."""

    def test_empty_api_key_does_not_raise(self) -> None:
        """Constructing AgentConfig with empty gemini_api_key must not raise."""
        config = AgentConfig(gemini_api_key="", _env_file=None)  # type: ignore[call-arg]
        assert config.gemini_api_key == ""

    def test_empty_api_key_is_falsy(self) -> None:
        """Empty gemini_api_key evaluates to False, enabling guard checks."""
        config = AgentConfig(gemini_api_key="", _env_file=None)  # type: ignore[call-arg]
        assert not config.gemini_api_key

    def test_non_empty_api_key_is_truthy(self) -> None:
        """Non-empty gemini_api_key evaluates to True."""
        config = AgentConfig(gemini_api_key="abc", _env_file=None)  # type: ignore[call-arg]
        assert config.gemini_api_key


# ===================================================================
# get_config singleton
# ===================================================================
class TestGetConfigSingleton:
    """Tests for the lru_cache-backed get_config() factory."""

    def test_returns_agent_config_instance(self) -> None:
        """get_config() returns an AgentConfig instance."""
        get_config.cache_clear()
        config = get_config()
        assert isinstance(config, AgentConfig)

    def test_returns_same_cached_instance(self) -> None:
        """Calling get_config() twice returns the identical object."""
        get_config.cache_clear()
        config_a = get_config()
        config_b = get_config()
        assert config_a is config_b

    def test_cache_clear_returns_new_instance(self) -> None:
        """After cache_clear(), get_config() constructs a fresh instance."""
        get_config.cache_clear()
        config_a = get_config()
        get_config.cache_clear()
        config_b = get_config()
        # They may be equal in value but must be distinct objects
        assert config_a is not config_b
