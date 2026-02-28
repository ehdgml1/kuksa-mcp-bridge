"""Configuration management for Kuksa MCP Bridge Server.

Loads settings from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class KuksaMcpConfig(BaseSettings):
    """Application configuration loaded from environment variables.

    Attributes:
        kuksa_databroker_host: Hostname of Kuksa Databroker gRPC endpoint.
        kuksa_databroker_port: Port of Kuksa Databroker gRPC endpoint.
        mcp_server_name: Human-readable MCP server name.
        mcp_log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        sim_mode: Simulator scenario mode.
        sim_update_interval_ms: Signal update interval in milliseconds.
    """

    kuksa_databroker_host: str = "localhost"
    kuksa_databroker_port: int = 55555
    mcp_server_name: str = "kuksa-vehicle-bridge"
    mcp_log_level: str = "INFO"
    sim_mode: str = "normal_driving"
    sim_update_interval_ms: int = 500

    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_config() -> KuksaMcpConfig:
    """Get the application configuration singleton.

    Returns:
        Cached KuksaMcpConfig instance loaded from environment.
    """
    return KuksaMcpConfig()
