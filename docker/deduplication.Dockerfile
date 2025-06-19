FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY services/deduplication/pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY services/deduplication/src/deduplication ./deduplication

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose health check port
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "-m", "deduplication.main"] 