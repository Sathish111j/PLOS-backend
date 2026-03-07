# Infrastructure

This folder contains infrastructure configuration and bootstrap assets used by Docker Compose.

## Layout

- database/   PostgreSQL initialization scripts and app migrations
  - migrations/  Database schema migrations (8 files: 001-008)
- kafka/      Kafka initialization scripts (topics)
- monitoring/ Prometheus configuration
- redis/      Redis configuration

Note: Qdrant, Meilisearch, and MinIO infrastructure are configured directly in docker-compose.yml without separate config files.

## Usage

These files are mounted or executed by docker compose and the service Dockerfiles. Update them alongside compose changes to keep local and production setups consistent.
