set -eu

# Apply project migrations without clobbering the Supabase image's built-in ones.
# This runs after the image's own /docker-entrypoint-initdb.d/migrate.sh.

export PGPASSWORD="${POSTGRES_PASSWORD:-}"

echo "zz-03-run-app-migrations.sh: applying app migrations (if any)"

for sql in /docker-entrypoint-initdb.d/app-migrations/*.sql; do
  if [ -f "$sql" ]; then
    echo "zz-03-run-app-migrations.sh: running $sql"
    psql -v ON_ERROR_STOP=1 --no-password --no-psqlrc \
      -U "${POSTGRES_USER:-postgres}" \
      -d "${POSTGRES_DB:-postgres}" \
      -f "$sql"
  fi
done
