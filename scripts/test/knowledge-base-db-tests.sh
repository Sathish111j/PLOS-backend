#!/bin/bash
set -e

echo "Running Knowledge Base migration tests in Docker container..."
docker compose --profile test run --rm knowledge-base-test
