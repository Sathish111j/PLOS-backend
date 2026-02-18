# Infrastructure

This folder contains infrastructure configuration and bootstrap assets used by Docker Compose.

## Layout

- database/   PostgreSQL initialization scripts and app migrations
- kafka/      Kafka initialization scripts (topics)
- monitoring/ Prometheus configuration
- redis/      Redis configuration

## Usage

These files are mounted or executed by docker-compose and the service Dockerfiles. Update them alongside compose changes to keep local and production setups consistent.
