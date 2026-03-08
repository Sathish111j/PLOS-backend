#!/bin/bash
# PLOS Backend - Development Start Script (Linux/macOS)

set -euo pipefail

# -- Colors ---------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m'

# -- Resolve paths --------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATION_DIR="$PROJECT_ROOT/infrastructure/database/migrations"
SEED_FILE="$PROJECT_ROOT/infrastructure/database/seed.sql"

DB_CONTAINER="plos-supabase-db"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-plos}"

# -- Infrastructure services ----------------------------------------------
INFRA_SERVICES=(
    supabase-db
    supabase-meta
    redis
    qdrant
    meilisearch
    minio
    zookeeper
    kafka
)

# -- Core application services --------------------------------------------
CORE_SERVICES=(
    context-broker
    journal-parser
    knowledge-base
    api-gateway
)

# =========================================================================
# Helper functions
# =========================================================================

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
ok()      { echo -e "${GREEN}[ OK ]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }

# =========================================================================
# 1. Validate environment
# =========================================================================

echo ""
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}  PLOS Development Start${NC}"
echo -e "${CYAN}==========================================${NC}"
echo ""

cd "$PROJECT_ROOT"

if [[ ! -f ".env" ]]; then
    fail ".env file not found at project root."
    echo "  Copy .env.example to .env and fill in the required values."
    exit 1
fi

# Source .env so variables are available (ignore errors for lines that are
# not valid shell assignments).
set +e
# shellcheck disable=SC1091
source .env 2>/dev/null
set -e

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    warn "GEMINI_API_KEY is not set in .env -- Gemini-dependent features will not work."
fi

# =========================================================================
# 2. Start infrastructure services
# =========================================================================

info "Starting infrastructure services..."
docker compose up -d "${INFRA_SERVICES[@]}"
echo ""

# =========================================================================
# 3. Wait for database readiness
# =========================================================================

info "Waiting for database readiness..."
MAX_ATTEMPTS=60
INTERVAL=2

for (( attempt=1; attempt<=MAX_ATTEMPTS; attempt++ )); do
    if docker exec "$DB_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null; then
        ok "Database is ready (attempt $attempt)."
        break
    fi
    if (( attempt == MAX_ATTEMPTS )); then
        fail "Database did not become ready after $MAX_ATTEMPTS attempts."
        exit 1
    fi
    sleep "$INTERVAL"
done

echo ""

# =========================================================================
# 4. Apply database migrations (via migration tracker)
# =========================================================================

info "Running migration tracker..."
bash "$(dirname "$0")/../setup/migrate.sh"
ok "Migration tracker finished."

echo ""

# =========================================================================
# 5. Seed the database
# =========================================================================

if [[ ! -f "$SEED_FILE" ]]; then
    warn "Seed file not found: $SEED_FILE -- skipping seed."
else
    info "Seeding the database..."
    docker exec -i "$DB_CONTAINER" \
        psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB" < "$SEED_FILE" > /dev/null
    ok "Database seeded."
fi

echo ""

# =========================================================================
# 6. Start core application services
# =========================================================================

info "Starting core application services..."
docker compose up -d "${CORE_SERVICES[@]}"
echo ""

# =========================================================================
# 7. Wait for service health endpoints
# =========================================================================

wait_for_health() {
    local name="$1"
    local url="$2"
    local max_attempts="${3:-30}"
    local interval="${4:-2}"

    info "Waiting for $name ($url)..."
    for (( i=1; i<=max_attempts; i++ )); do
        if curl -sf "$url" > /dev/null 2>&1; then
            ok "$name is healthy."
            return 0
        fi
        sleep "$interval"
    done
    fail "$name did not become healthy after $max_attempts attempts."
    return 1
}

HEALTH_FAILURES=0

wait_for_health "Context Broker"  "http://localhost:8001/health" 45 2 || (( HEALTH_FAILURES++ )) || true
wait_for_health "Journal Parser"  "http://localhost:8002/health" 45 2 || (( HEALTH_FAILURES++ )) || true
wait_for_health "Knowledge Base"  "http://localhost:8003/health" 45 2 || (( HEALTH_FAILURES++ )) || true

echo ""

# =========================================================================
# 8. Summary
# =========================================================================

echo -e "${CYAN}==========================================${NC}"
if (( HEALTH_FAILURES == 0 )); then
    echo -e "${GREEN}  Startup complete -- all services healthy${NC}"
else
    echo -e "${YELLOW}  Startup complete -- $HEALTH_FAILURES service(s) not healthy${NC}"
fi
echo -e "${CYAN}==========================================${NC}"
echo ""
echo "  Access Points:"
echo "    API Gateway:     http://localhost:8000"
echo "    Context Broker:  http://localhost:8001"
echo "    Journal Parser:  http://localhost:8002"
echo "    Knowledge Base:  http://localhost:8003"
echo ""
echo "  Verify all services:"
echo "    ./scripts/verify/verify-infrastructure.sh"
echo ""
echo "  End-to-end smoke test:"
echo "    ./scripts/verify/smoke-e2e.sh"
echo ""
