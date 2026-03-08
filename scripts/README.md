# PLOS Backend Scripts

All scripts require Docker and Docker Compose (plugin >= 2.x).
Make scripts executable once after cloning:

```bash
chmod +x scripts/**/*.sh
```

---

## Folder Layout

```
scripts/
  lint/       Code quality checks
  setup/      First-time setup and database management
  start/      Start the full stack
  stop/       Stop and cleanup
  verify/     Infrastructure health checks and smoke tests
  dev-tools/  Developer-only debugging scripts (not for CI/production)
```

---

## Script Reference

### lint/

| Script | Purpose |
|--------|---------|
| `lint/lint.sh` | Run all linters (black, ruff, isort). Use `--fix` to auto-correct. |

```bash
./scripts/lint/lint.sh           # check mode
./scripts/lint/lint.sh --fix     # auto-fix formatting
./scripts/lint/lint.sh --install # install linting dependencies first
```

---

### setup/

| Script | Purpose |
|--------|---------|
| `setup/setup.sh` | Prerequisites check and .env creation. Run once before first start. |
| `setup/migrate.sh` | Incremental SQL migration runner. Safe to run on existing databases. |
| `setup/seed.sh` | Seed the database with initial data from `infrastructure/database/seed.sql`. |

```bash
./scripts/setup/setup.sh    # first-time setup
./scripts/setup/migrate.sh  # apply pending migrations
./scripts/setup/seed.sh     # seed initial data
```

---

### start/

| Script | Purpose |
|--------|---------|
| `start/dev.sh` | Full stack startup: infra -> wait for DB -> migrate -> seed -> app services -> health checks |

```bash
./scripts/start/dev.sh
```

The script outputs each service health endpoint and exits non-zero if any service
failed to become healthy.

---

### stop/

| Script | Purpose |
|--------|---------|
| `stop/stop.sh` | Graceful shutdown. Use `--clean` to also delete all volumes. |

```bash
./scripts/stop/stop.sh           # stop, keep data volumes
./scripts/stop/stop.sh --clean   # stop and delete all data (fresh start)
```

---

### verify/

| Script | Purpose |
|--------|---------|
| `verify/verify-infrastructure.sh` | 9-test infrastructure check (DB, Redis, Qdrant, Kafka, KB service). Profile-gated services (Studio, Prometheus, Grafana) are reported as skips, not errors. |
| `verify/smoke-e2e.sh` | End-to-end API smoke test through the gateway (auth, journal, reports). |

```bash
./scripts/verify/verify-infrastructure.sh   # infrastructure health
./scripts/verify/smoke-e2e.sh               # E2E API smoke test
```

Exit codes: 0 = pass or pass-with-warnings, 1 = hard failure.

Optional monitoring services must be started explicitly:
```bash
docker compose --profile monitoring up -d   # Prometheus + Grafana
docker compose --profile studio up -d       # Supabase Studio
docker compose --profile ui up -d           # Kafka UI, etc.
```

---

### dev-tools/

These scripts are for local debugging only. They require all services to be running.
Do NOT use them in CI.

| Script | Purpose |
|--------|---------|
| `dev-tools/deep_store_verify.py` | Verify consistency across PostgreSQL, Qdrant, Meilisearch, and Redis for the knowledge base. |
| `dev-tools/manual_deep_test.py` | Full knowledge base feature test with DB and vector DB validation at each step. |

```bash
python3 scripts/dev-tools/deep_store_verify.py
python3 scripts/dev-tools/manual_deep_test.py
```

---

## Typical Workflows

### First-time setup

```bash
./scripts/setup/setup.sh    # creates .env, checks docker
# edit .env -- set GEMINI_API_KEY
./scripts/start/dev.sh      # starts everything and runs migrations
```

### Daily startup

```bash
./scripts/start/dev.sh
```

### Verify everything is healthy

```bash
./scripts/verify/verify-infrastructure.sh
./scripts/verify/smoke-e2e.sh
```

### Fresh start (wipe all data)

```bash
./scripts/stop/stop.sh --clean
./scripts/start/dev.sh
```

### Code quality check before committing

```bash
./scripts/lint/lint.sh
# or to auto-fix:
./scripts/lint/lint.sh --fix
```

### Apply new database migrations

```bash
./scripts/setup/migrate.sh
```

### Start optional monitoring stack

```bash
docker compose --profile monitoring up -d
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3333
```

---

## Access Points

| Service | URL |
|---------|-----|
| API Gateway | http://localhost:8000 |
| Context Broker | http://localhost:8001 |
| Journal Parser | http://localhost:8002 |
| Knowledge Base | http://localhost:8003 |
| Qdrant | http://localhost:6333 |
| Meilisearch | http://localhost:7700 |
| MinIO Console | http://localhost:9001 |
| Grafana | http://localhost:3333 (--profile monitoring) |
| Kafka UI | http://localhost:18080 (--profile ui) |
| Supabase Studio | http://localhost:3000 (--profile studio) |

---

## Troubleshooting

**Service health check fails on startup**

```bash
docker compose logs <service-name>
docker compose restart <service-name>
```

**Port already in use**

```bash
lsof -i :<port>   # find the conflicting process
```

**Database migration issues**

```bash
docker exec plos-supabase-db psql -U postgres -d plos \
  -c "SELECT filename, applied_at FROM schema_migrations ORDER BY applied_at;"
```

**Fresh start needed**

```bash
./scripts/stop/stop.sh --clean
./scripts/start/dev.sh
```

**Run pytest unit / integration tests**

```bash
pytest services/ shared/ tests/ -v
```

**Deep data store debug**

```bash
python3 scripts/dev-tools/deep_store_verify.py
```

---

*Last updated: March 2026*
