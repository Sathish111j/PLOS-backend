# PLOS - Personal Life Management System

A personal life management backend that converts unstructured journal entries, notes, links, PDFs, and media into structured, queryable, and semantically searchable data using AI.

Designed as a modular, event-driven system focused on correctness, traceability, and long-term personal data integrity.



## Core Capabilities

- Parse unstructured journal entries using LLMs (Google Gemini)
- Normalize activities, health, work, and life events into consistent data models
- Maintain evolving user context - aggregate state from dispersed life data
- Store and search personal knowledge - notes, links, PDFs, images with semantic indexing
- Semantic search via vector embeddings - find information by meaning, not keywords
- Time-series analytics on life metrics - patterns, trends, correlations
- Confidence-aware inference - explicit data vs inferred vs missing, with quality scores
- Event-driven processing - asynchronous, decoupled data flow with Kafka

---



## Architecture

PLOS follows a layered, event-driven architecture:

```
┌─────────────────────────────────────────────────────────┐
│               CLIENT LAYER                              │
│          (Frontend Applications)                        │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │       EDGE LAYER               │
         │   API Gateway (Kong)           │
         │   Authentication & Routing     │
         └───────────────┬────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼──┐         ┌───────▼──────┐    ┌───────▼─────┐
│ CTX  │         │   PARSING     │    │  KNOWLEDGE  │
│      │         │               │    │             │
│ mgmt │         │ extraction    │    │ indexing    │
└───┬──┘         │ normalization │    │ search      │
    │            └───────┬──────┘    └───────┬─────┘
    │                    │                    │
    └────────────────────┼────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │    ASYNC LAYER                 │
         │  Kafka Event Bus               │
         │  - Topic-based pub/sub         │
         │  - Event sourcing              │
         │  - Audit trail                 │
         └───────────────┬────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
┌───▼──────┐    ┌────────▼─────┐  ┌──────────▼────┐
│PostgreSQL │    │ Redis Cache  │  │ Qdrant Vectors│
│+ Timeline │    │              │  │                │
│ DB        │    │ Hot data     │  │ Semantic index │
│           │    │ Sessions     │  │                │
└───────────┘    └──────────────┘  └─────────────────┘
```

**Key Layers:**

1. **Edge Layer**: API Gateway (Kong) handles routing, auth, rate limiting
2. **Processing Layer**: Domain-specific services for parsing, context, knowledge (implementation details evolve)
3. **Async Layer**: Kafka for event streaming and service decoupling
4. **Storage Layer**: Polyglot persistence - OLTP, cache, vectors

---

## Technology Stack

**Runtime & API**
- Python 3.11+
- FastAPI (async, type-safe)
- Pydantic (data validation)

**Data Processing**
- Google Gemini API (LLM-based extraction)
- Kafka (async event streaming)

**Data Storage**
- PostgreSQL (relational data)
- TimescaleDB (time-series data)
- Redis (hot cache, sessions)
- Qdrant (vector embeddings)

**Observability**
- Prometheus (metrics)
- Grafana (dashboards)
- Structured logging

**Deployment**
- Docker & Docker Compose
- Kong API Gateway

---

## Infrastructure

All infrastructure runs in Docker. Compose file orchestrates:

**Databases**
- PostgreSQL (port 5432) - transactional data
- TimescaleDB (hypertables) - time-series
- Redis (port 6379) - caching

**Message Bus**
- Kafka (port 9092) - event streaming
- Kafka topics for domain events

**Search**
- Qdrant (port 6333) - vector database

**Monitoring**
- Prometheus (port 9090) - metrics scraping
- Grafana (port 3333) - visualization
- Kafka UI (port 8080) - topic inspection

**API Gateway**
- Kong (port 8000) - request routing

---

## Getting Started

### Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)
- Python 3.11+ (for local dev)
- Google Gemini API key

### Setup

```bash
# Clone
git clone https://github.com/Sathish111j/LifeOSbackend.git
cd LifeOSbackend

# Configure
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and passwords
```

### Start Infrastructure

```powershell
# Windows
./scripts/start-infrastructure.ps1

# Linux/Mac
docker-compose up -d postgres redis kafka qdrant
```

Wait for services to be healthy (use `docker ps`)

### Verify

```powershell
# Windows
./scripts/verify-infrastructure.ps1

# Linux/Mac
./scripts/verify.sh
```

Expected checks: PostgreSQL, Redis, Kafka, Qdrant

### Access Points

- Kafka UI: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3333 (admin/admin)
- Qdrant: http://localhost:6333/dashboard

---

## Configuration

### Environment Variables

