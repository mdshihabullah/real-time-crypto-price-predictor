# 2-stage Dockerfile for the `technical_indicators` service

########################################################
# Stage 1: Builder with uv and TA-Lib
########################################################
FROM python:3.12-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    make \
    wget \
    tar

# Install ta-lib
ENV TALIB_DIR=/usr/local
RUN wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz && \
    tar -xzf ta-lib-0.6.4-src.tar.gz && \
    cd ta-lib-0.6.4/ && \
    ./configure --prefix=$TALIB_DIR && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.6.4-src.tar.gz ta-lib-0.6.4/

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set service name as build argument
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}

WORKDIR /app

# Copy only the requirements.txt file
COPY services/${SERVICE_NAME}/requirements.txt /app/

# Create virtual environment and install dependencies using uv add
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv add -r requirements.txt

# Copy only the required service files
COPY services/${SERVICE_NAME}/src /app/src

########################################################
# Stage 2: Efficient runtime image
########################################################
FROM python:3.12-alpine

# Required build arguments for OCI labels
ARG SERVICE_NAME
ARG BUILD_DATE
ARG VERSION
ARG SOURCE_COMMIT

# OCI-compliant labels
LABEL org.opencontainers.image.title="${SERVICE_NAME} Service" \
      org.opencontainers.image.description="Technical indicators service for cryptocurrency data processing" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.licenses="MIT"

# Install runtime dependencies only
RUN apk add --no-cache libstdc++

# Copy only necessary libraries from builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
COPY --from=builder /usr/local/include/ta-lib /usr/local/include/ta-lib
RUN ldconfig /usr/local/lib || echo "Alpine doesn't have ldconfig, continuing..."

# Set up a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy virtual environment and application code
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

# Set up environment for performance and security
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONHASHSEED=random \
    PYTHONFAULTHANDLER=1

# Create state directory if needed
RUN mkdir -p /app/state && chown -R appuser:appgroup /app/state

# Switch to non-root user
USER appuser

# Define health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0 if 'src' in sys.path else 1)"

# Run the service
CMD ["python", "/app/src/technical_indicators/main.py"]

# If you want to debug the file system, uncomment the line below
# This will keep the container running and allow you to exec into it
# CMD ["/bin/bash", "-c", "sleep 999999"]