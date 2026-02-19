FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY services/knowledge-base/requirements/base.txt /tmp/requirements/base.txt
COPY services/knowledge-base/requirements/api.txt /tmp/requirements/api.txt
COPY services/knowledge-base/requirements/storage.txt /tmp/requirements/storage.txt
COPY services/knowledge-base/requirements/ai.txt /tmp/requirements/ai.txt
COPY services/knowledge-base/requirements/processing.txt /tmp/requirements/processing.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements/base.txt && \
    pip install --no-cache-dir -r /tmp/requirements/api.txt && \
    pip install --no-cache-dir -r /tmp/requirements/storage.txt && \
    pip install --no-cache-dir -r /tmp/requirements/processing.txt && \
    pip install --no-cache-dir -r /tmp/requirements/ai.txt && \
    rm -rf /root/.cache/pip

FROM python:3.11-slim AS production

RUN groupadd --gid 1000 plos && \
    useradd --uid 1000 --gid plos --shell /bin/bash --create-home plos

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=plos:plos shared /app/shared
COPY --chown=plos:plos services/knowledge-base/src/app /app/app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=knowledge-base \
    SERVICE_PORT=8003

USER plos

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2", "--loop", "uvloop", "--http", "httptools"]
