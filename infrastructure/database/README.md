# Database Infrastructure

This folder contains PostgreSQL initialization scripts and application migrations.

## Files

- init.sql
  Base database setup executed on container initialization.
- seed.sql
  Optional seed data for local development.
- 00-supabase-admin.sh
  Supabase admin initialization script.
- zz-03-run-app-migrations.sh
  Runs app-specific migrations on startup.

## Migrations

- migrations/
  Versioned SQL migrations applied by the init scripts.
  - `004_journal_timeseries.sql` adds Timescale hypertable `journal_timeseries` for analytics workloads.

## Notes

These scripts run automatically via docker-compose. If you change schema or seed data, keep migration ordering and idempotency in mind.

Current first-time initialization order (when DB volume is empty):

1. `00-supabase-admin.sh`
2. `init.sql`
3. `zz-03-run-app-migrations.sh` (executes files in `migrations/`)
4. `seed.sql`

For regular startups after initialization, mounted init scripts are not re-run by PostgreSQL entrypoint.
