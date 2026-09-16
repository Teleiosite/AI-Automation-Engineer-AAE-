# ==============================================================================
# AAE Production Dockerfile (Phase 23 / Production Packaging & Deployment)
# Multi-stage, minimal, non-root hardened runtime container.
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install .

# Stage 2: Final Minimal Hardened Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Install runtime dependencies (libpq for psycopg) and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged application user
RUN groupadd -g 10001 aae && \
    useradd -u 10001 -g aae -s /bin/false -m aae

# Copy application source code (includes app/db/migrations configured in alembic.ini)
COPY --chown=aae:aae app/ ./app/
COPY --chown=aae:aae alembic.ini .
COPY --chown=aae:aae pyproject.toml .

# Switch to non-root user
USER aae

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
