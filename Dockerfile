# Build Stage
FROM python:3.14-slim as builder

WORKDIR /app

# Security: Install updates and build deps
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtualenv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final Stage
FROM python:3.14-slim

WORKDIR /app

# Security: Install updates and runtime deps (libpq5 for postgres)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Set environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create writable uploads dir before switching to non-root
RUN mkdir -p /app/uploads && chmod 777 /app/uploads
ENV UPLOAD_DIR=/app/uploads

# Security: Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# Default port (Railway overrides via $PORT)
ENV PORT=8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run Application with Env Validation
CMD ["/bin/bash", "-c", "python scripts/check_env.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
