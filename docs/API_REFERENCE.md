# PLOS Backend API Reference

Complete API documentation for all PLOS services.

## Service Overview

| Service | Port | Purpose | Base URL |
|---------|------|---------|----------|
| API Gateway | 8000 | Main entry point | http://localhost:8000 |
| Journal Parser | 8002 | Journal processing | http://localhost:8002 |
| Context Broker | 8001 | User context | http://localhost:8001 |
| Knowledge Base | 8003 | Document search | http://localhost:8003 |

## Authentication

All services require JWT authentication except health endpoints. Include `Authorization: Bearer <token>` header.

### Auth Endpoints

**POST /auth/register**
- Register new user
- Body: `{"email": "string", "password": "string"}`
- Returns: JWT token

**POST /auth/login**
- Login existing user
- Body: `{"email": "string", "password": "string"}`
- Returns: JWT token

**GET /auth/me**
- Get current user profile
- Returns: User info

## Journal Parser API

### Core Endpoints

**POST /journal/process**
- Process journal entry with AI extraction
- Body: `{"user_id": "uuid", "entry_text": "string", "entry_date": "date"}`
- Returns: Extraction results

**POST /journal/resolve-gap**
- Resolve single clarification gap
- Body: `{"gap_id": "uuid", "resolution": "string"}`

**POST /journal/resolve-paragraph**
- Resolve multiple gaps via paragraph
- Body: `{"user_id": "uuid", "paragraph": "string"}`

**GET /journal/pending-gaps**
- Get unresolved clarification gaps
- Query: `?user_id=uuid`

### Reporting Endpoints

All reporting endpoints support time ranges: `weekly`, `monthly`, `range`

**GET /journal/reports/overview/{period}**
- Aggregated overview metrics
- Query: `?user_id=uuid&start_date=date&end_date=date`

**GET /journal/reports/calories/{period}**
- Calorie tracking data

**GET /journal/reports/sleep/{period}**
- Sleep duration and quality

**GET /journal/reports/mood/{period}**
- Mood score trends

**GET /journal/reports/water/{period}**
- Water intake tracking

**GET /journal/reports/steps/{period}**
- Step count data

**GET /journal/reports/activity/{period}**
- Physical activity metrics

**GET /journal/reports/nutrition/{period}**
- Nutritional data

**GET /journal/reports/social/{period}**
- Social interaction metrics

**GET /journal/reports/health/{period}**
- Health symptoms and metrics

**GET /journal/reports/work/{period}**
- Work productivity metrics

## Context Broker API

**GET /context/{user_id}**
- Get complete user context
- Returns: Full context object

**POST /context/update**
- Update user context
- Body: Context update data

**GET /context/{user_id}/summary**
- Lightweight context summary

**POST /context/{user_id}/invalidate**
- Clear cached context

## Knowledge Base API

### Document Management

**POST /upload**
- Upload document for processing
- Body: Base64 encoded content
- Returns: Document ID

**GET /documents**
- List user's documents
- Query: `?bucket_id=uuid&page=1&limit=20`

### Search & Chat

**POST /search**
- Hybrid search across documents
- Body: `{"query": "string", "filters": {...}}`
- Returns: Search results with snippets

**POST /chat**
- RAG chat with streaming support
- Body: `{"message": "string", "session_id": "uuid"}`
- Returns: Streaming chat response

### Buckets & Organization

**GET /buckets**
- List user's buckets

**POST /buckets**
- Create new bucket
- Body: `{"name": "string", "description": "string"}`

**POST /buckets/{bucket_id}/move**
- Move bucket in hierarchy

### Graph & Entities

**GET /graph/entity/search**
- Search entities by name/alias
- Query: `?q=string`

**GET /graph/entity/{entity_id}**
- Get entity details with documents

**GET /graph/related/{entity_id}**
- Find related entities

**GET /graph/path**
- Shortest path between entities
- Query: `?from=entity1&to=entity2`

### Operations & Monitoring

**GET /ops/embedding-dlq/stats**
- Embedding dead letter queue statistics

**POST /ops/embedding-dlq/reprocess-unreplayable**
- Retry failed embeddings

## Environment Variables

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEYS` | Pipe-separated API keys | Required |
| `POSTGRES_PASSWORD` | Database password | Required |
| `REDIS_PASSWORD` | Redis password | Required |
| `JWT_SECRET` | JWT signing secret | Required |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_DEFAULT_MODEL` | Default Gemini model | gemini-3-flash-preview |
| `GEMINI_EMBEDDING_MODEL` | Embedding model | gemini-embedding-001 |
| `MINIO_ENABLED` | Enable object storage | true |
| `USE_GEMINI_CACHING` | Cache API responses | false |
| `LOG_LEVEL` | Logging level | INFO |

## Docker Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| `studio` | Supabase Studio, Meta | Database management |
| `ui` | Kafka UI, Redis Commander | Infrastructure monitoring |
| `monitoring` | Prometheus, Grafana | Metrics and dashboards |
| `bi` | Metabase | Business intelligence |
| `test` | Knowledge Base test suite | Testing |

Example: `docker compose --profile monitoring --profile ui up -d`

## Health Checks

All services expose health endpoints:

- `GET /health` - Basic health check
- `GET /metrics` - Prometheus metrics

## Error Responses

Standard error format:
```json
{
  "detail": "Error message",
  "error_code": "ERROR_TYPE"
}
```

Common error codes:
- `AUTHENTICATION_FAILED` - Invalid/missing token
- `VALIDATION_ERROR` - Invalid request data
- `NOT_FOUND` - Resource not found
- `RATE_LIMITED` - Too many requests
- `INTERNAL_ERROR` - Server error</content>
<parameter name="filePath">/workspaces/PLOS-backend/docs/API_REFERENCE.md