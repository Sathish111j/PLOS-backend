#!/bin/bash
# PLOS Database Migration Runner
# Applies pending SQL migrations incrementally.
# Tracks applied migrations in the schema_migrations table.
# Safe to run on existing databases -- skips already-applied files.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

DB_CONTAINER="${DB_CONTAINER:-plos-supabase-db}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-plos}"
MIGRATION_DIR="$(cd "$(dirname "$0")/../../infrastructure/database/migrations" && pwd)"

run_sql() {
    docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$PG_DB" "$@"
}

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  PLOS Database Migration Runner${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Wait for database
echo -e "${YELLOW}Checking database connection...${NC}"
for i in $(seq 1 30); do
    if docker exec "$DB_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
        echo -e "${GREEN}Database is ready.${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}Database did not become ready in time.${NC}"
        exit 1
    fi
    sleep 2
done

# Create schema_migrations table if it does not exist
echo -e "${YELLOW}Ensuring schema_migrations table exists...${NC}"
run_sql <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL
echo -e "${GREEN}schema_migrations table ready.${NC}"
echo ""

# Bootstrap: if schema_migrations is empty but the DB already has migration
# artifacts (e.g. from the init entrypoint), mark all known migrations as
# applied so they are not re-run.
ROW_COUNT=$(run_sql -t -A -c "SELECT count(*) FROM schema_migrations;")
if [ "${ROW_COUNT:-0}" -eq 0 ]; then
    # Check if the DB already has tables created by migrations
    HAS_TABLES=$(run_sql -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('documents','buckets','document_chunks');")
    if [ "${HAS_TABLES:-0}" -gt 0 ]; then
        echo -e "${YELLOW}Detected existing migration artifacts. Bootstrapping schema_migrations...${NC}"
        for sql_file in "$MIGRATION_DIR"/*.sql; do
            [ -f "$sql_file" ] || continue
            fname="$(basename "$sql_file")"
            run_sql -c "INSERT INTO schema_migrations (filename) VALUES ('$fname') ON CONFLICT DO NOTHING;"
        done
        echo -e "${GREEN}Bootstrapped with existing migrations.${NC}"
        echo ""
    fi
fi

# Enumerate pending migrations
APPLIED=$(run_sql -t -A -c "SELECT filename FROM schema_migrations ORDER BY filename;")

PENDING=0
APPLIED_COUNT=0

for sql_file in "$MIGRATION_DIR"/*.sql; do
    [ -f "$sql_file" ] || continue
    fname="$(basename "$sql_file")"

    if echo "$APPLIED" | grep -qxF "$fname"; then
        APPLIED_COUNT=$((APPLIED_COUNT + 1))
        continue
    fi

    PENDING=$((PENDING + 1))

    echo -e "${YELLOW}Applying: $fname${NC}"
    run_sql < "$sql_file"
    run_sql -c "INSERT INTO schema_migrations (filename) VALUES ('$fname');"
    echo -e "${GREEN}  Applied.${NC}"
done

echo ""
if [ "$PENDING" -eq 0 ]; then
    echo -e "${GREEN}No pending migrations. $APPLIED_COUNT already applied.${NC}"
else
    echo -e "${GREEN}Applied $PENDING migration(s). Total applied: $((APPLIED_COUNT + PENDING)).${NC}"
fi
