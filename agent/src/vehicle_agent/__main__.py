"""Entry point for ``python -m vehicle_agent``.

Launches the FastAPI application with Uvicorn using configuration
from environment variables.
"""

import logging

import uvicorn

from vehicle_agent.config import get_config

logger = logging.getLogger(__name__)


def main() -> None:
    """Launch the Vehicle AI Agent server."""
    config = get_config()

    log_level = config.agent_log_level.lower()
    logger.info("Starting Vehicle AI Agent on port 8000")

    uvicorn.run(
        "vehicle_agent.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
