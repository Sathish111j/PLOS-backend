#!/bin/bash
# PLOS Setup Script
# Initial setup for local development environment

set -e

echo "=========================================="
echo "  PLOS - Initial Setup"
echo "=========================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose found"
echo ""

# Check .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your GEMINI_API_KEY!"
    echo "   Without it, AI features won't work."
    echo ""
    read -p "Press Enter when you've updated .env..."
else
    echo "✓ .env file exists"
fi

echo ""
echo "🏗️  Building Docker images..."
docker-compose build

echo ""
echo "🚀 Starting infrastructure services (PostgreSQL, Redis, Kafka)..."
docker-compose up -d postgres redis zookeeper kafka

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 15

echo ""
echo "🗄️  Running database migrations..."
# Database will auto-initialize with init scripts

echo ""
echo "📨 Creating Kafka topics..."
docker-compose exec -T kafka bash /infrastructure/kafka/init-topics.sh || true

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Verify .env has your GEMINI_API_KEY"
echo "  2. Run: ./scripts/dev.sh to start all services"
echo "  3. Open: http://localhost:3000 (Frontend)"
echo "  4. API Docs: http://localhost:8000/docs"
echo ""
echo "Useful commands:"
echo "  ./scripts/dev.sh     - Start all services"
echo "  ./scripts/test.sh    - Run tests"
echo "  ./scripts/clean.sh   - Clean everything"
echo ""
