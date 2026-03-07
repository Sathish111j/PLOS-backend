# Kafka Infrastructure

This folder contains Kafka bootstrap scripts.

## Files

- init-topics.sh
  Creates required Kafka topics after the broker is healthy.

## Usage

Run from the kafka container when needed:

  docker compose exec -T kafka bash /infrastructure/kafka/init-topics.sh

## Topics Created

The init script creates 6 Kafka topics:

| Topic | Partitions | Retention | Purpose |
|-------|-----------|-----------|---------|
| `plos.journal.entries` | 3 | 7 days | Raw journal entries from API |
| `plos.journal.parsed` | 3 | 7 days | Parsed entries (legacy compatibility) |
| `plos.journal.extraction.complete` | 3 | 7 days | Complete extraction with all data |
| `plos.context.updates` | 3 | 1 day | Context updates from services |
| `plos.knowledge.index` | 3 | 1 day | Knowledge indexing requests |
| `plos.event.stream` | 6 | 30 days | Unified event stream for analytics |
