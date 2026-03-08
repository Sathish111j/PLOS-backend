#!/bin/bash
set -e

# PLOS Database Seeding Script
# Seeds the database with initial data after schema is initialized.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DB_CONTAINER="plos-supabase-db"
SEED_FILE="$PROJECT_ROOT/infrastructure/database/seed.sql"

echo ""
echo "========================================"
echo "  PLOS Database Seeding"
echo "========================================"
echo ""

# Check if database is ready
echo "Checking database connection..."
PG_READY=$(docker exec "$DB_CONTAINER" pg_isready -U postgres 2>&1 || true)
if echo "$PG_READY" | grep -q "accepting connections"; then
    echo "Database is ready"
else
    echo "Database not ready!"
    exit 1
fi

# Check seed file exists
if [ ! -f "$SEED_FILE" ]; then
    echo "Seed file not found at $SEED_FILE"
    exit 1
fi

# Seed the database
echo ""
echo "Seeding database..."
if docker exec -i "$DB_CONTAINER" psql -U postgres -d plos < "$SEED_FILE"; then
    echo "Database seeded successfully!"
else
    echo "Failed to seed database!"
    exit 1
fi

echo ""
echo "Database seeding complete!"
