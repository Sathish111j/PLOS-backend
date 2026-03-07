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
  Versioned SQL migrations applied by the init scripts:
  - `001_journal_timeseries.sql` - Initial journal timeseries table
  - `002_knowledge_base_document_management.sql` - Document management tables
  - `003_knowledge_base_chunking.sql` - Document chunking tables
  - `004_knowledge_base_deduplication_integrity.sql` - Deduplication integrity
  - `005_knowledge_base_chunk_deduplication.sql` - Chunk deduplication
  - `006_knowledge_base_vector_search_entities.sql` - Vector search and entities
  - `007_bucket_hierarchy_and_ai_routing.sql` - Bucket organization
  - `008_chat_sessions.sql` - Chat session management

## Notes

These scripts run automatically via docker-compose. If you change schema or seed data, keep migration ordering and idempotency in mind.

Current first-time initialization order (when DB volume is empty):

1. `00-supabase-admin.sh`
2. `init.sql`
3. `zz-03-run-app-migrations.sh` (executes files in `migrations/`)
4. `seed.sql`

For regular startups after initialization, mounted init scripts are not re-run by PostgreSQL entrypoint.
