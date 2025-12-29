#!/bin/bash
# PLOS Setup Script - Linux/Mac
# For Windows, use PowerShell scripts instead

set -e

echo "=========================================="
echo "  PLOS - Initial Setup"
echo "=========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "[ERROR] Docker Compose is not installed."
    exit 1
fi

echo "[OK] Docker and Docker Compose found"
echo ""

# Check .env file
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    if [ ! -f .env.example ]; then
        echo "[ERROR] .env.example not found!"
        exit 1
    fi
    cp .env.example .env
    echo "[OK] .env file created"
    echo ""
    echo "IMPORTANT: Edit .env and add your GEMINI_API_KEY!"
    echo ""
    read -p "Press Enter when you've updated .env..."
else
    echo "[OK] .env file exists"
fi

echo ""
echo "[OK] Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Make sure GEMINI_API_KEY is set in .env"
echo "  2. Run: ./scripts/dev.sh"
echo ""
echo "Waiting for services to be ready..."
sleep 15

echo ""
echo "Running database migrations..."
# Database will auto-initialize with init scripts

echo ""
echo "Creating Kafka topics..."
docker-compose exec -T kafka bash /infrastructure/kafka/init-topics.sh || true

echo ""
echo "=========================================="
echo "  Setup Complete!"
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
