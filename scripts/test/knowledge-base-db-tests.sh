#!/bin/bash
# Knowledge Base database integration tests.
# Starts minimal infrastructure (PostgreSQL, Redis, Qdrant, Meilisearch),
# runs migrations, executes the knowledge-base pytest suite, then tears down.
#
# Usage:
#   ./scripts/test/knowledge-base-db-tests.sh [pytest-args...]
#
# Environment variables (with defaults that match docker-compose.yml):
#   POSTGRES_USER     postgres
#   POSTGRES_PASSWORD plos_db_secure_2025
#   POSTGRES_DB       plos
#   REDIS_PASSWORD    plos_redis_secure_2025

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-plos_db_secure_2025}"
POSTGRES_DB="${POSTGRES_DB:-plos}"
REDIS_PASSWORD="${REDIS_PASSWORD:-plos_redis_secure_2025}"

COMPOSE_FILE="docker-compose.yml"
TIMEOUT_INFRA=120
TIMEOUT_DB=90

cleanup() {
    echo ""
    echo "--- Cleaning up test infrastructure ---"
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Start minimal infrastructure
# ---------------------------------------------------------------------------
echo "--- Starting test infrastructure ---"
docker compose -f "$COMPOSE_FILE" up -d \
    supabase-db \
    redis \
    qdrant \
    meilisearch

# ---------------------------------------------------------------------------
# 2. Wait for PostgreSQL
# ---------------------------------------------------------------------------
echo "--- Waiting for PostgreSQL (timeout ${TIMEOUT_DB}s) ---"
DB_READY=0
for i in $(seq 1 "$TIMEOUT_DB"); do
    if docker compose -f "$COMPOSE_FILE" exec -T supabase-db \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
        echo "PostgreSQL ready after ${i}s"
        DB_READY=1
        break
    fi
    sleep 1
done

if [ "$DB_READY" -eq 0 ]; then
    echo "ERROR: PostgreSQL did not become ready within ${TIMEOUT_DB}s"
    docker compose -f "$COMPOSE_FILE" logs supabase-db --tail=50
    exit 1
fi

# ---------------------------------------------------------------------------
# 3. Wait for Qdrant
# ---------------------------------------------------------------------------
echo "--- Waiting for Qdrant ---"
for i in $(seq 1 60); do
    if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
        echo "Qdrant ready after ${i}s"
        break
    fi
    sleep 1
done

# ---------------------------------------------------------------------------
# 4. Apply schema migrations
# ---------------------------------------------------------------------------
echo "--- Applying database migrations ---"
if [ -f "scripts/setup/migrate.sh" ]; then
    bash scripts/setup/migrate.sh || {
        echo "ERROR: migrations failed"
        exit 1
    }
fi

# ---------------------------------------------------------------------------
# 5. Install test dependencies (into current Python env)
# ---------------------------------------------------------------------------
echo "--- Installing test dependencies ---"
pip install --quiet --upgrade pip
pip install --quiet \
    -r services/knowledge-base/requirements/base.txt \
    -r services/knowledge-base/requirements/api.txt \
    -r services/knowledge-base/requirements/storage.txt \
    -r services/knowledge-base/requirements/ai.txt \
    -r services/knowledge-base/requirements/processing.txt \
    -r services/knowledge-base/requirements/graph.txt \
    -r services/knowledge-base/requirements/test.txt

# ---------------------------------------------------------------------------
# 6. Run tests
# ---------------------------------------------------------------------------
echo "--- Running knowledge-base tests ---"
export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB REDIS_PASSWORD
export PYTHONPATH="$PROJECT_ROOT"

TEST_ARGS=("${@:-tests/knowledge_base/}")

python -m pytest "${TEST_ARGS[@]}" \
    -v \
    --tb=short \
    --timeout=120 \
    -x \
    2>&1

echo "--- Knowledge Base DB tests completed ---"
