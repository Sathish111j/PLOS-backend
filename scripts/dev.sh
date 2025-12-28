#!/bin/bash
# PLOS Development Environment - Linux/Mac
# For Windows, use PowerShell scripts instead

set -e

echo "=========================================="
echo "  PLOS - Development Startup"
echo "=========================================="
echo ""

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create one from .env.example"
    exit 1
fi

# Step 1: Start Infrastructure
echo "[1/2] Starting Infrastructure..."
docker-compose up -d postgres redis zookeeper kafka qdrant prometheus grafana kafka-ui

echo ""
echo "Waiting 30 seconds for infrastructure to be healthy..."
sleep 30

# Step 2: Start Services
echo ""
echo "[2/2] Starting Application Services..."
docker-compose up -d context-broker journal-parser knowledge-system api-gateway

echo ""
echo "Waiting 10 seconds for services to start..."
sleep 10

echo ""
echo "=========================================="
echo "  ✅ System Started!"
echo "=========================================="
echo ""
echo "Infrastructure:"
echo "  Kafka UI:       http://localhost:8080"
echo "  Grafana:        http://localhost:3333"
echo "  Prometheus:     http://localhost:9090"
echo ""
echo "APIs:"
echo "  API Gateway:    http://localhost:8000"
echo "  Context Broker: http://localhost:8001/health"
echo "  Journal Parser: http://localhost:8002/health"
echo "  Knowledge:      http://localhost:8003/health"
echo ""
echo "Commands:"
echo "  docker-compose logs -f              - View all logs"
echo "  docker-compose logs -f <service>    - View specific service"
echo "  docker-compose ps                   - List services"
echo "  docker-compose down                 - Stop all"
echo ""
