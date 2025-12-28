#!/bin/bash
# PLOS Development Environment
# Start all services for local development

set -e

echo "=========================================="
echo "  PLOS - Starting Development Environment"
echo "=========================================="
echo ""

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Run ./scripts/setup.sh first."
    exit 1
fi

# Start all services
echo "🚀 Starting all services..."
echo ""

docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

echo ""
echo "=========================================="
echo "  ✅ All Services Started!"
echo "=========================================="
echo ""
echo "Access Points:"
echo "  Frontend:          http://localhost:3000"
echo "  API Gateway:       http://localhost:8000"
echo "  API Docs:          http://localhost:8000/docs"
echo "  Context Broker:    http://localhost:8001"
echo "  Grafana:           http://localhost:3001 (admin/admin)"
echo "  Prometheus:        http://localhost:9090"
echo "  Kafka UI:          http://localhost:8080"
echo "  Jaeger:            http://localhost:16686"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f              - View all logs"
echo "  docker-compose logs -f <service>    - View specific service logs"
echo "  docker-compose ps                   - List running services"
echo "  docker-compose down                 - Stop all services"
echo ""
echo "Happy coding! 🎉"
echo ""
