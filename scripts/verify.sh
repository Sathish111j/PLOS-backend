#!/bin/bash
# PLOS Backend - Service Verification Script (Linux/Mac)
# For Windows, use: ./scripts/verify-infrastructure.ps1

set -e

echo "=========================================="
echo "PLOS Backend - Service Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}[X]${NC} No services running. Start with: ./scripts/dev.sh"
    exit 1
fi

echo "1. Infrastructure Services"
echo "--------------------------"

# PostgreSQL
if docker exec plos-postgres pg_isready -U postgres &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} PostgreSQL"
else
    echo -e "${RED}[X]${NC} PostgreSQL"
fi

# Redis
if docker exec plos-redis redis-cli -a plos_redis_secure_2025 ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}[OK]${NC} Redis"
else
    echo -e "${RED}[X]${NC} Redis"
fi

# Kafka
if docker exec plos-kafka kafka-topics --bootstrap-server localhost:9092 --list &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Kafka"
else
    echo -e "${RED}[X]${NC} Kafka"
fi

# Qdrant
if curl -s -H "api-key: qdrant_secure_key_2025" http://localhost:6333/collections &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Qdrant"
else
    echo -e "${RED}[X]${NC} Qdrant"
fi

echo ""
echo "2. Application Services"
echo "-----------------------"

# Context Broker
if curl -s http://localhost:8001/health &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Context Broker (http://localhost:8001/health)"
else
    echo -e "${RED}[X]${NC} Context Broker"
fi

# Journal Parser  
if curl -s http://localhost:8002/health &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Journal Parser (http://localhost:8002/health)"
else
    echo -e "${RED}[X]${NC} Journal Parser"
fi

# Knowledge System
if curl -s http://localhost:8003/health &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Knowledge System (http://localhost:8003/health)"
else
    echo -e "${RED}[X]${NC} Knowledge System"
fi

echo ""
echo "3. Database Check"
echo "-----------------"

if docker exec plos-postgres psql -U postgres -d plos -c "SELECT 1" > /dev/null 2>&1; then
    table_count=$(docker exec plos-postgres psql -U postgres -d plos -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d ' ')
    echo -e "${GREEN}[OK]${NC} PostgreSQL accessible - $table_count tables"
else
    echo -e "${RED}[X]${NC} PostgreSQL NOT accessible"
fi

echo ""
echo "4. Kafka Topics"
echo "---------------"

topics=$(docker exec plos-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | grep -v "^$" | wc -l)
if [ "$topics" -gt 0 ]; then
    echo -e "${GREEN}[OK]${NC} Kafka has $topics topics"
else
    echo -e "${YELLOW}[!]${NC} No Kafka topics found"
fi

echo ""
echo "5. Summary"
echo "----------"

total_services=$(docker-compose ps --services 2>/dev/null | wc -l)
running_services=$(docker-compose ps 2>/dev/null | grep "Up" | wc -l)

echo "Services Running: $running_services / $total_services"
echo ""

if [ "$running_services" -ge "$total_services" ]; then
    echo -e "${GREEN}All services are operational!${NC}"
else
    echo -e "${YELLOW}Some services may not be running${NC}"
    echo "Check logs with: docker-compose logs -f"
fi

echo ""
echo "=========================================="
echo "Access Points:"
echo "  API Gateway:     http://localhost:8000"
echo "  Context Broker:  http://localhost:8001"
echo "  Journal Parser:  http://localhost:8002"
echo "  Knowledge:       http://localhost:8003"
echo "  Kafka UI:        http://localhost:8080"
echo "  Grafana:         http://localhost:3333"
echo "=========================================="
echo ""
