# PLOS Backend

Personal Life Operating System — an AI-powered backend that parses natural-language journal entries into structured life data, stores it across a multi-store persistence layer, and exposes it through a microservice API.

[![CI](https://github.com/Sathish111j/PLOS-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/Sathish111j/PLOS-backend/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![License](https://img.shields.io/badge/License-GPL--3.0-lightgrey)

---

## Architecture

```
                        ┌─────────────────────┐
  Client Request  ──▶   │    Kong API Gateway  │  :8000
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼──────────────────────┐
              │                    │                       │
              ▼                    ▼                       ▼
   ┌──────────────────┐  ┌─────────────────┐  ┌────────────────────┐
   │  Context Broker  │  │ Journal Parser  │  │  Knowledge Base    │
   │     :8001        │  │     :8002       │  │     :8003          │
   │                  │  │                 │  │                    │
   │ User state       │  │ Gemini AI       │  │ Document ingestion │
   │ Context windows  │  │ extraction      │  │ Hybrid search      │
   │ Session cache    │  │ Auth + JWT      │  │ Graph relations    │
   └──────┬───────────┘  └─────────┬───────┘  └─────────┬──────────┘
          │                        │                     │
          └───────────────┬────────┘─────────────────────┘
                          │
              ┌───────────▼────────────────────────┐
              │           Shared Infrastructure     │
              │                                     │
              │  PostgreSQL  Redis  Kafka            │
              │  Qdrant  Meilisearch  MinIO          │
              └─────────────────────────────────────┘
```

### Services

| Service | Port | Responsibility |
|---|---|---|
| `api-gateway` | 8000 | Kong DB-less reverse proxy, rate limiting, routing |
| `context-broker` | 8001 | User context state, Redis caching, context window management |
| `journal-parser` | 8002 | Journal ingestion, Gemini AI extraction, reporting endpoints |
| `knowledge-base` | 8003 | Document upload/ingest, hybrid vector+keyword search, graph relations |

### Infrastructure

| Component | Image | Purpose |
|---|---|---|
| PostgreSQL | `supabase/postgres:15.8.1.060` | Primary data store |
| Redis | `redis:7-alpine` | Cache, session store |
| Qdrant | `qdrant/qdrant:v1.12.0` | Vector embeddings (768-dim) |
| Meilisearch | `getmeili/meilisearch:v1.11` | Typo-tolerant full-text search |
| MinIO | `minio/minio` | Object storage for raw documents |
| Kafka + Zookeeper | `confluentinc/cp-kafka:7.5.0` | Async event streaming |

---

## Prerequisites

- Docker Engine >= 24 with Compose plugin >= 2.x
- 8 GB RAM available to Docker
- A [Google Gemini API key](https://aistudio.google.com/)

---

## Quick Start

```bash
git clone https://github.com/Sathish111j/PLOS-backend.git
cd PLOS-backend

# First-time setup: checks prerequisites, creates .env
./scripts/setup/setup.sh

# Edit .env and set GEMINI_API_KEY (required)
# Then start the full stack
./scripts/start/dev.sh
```

`dev.sh` handles: infrastructure startup → DB readiness wait → schema migrations → seed → application services → health checks.

Verify everything is healthy:

```bash
./scripts/verify/verify-infrastructure.sh
./scripts/verify/smoke-e2e.sh   # end-to-end API smoke test
```

---

## Environment

Copy `.env.example` to `.env`. Minimum required variables:

```env
GEMINI_API_KEY=your_key_here

# Database (defaults work for local dev)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=plos_db_secure_2025
POSTGRES_DB=plos

# Redis
REDIS_PASSWORD=plos_redis_secure_2025

# Meilisearch
MEILISEARCH_MASTER_KEY=plos_meili_secure_2025
```

---

## Optional Profiles

Core services start by default. Optional services require explicit profiles:

```bash
docker compose --profile studio up -d      # Supabase Studio UI      :3000
docker compose --profile monitoring up -d  # Prometheus + Grafana    :9090 / :3333
docker compose --profile ui up -d          # Kafka UI                :18080
docker compose --profile bi up -d          # Metabase BI             :3001
```

---

## API Endpoints

All traffic goes through the gateway at `:8000`. Services are also reachable directly.

### Journal Parser (`/`)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Obtain JWT token |
| POST | `/journal/entries` | Submit a journal entry for AI extraction |
| GET | `/journal/entries` | List journal entries |
| GET | `/journal/reports/weekly-overview` | Weekly aggregated metrics |
| GET | `/journal/reports/daily-overview` | Daily aggregated metrics |
| GET | `/health` | Service health |

### Context Broker (`/context`)

| Method | Path | Description |
|---|---|---|
| GET | `/context/health` | Service health |
| GET/POST | `/context/...` | User context state management |

### Knowledge Base (`/kb`)

| Method | Path | Description |
|---|---|---|
| POST | `/kb/upload` | Upload a document (multipart) |
| POST | `/kb/ingest` | Ingest document URL |
| GET | `/kb/documents` | List all documents |
| GET | `/kb/buckets` | List buckets |
| POST | `/kb/buckets` | Create a bucket |
| GET | `/kb/search` | Hybrid semantic + keyword search |
| GET | `/kb/health` | Service health |

Interactive API docs available at each service's `/docs` path when running.

---

## Database Migrations

Migrations are tracked in `infrastructure/database/migrations/` and applied incrementally via `schema_migrations` table.

```bash
# Apply pending migrations
./scripts/setup/migrate.sh

# Seed initial data
./scripts/setup/seed.sh
```

The migration runner is idempotent — safe to run against an existing database.

---

## Repository Layout

```
PLOS-backend/
├── services/
│   ├── api-gateway/         Kong configuration (kong.yml, kong.conf)
│   ├── context-broker/      FastAPI service + Dockerfile
│   ├── journal-parser/      FastAPI service + Dockerfile
│   └── knowledge-base/      FastAPI service + Dockerfile + split requirements/
├── shared/
│   ├── auth/                JWT validation, user models, auth middleware
│   ├── gemini/              Resilient Gemini client with key rotation
│   ├── kafka/               Producer abstraction, topic definitions
│   ├── models/              Shared Pydantic models
│   └── utils/               Config, logging, metrics helpers
├── infrastructure/
│   ├── database/            init.sql, migrations/, seed.sql
│   ├── kafka/               init-topics.sh
│   ├── monitoring/          prometheus.yml, alerts.yml, Grafana provisioning
│   └── redis/               redis.conf
├── scripts/
│   ├── lint/lint.sh
│   ├── setup/{setup,migrate,seed}.sh
│   ├── start/dev.sh
│   ├── stop/stop.sh
│   ├── verify/{verify-infrastructure,smoke-e2e}.sh
│   └── dev-tools/           Local debugging scripts (not for CI)
├── tests/                   pytest integration and E2E tests
├── docs/                    Architecture, API reference, setup guides
├── docker-compose.yml
├── docker-compose.dev.yml   Volume mounts for hot reload
└── pyproject.toml           Linter config (black, ruff, isort)
```

---

## Development

### Linting

```bash
./scripts/lint/lint.sh          # check
./scripts/lint/lint.sh --fix    # auto-fix
```

Runs black, ruff, and isort against `services/` and `shared/`.

### Tests

```bash
pytest services/ shared/ tests/ -v
```

### Hot Reload (dev override)

`docker-compose.dev.yml` mounts local source into containers. Services restart on code change:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Stopping

```bash
./scripts/stop/stop.sh            # stop, keep volumes
./scripts/stop/stop.sh --clean    # stop and delete all data
```

---

## Documentation

| Doc | Contents |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Step-by-step local setup |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Full API reference for all services |
| [docs/ARCHITECTURE_STANDARDS.md](docs/ARCHITECTURE_STANDARDS.md) | Service design conventions |
| [docs/JOURNAL_PROCESSING_FLOW.md](docs/JOURNAL_PROCESSING_FLOW.md) | Journal → AI extraction → storage pipeline |
| [docs/KB_FEATURES_AND_FLOWS.md](docs/KB_FEATURES_AND_FLOWS.md) | Knowledge base ingestion and search |
| [docs/HYBRID_SEARCH_ARCHITECTURE.md](docs/HYBRID_SEARCH_ARCHITECTURE.md) | Qdrant + Meilisearch hybrid search design |
| [shared/gemini/DOCUMENTATION.md](shared/gemini/DOCUMENTATION.md) | Gemini client configuration and key rotation |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

*License: GPL-3.0-or-later*
