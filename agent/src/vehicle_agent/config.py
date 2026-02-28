"""Configuration management for the Vehicle AI Agent.

Loads settings from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Application configuration loaded from environment variables.

    Attributes:
        gemini_api_key: Google Gemini API key for LLM access.
        gemini_model: Gemini model identifier to use for generation.
        kuksa_databroker_host: Hostname of Kuksa Databroker gRPC endpoint.
        kuksa_databroker_port: Port of Kuksa Databroker gRPC endpoint.
        mcp_server_command: Executable to launch the MCP server subprocess.
        mcp_server_args: Arguments passed to the MCP server subprocess.
        mcp_server_cwd: Working directory for the MCP server subprocess.
        agent_log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        max_tool_calls_per_turn: Maximum tool invocations per single user turn.
    """

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    kuksa_databroker_host: str = "localhost"
    kuksa_databroker_port: int = 55555
    mcp_server_command: str = "python"
    mcp_server_args: list[str] = ["-m", "kuksa_mcp.server"]
    mcp_server_cwd: str | None = None
    agent_log_level: str = "INFO"
    max_tool_calls_per_turn: int = 10

    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_config() -> AgentConfig:
    """Get the application configuration singleton.

    Returns:
        Cached AgentConfig instance loaded from environment.
    """
    return AgentConfig()
