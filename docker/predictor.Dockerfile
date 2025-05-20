########################  Stage 1 – builder  ##########################
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set uv configuration for better performance and Docker compatibility
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install build dependencies for scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the application source
COPY services/predictor/ .

# Install dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e .

# Create necessary directories with proper permissions
RUN mkdir -p /app/drift_reports /app/reports && \
    chmod -R 777 /app/drift_reports /app/reports

########################  Stage 2 – runtime  ##########################
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/

# Copy application files
COPY --from=builder /app/ /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create and use non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from predictor.main import __name__ as _; sys.exit(0)"

# Use exec form for ENTRYPOINT to avoid shell requirement
ENTRYPOINT ["python", "/app/src/predictor/main.py"]
