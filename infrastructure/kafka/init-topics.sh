#!/bin/bash
# PLOS Kafka Topic Initialization Script
# Creates all necessary Kafka topics with appropriate partitions and replication
# Uses dot notation for topic naming (standard Kafka practice)
#
# With generalized extraction, we don't need separate topics for each data type
# (mood, sleep, nutrition, etc.). The JOURNAL_EXTRACTION_COMPLETE topic publishes
# the complete extraction result which downstream services can consume.

set -e

echo "Waiting for Kafka to be ready..."
sleep 10

echo "Creating Kafka topics..."

# ============================================================================
# JOURNAL PROCESSING (Core Flow)
# ============================================================================

# Input: Raw journal entries from API
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.entries \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Output: Parsed/extracted entries (legacy, kept for compatibility)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.parsed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Output: Complete extraction with all data (activities, meals, sleep, etc.)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.extraction.complete \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# ============================================================================
# STATE CHANGES (For Downstream Services)
# ============================================================================

# Relationship state changed (HARMONY -> CONFLICT, etc.)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.relationship.state.changed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Health alerts triggered (sleep debt, mood issues, etc.)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.health.alerts.triggered \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Context updated (baseline recalculated, patterns detected)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.context.updates \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# ============================================================================
# TASKS AND GOALS
# ============================================================================

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.task.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.goal.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# ============================================================================
# NOTIFICATIONS
# ============================================================================

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.notification.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# ============================================================================
# AI AGENT REQUESTS
# ============================================================================

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.insight.requests \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.scheduling.requests \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# ============================================================================
# GENERAL
# ============================================================================

# Unified event stream for analytics/logging
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.event.stream \
  --partitions 6 \
  --replication-factor 1 \
  --config retention.ms=2592000000

echo "Kafka topics created successfully!"

# List all topics
echo "Listing all topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list
