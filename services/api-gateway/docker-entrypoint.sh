#!/bin/sh
# Kong initialization script

set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$KONG_PG_PASSWORD psql -h "$KONG_PG_HOST" -U "$KONG_PG_USER" -d postgres -c '\q'; do
  >&2 echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - executing Kong migrations"

# Run migrations
kong migrations bootstrap --vv

# Start Kong
exec "$@"
