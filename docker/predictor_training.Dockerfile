# Use UV with Python 3.12 on Debian bookworm-slim for better wheel support
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Enable bytecode compilation for better performance
ENV UV_COMPILE_BYTECODE=1

# Copy from cache instead of linking
ENV UV_LINK_MODE=copy

# Copy the predictor service
COPY services/predictor /app/services/predictor

# Change to predictor directory
WORKDIR /app/services/predictor

# Install, build, and cleanup in single layer
RUN apt-get update && apt-get install -y \
    build-essential cmake git libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --no-dev \
    && uv add setuptools \
    && apt-get purge -y build-essential cmake \
    && apt-get autoremove -y \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache/* \
    && find /app -name "*.pyc" -delete \
    && find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Create necessary directories
RUN mkdir -p /app/drift_reports /app/reports

# Set environment to use the virtual environment
ENV PATH="/app/services/predictor/.venv/bin:$PATH"

# Set Python environment variables for optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mlflow; print('OK')" || exit 1

# Entry point
ENTRYPOINT ["python", "src/predictor/train.py"]
