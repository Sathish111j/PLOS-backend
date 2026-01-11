set -eu

# Ensure supabase_admin can authenticate during the Supabase image's own migrations.
# The image's /docker-entrypoint-initdb.d/migrate.sh connects as supabase_admin
# using the POSTGRES_PASSWORD value, so we pre-set that password here.

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "00-supabase-admin.sh: POSTGRES_PASSWORD is empty; skipping supabase_admin password setup" >&2
  return 0 2>/dev/null || exit 0
fi

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql -v ON_ERROR_STOP=1 --no-password --no-psqlrc \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-postgres}" \
  <<'EOSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_admin') THEN
    CREATE ROLE supabase_admin LOGIN SUPERUSER;
  END IF;
END $$;
EOSQL

psql -v ON_ERROR_STOP=1 --no-password --no-psqlrc \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-postgres}" \
  --set=admin_pass="${POSTGRES_PASSWORD}" \
  <<'EOSQL'
ALTER ROLE supabase_admin WITH LOGIN SUPERUSER PASSWORD :'admin_pass';
EOSQL

# Some Supabase hooks/extensions may need this capability.
psql -v ON_ERROR_STOP=1 --no-password --no-psqlrc \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-postgres}" \
  -c "GRANT pg_read_server_files TO supabase_admin;" || true