```env
# Google Gemini API
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=plos
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=redis-password

# Kafka
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC_PREFIX=plos

# Application
LOG_LEVEL=INFO
DEBUG=false
```

### Data Models

Key data structures stored across layers:

**User Context** - Aggregated state in PostgreSQL
- User profile and preferences
- Activity patterns
- Health metrics
- Relationship network

**Parsed Entries** - Structured extraction results in PostgreSQL
- Original content + metadata
- Extracted fields with confidence scores
- Activity classifications
- Temporal and contextual tags

**Time Series** - Life metrics in TimescaleDB
- Mood, energy, stress, sleep quality
- Activity duration and intensity
- Health measurements
- Aggregated patterns

**Knowledge** - Embeddings in Qdrant
- Semantic vectors for journal entries
- Indexed notes, links, PDFs
- Fast semantic search

**Events** - Transient state in Kafka
- User actions (created entry, updated context)
- Parsed data (extraction complete, confidence changed)
- System events (cache invalidation, notifications)

---

## Development

### Local Setup

```bash
# Create venv
python -m venv venv

# Activate
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set credentials
export GEMINI_API_KEY=your-key
export POSTGRES_PASSWORD=your-password
```

### Code Quality

```bash
# Format
black .
isort .

# Lint
./scripts/lint.ps1

# Type check
mypy services/

# Test
pytest tests/
```


## Monitoring

**Prometheus** (http://localhost:9090)
- Scrapes all services every 15 seconds
- Stores metrics locally (15 day retention)
- Query language: PromQL

**Grafana** (http://localhost:3333)
- Dashboards for service health
- Log aggregation
- Alerting configuration

**Kafka UI** (http://localhost:8080)
- Visual topic browsing
- Message inspection
- Consumer group monitoring

**Logs**
- JSON structured logs
- Consistent format across services
- Filterable by service, level, timestamp

### Key Metrics

- Service uptime and response latency
- Kafka message lag
- Database connection pool usage
- Cache hit/miss ratio
- LLM API call duration
- Extraction confidence distribution

---

## Contributing

### Code Standards

- PEP 8 + Black formatting
- Type hints on all functions
- Docstrings for classes and public methods
- Tests for business logic

### Before Submitting PR

```bash
# Format code
black . && isort .

# Lint and type check
./scripts/lint.ps1

# Run tests
pytest tests/ -v

# Check for secrets
git diff --staged | grep -i "password\|key\|token"
```

### Commit Messages

- `feat: add new feature`
- `fix: resolve issue`
- `docs: update documentation`
- `refactor: restructure code`
- `test: add or update tests`


## Troubleshooting

### Infrastructure Won't Start

```bash
# Check Docker
docker-compose config

# View logs
docker-compose logs postgres

# Rebuild
docker-compose down -v
docker-compose up
```

### Kafka Issues

```bash
# Check broker is reachable
docker exec kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092

# View topics
docker exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# Check consumer lag
docker exec kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group plos --describe
```

### Database Issues

```bash
# Connect directly
psql -h localhost -U postgres -d plos

# Check TimescaleDB
SELECT * FROM timescaledb_information.hypertables;

# Reset (DESTRUCTIVE)
./scripts/clean.sh
```

### High Memory Usage

- Check Redis key size: `redis-cli --bigkeys`
- Check Kafka retention: `docker-compose logs kafka`
- Reduce Prometheus retention: Edit `prometheus.yml`

---

## Performance Tuning

**PostgreSQL**
- Index on user_id, entry_date for queries
- Vacuum and analyze periodically
- Connection pooling via PgBouncer (future)

**Redis**
- Set appropriate TTL on cached values
- Monitor memory with `INFO memory`
- Use hash structures for related data

**Kafka**
- Tune consumer batch size based on message volume
- Monitor partition lag
- Archive old topics to reduce broker disk usage

**Qdrant**
- Batch vector operations
- Use appropriate similarity metric
- Monitor index size

---



## Related Technologies

- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Google Gemini API](https://ai.google.dev/) - LLM for extraction
- [Apache Kafka](https://kafka.apache.org/) - Event streaming
- [Qdrant](https://qdrant.tech/) - Vector search
- [TimescaleDB](https://www.timescale.com/) - Time-series extension
- [Kong](https://konghq.com/) - API gateway
- [PostgreSQL](https://www.postgresql.org/) - OLTP database
- [Redis](https://redis.io/) - Caching
- [Prometheus](https://prometheus.io/) - Metrics
- [Grafana](https://grafana.com/) - Dashboards

---

**Last Updated:** December 29, 2025  
**Repository:** https://github.com/Sathish111j/LifeOSbackend
