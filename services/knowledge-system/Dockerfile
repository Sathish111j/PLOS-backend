# ============================================================================
# PLOS Knowledge System - Dockerfile
# Focus: stability on WSL2 (smaller build context + fewer pip resolver passes)
# ============================================================================

FROM python:3.14-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Copy requirements first for caching
COPY services/knowledge-system/requirements.txt ./requirements.txt

# Install all deps in a single resolver pass (reduces peak memory vs many RUNs)
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ============================================================================
# Stage 2: Production - Minimal runtime image
# ============================================================================
FROM python:3.14-slim AS production

# Security: Create non-root user
RUN groupadd --gid 1000 plos && \
    useradd --uid 1000 --gid plos --shell /bin/bash --create-home plos

WORKDIR /app

# Install runtime dependencies only (no gcc, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=plos:plos shared /app/shared

COPY --chown=plos:plos services/knowledge-system/src /app/src

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=knowledge-system \
    SERVICE_PORT=8003 \
    UVICORN_LOOP=uvloop \
    UVICORN_HTTP=httptools

# Switch to non-root user
USER plos

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8003", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--log-level", "info"]
