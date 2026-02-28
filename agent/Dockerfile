FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Install mcp-server in its own venv (needed as subprocess)
COPY mcp-server/pyproject.toml mcp-server/uv.lock /mcp-server/
COPY mcp-server/src/ /mcp-server/src/
RUN cd /mcp-server && uv sync --frozen --no-dev

# Install agent server
COPY agent/pyproject.toml agent/uv.lock ./
COPY agent/src/ src/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# MCP subprocess uses the mcp-server's own venv Python
ENV MCP_SERVER_COMMAND="/mcp-server/.venv/bin/python"
ENV MCP_SERVER_ARGS='["-m", "kuksa_mcp.server"]'
ENV MCP_SERVER_CWD="/mcp-server"

CMD ["uvicorn", "vehicle_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
