#!/bin/bash
# PLOS Kafka Topic Initialization Script
# Creates all necessary Kafka topics with appropriate partitions and replication
# Uses dot notation for topic naming (standard Kafka practice)

set -e

echo "Waiting for Kafka to be ready..."
sleep 10

echo "Creating Kafka topics..."

# Journal and Parsing Topics
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.entries \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.entries.raw \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.parsed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.journal.extraction.complete \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Data Extraction Topics
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.mood.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.health.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.nutrition.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.exercise.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.work.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.habit.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.sleep.data.extracted \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.mood.data.extracted \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Context and State Updates
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.context.updates \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# Relationship Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.relationship.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.relationship.state.changed \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Health Alerts
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.health.alerts \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.health.alerts.triggered \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Predictions
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.predictions \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.predictions.generated \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=86400000

# Task and Goal Events
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

# Calendar Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.calendar.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Notification Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.notification.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# Knowledge Events
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.knowledge.events \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# AI Agent Events
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

# Event Stream (General)
kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists \
  --topic plos.event.stream \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

echo "All Kafka topics created successfully!"
echo ""
echo "Listing all topics:"
kafka-topics.sh --bootstrap-server kafka:9092 --list

exit 0
