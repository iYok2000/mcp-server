# -----------------------------------------------------------------------------
# Stage 1: build Rust core
# -----------------------------------------------------------------------------
FROM rust:1-bookworm AS rust
WORKDIR /build

COPY core ./core
RUN cargo build --release -p core

# -----------------------------------------------------------------------------
# Stage 2: MCP server (Python + core binary)
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install uv for reproducible Python deps
RUN pip install --no-cache-dir uv

COPY control/ control/
COPY --from=rust /build/target/release/core /app/core

# Install Python deps (use uv so lockfile is respected)
RUN uv sync --frozen --project control/

# Paths for deploy: override via env or use these defaults
ENV MCP_DB_PATH=/data/mcp.db \
    MCP_CORE_BIN=/app/core

# Persist DB outside container (override MCP_DB_PATH to /data/mcp.db in run)
VOLUME /data

WORKDIR /app/control
# MCP protocol is stdio; no port to expose
ENTRYPOINT ["uv", "run", "python", "server.py"]
