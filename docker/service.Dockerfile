# Stage 1: Builder - using an image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and set link mode
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set service name as build argument
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}

# Copy the entire services directory to maintain workspace structure
COPY services /app/services

# Copy project configuration files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies from workspace
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    # First install the common dependencies
    uv sync --frozen --no-install-project --no-dev && \
    # Then install the specific service
    . .venv/bin/activate && \
    uv pip install -e ./services/${SERVICE_NAME}

# Stage 2: Runtime image - minimal size
FROM python:3.12-slim

# Install only essential runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser

WORKDIR /app

# Copy only the virtual environment and the specific service
COPY --from=builder /app/.venv /app/.venv
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}
COPY --from=builder /app/services/${SERVICE_NAME} /app/services/${SERVICE_NAME}

# Create state directory with appropriate permissions
# This provides a fallback if no volume is mounted
RUN mkdir -p /app/state && chown -R appuser:appuser /app/state

# Set up environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Switch to non-root user
USER appuser

# Run the service directly
CMD ["sh", "-c", "python /app/services/${SERVICE_NAME}/src/${SERVICE_NAME}/main.py"]
