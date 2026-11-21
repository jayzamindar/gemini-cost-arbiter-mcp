# ==============================================================================
# Multi-Stage Secure Dockerfile for Gemini Cost Arbiter MCP Server
# Target Standard: Non-root execution, minimal attack surface, health checks
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder (Compile dependencies and wheels)
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /build

# Install compilation essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy configuration and source files
COPY pyproject.toml requirements.txt README.md /build/
COPY config/ /build/config/
COPY src/ /build/src/
COPY app/ /build/app/

# Build standalone application wheels
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt setuptools


# ------------------------------------------------------------------------------
# Stage 2: Production Runner (Lean, Non-Root Runtime)
# ------------------------------------------------------------------------------
FROM python:3.13-slim AS runner

# Create non-root system user and group (UID/GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser

WORKDIR /app

# Install runtime dependencies from wheels only (no compilers in final image)
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application files and runtime configs
COPY config/ /app/config/
COPY prompts/ /app/prompts/
COPY README.md /app/

# Create persistent data directory for SQLite ledger and grant ownership
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Enforce non-root execution
USER appuser

# Expose Model Context Protocol SSE HTTP Port
EXPOSE 8000

# Container health probe validating FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)"

# Default command: Host Model Context Protocol over Server-Sent Events with persistent ledger
CMD ["gemini-cost-arbiter", "run-mcp", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000", "--db-path", "/app/data/finops.db"]
