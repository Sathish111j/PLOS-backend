# Kafka Infrastructure

This folder contains Kafka bootstrap scripts.

## Files

- init-topics.sh
  Creates required Kafka topics after the broker is healthy.

## Usage

Run from the kafka container when needed:

  docker-compose exec -T kafka bash /infrastructure/kafka/init-topics.sh
