#!/bin/bash
# ============================================================================
# PLOS Kafka Topic Initialization Script
# Creates all necessary Kafka topics with appropriate partitions and replication
# ============================================================================
#
# Topics are organized by domain and follow dot notation (standard Kafka practice).
# With generalized extraction, the journal parser publishes complete extraction
# results to a single topic which downstream services consume.
#
# ============================================================================

set -e

echo "============================================"
echo "PLOS Kafka Topic Initialization"
echo "============================================"

echo "Waiting for Kafka to be ready..."
sleep 10

# Wait for Kafka to be fully ready
until kafka-broker-api-versions --bootstrap-server kafka:9092 > /dev/null 2>&1; do
  echo "Kafka not ready yet, waiting..."
  sleep 2
done

echo "Kafka is ready. Creating topics..."

# ============================================================================
# JOURNAL PROCESSING TOPICS (Active)
# ============================================================================

# Input: Raw journal entries from API
echo "Creating plos.journal.entries..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.entries \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

# Output: Parsed entries (legacy compatibility)
echo "Creating plos.journal.parsed..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.parsed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

# Output: Complete extraction with all data types
echo "Creating plos.journal.extraction.complete..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.extraction.complete \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --config cleanup.policy=delete

# ============================================================================
# CONTEXT AND STATE TOPICS (Active)
# ============================================================================

# Context updates from various services
echo "Creating plos.context.updates..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.context.updates \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000 \
  --config cleanup.policy=delete

# ============================================================================
# KNOWLEDGE SYSTEM TOPICS (Active)
# ============================================================================

# Knowledge indexing requests
echo "Creating plos.knowledge.index..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.knowledge.index \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000 \
  --config cleanup.policy=delete

# ============================================================================
# GENERAL EVENT STREAM (Active)
# ============================================================================

# Unified event stream for analytics and logging
echo "Creating plos.event.stream..."
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.event.stream \
  --partitions 6 \
  --replication-factor 1 \
  --config retention.ms=2592000000 \
  --config cleanup.policy=delete

echo ""
echo "============================================"
echo "Kafka topics created successfully!"
echo "============================================"
echo ""

# List all topics
echo "Current topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list
