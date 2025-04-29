# Use the official Structurizr Lite as base
FROM structurizr/lite:latest

# Add OCI-compliant labels
LABEL org.opencontainers.image.title="Structurizr Documentation"
LABEL org.opencontainers.image.description="C4 model documentation for Real-time Trading System"
LABEL org.opencontainers.image.vendor="RWMLOps"
LABEL org.opencontainers.image.authors="mdshihabullah"
LABEL org.opencontainers.image.source="https://github.com/mdshihabullah/real-time-crypto-price-predictor"
LABEL org.opencontainers.image.url="https://github.com/mdshihabullah/real-time-crypto-price-predictor"
LABEL org.opencontainers.image.version="0.0.1"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /usr/local/structurizr

# Copy the C4 model files
COPY docs/c4model/ .

# Fix permissions - this is critical
RUN chown -R 1000:1000 /usr/local/structurizr && \
    chmod -R 755 /usr/local/structurizr && \
    find /usr/local/structurizr -type d -exec chmod 755 {} \; && \
    find /usr/local/structurizr -type f -exec chmod 644 {} \;


# Add health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

# Explicitly set the user to non-root for security
USER 1000:1000

# Document the port that will be exposed
EXPOSE 8080
