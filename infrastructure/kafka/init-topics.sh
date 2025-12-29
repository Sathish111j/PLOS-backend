#!/bin/bash
# PLOS Kafka Topic Initialization Script
# Creates all necessary Kafka topics with appropriate partitions and replication

set -e

echo "Waiting for Kafka to be ready..."
sleep 10

echo "Creating Kafka topics..."

# Journal & Parsing Topics
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic journal_entries \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic journal_entries_raw \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic parsed_entries \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Data Extraction Topics
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic mood_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic health_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic nutrition_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic exercise_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic work_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic habit_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Context & State Updates
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic context_updates \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# Relationship Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic relationship_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Health Alerts
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic health_alerts \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Predictions
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic predictions \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# Task & Goal Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic task_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic goal_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Calendar Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic calendar_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Notification Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic notification_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Knowledge Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic knowledge_events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# AI Agent Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic insight_requests \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic scheduling_requests \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# Event Stream (General)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic event_stream \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

echo "✓ All Kafka topics created successfully!"
echo ""
echo "Listing all topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list

exit 0
