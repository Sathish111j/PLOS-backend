# PLOS - Quick Start Guide

Get PLOS running in **5 minutes**.

---

## Prerequisites

- Docker Desktop installed  
- Git installed  
- Google Gemini API key (free at [Google AI Studio](https://aistudio.google.com/))

---

## Installation (3 Steps)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd PLOS-backend
cp .env.example .env
```

### 2. Add Your API Key

Edit `.env` and add your Gemini API key:

```env
GEMINI_API_KEYS=your-key-here
```

### 3. Start Everything

```bash
# Make scripts executable (Linux/Mac)
chmod +x scripts/start/*.sh scripts/stop/*.sh scripts/verify/*.sh scripts/setup/*.sh scripts/test/*.sh

# Run setup (first time only)
./scripts/setup/setup.sh

# Start all services
./scripts/start/dev.sh
```

---

## Verify It's Working

Open in your browser:

| Service | URL | Purpose |
|---------|-----|---------|
| **API Gateway** | http://localhost:8000/docs | Main API documentation |
| **Journal Parser** | http://localhost:8002/docs | Journal processing API |
| **Context Broker** | http://localhost:8001/docs | User context management |
| **Knowledge Base** | http://localhost:8003/docs | Document search and ingestion |
| **Supabase Studio** | http://localhost:3000 | Database management |
| **Metabase** | http://localhost:3001 | Data visualization |
| **Qdrant** | http://localhost:6333 | Vector database |
| **Meilisearch** | http://localhost:7700 | Full-text search |
| **MinIO Console** | http://localhost:9001 | Object storage |
| **Kafka UI** | http://localhost:18080 | Message queue monitoring |
| **Redis Commander** | http://localhost:8081 | Cache management |
| **Prometheus** | http://localhost:9090 | Metrics collection |
| **Grafana** | http://localhost:3333 | Dashboard visualization |

Or test with curl:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

---

## What's Running?

```bash
docker compose ps
```

You should see:
- PostgreSQL (database)
- Redis (cache)
- Kafka (message queue)
- API Gateway
- Context Broker
- Knowledge Base
- Qdrant
- Monitoring tools

---

## Docker Profiles

Some services are behind Docker Compose profiles and won't start by default. To access them:

| Profile | Services | Command |
| ------- | -------- | ------- |
| `studio` | Supabase Studio, Supabase Meta | `docker compose --profile studio up -d` |
| `ui` | Kafka UI, Redis Commander | `docker compose --profile ui up -d` |
| `monitoring` | Prometheus, Grafana | `docker compose --profile monitoring up -d` |
| `bi` | Metabase | `docker compose --profile bi up -d` |

Example: `docker compose --profile monitoring --profile ui up -d`

---

## Quick Commands

```bash
# View logs
docker compose logs -f

# Stop everything
docker compose down

# Start again
./scripts/start/dev.sh

# Clean everything
./scripts/stop/clean.sh
```

---

## Next Steps

1. **Setup complete!** All services are running.
2. **Explore the APIs** using the documentation links above.
3. **Add journal entries** via the Journal Parser API.
4. **Upload documents** to the Knowledge Base.
5. **View analytics** in Metabase and Grafana.

For more details, see:
- [API Reference](../docs/API_REFERENCE.md) - Complete API documentation
- [Architecture Standards](../docs/ARCHITECTURE_STANDARDS.md)
- [Journal Processing Flow](../docs/JOURNAL_PROCESSING_FLOW.md)
- [Knowledge Base Features](../docs/KB_FEATURES_AND_FLOWS.md)

---

## Troubleshooting

**Services won't start?**
```bash
docker compose logs
```

**Port already in use?**

Edit `.env` and change the port:
```env
API_GATEWAY_PORT=8080  # Instead of 8000
```

**Need to reset everything?**
```bash
./scripts/stop/clean.sh
./scripts/setup/setup.sh
```

---

**Happy building!**

