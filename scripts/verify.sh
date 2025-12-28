#!/bin/bash

# PLOS Backend - Connection Verification Script
# Run this after docker-compose up to verify all connections

echo "========================================"
echo "PLOS Backend - Connection Verification"
echo "========================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check service
check_service() {
    local name=$1
    local url=$2
    
    if curl -f -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $name is NOT running"
        return 1
    fi
}

# Function to check port
check_port() {
    local name=$1
    local port=$2
    
    if docker-compose exec -T postgres nc -z localhost $port > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (port $port) is accessible"
        return 0
    else
        echo -e "${RED}✗${NC} $name (port $port) is NOT accessible"
        return 1
    fi
}

echo "1. Checking Docker Services..."
echo "--------------------------------"

# Check if docker-compose is running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}✗${NC} No services are running. Please run: docker-compose up -d"
    exit 1
fi

services=$(docker-compose ps --services)
for service in $services; do
    status=$(docker-compose ps $service | grep Up)
    if [ -n "$status" ]; then
        echo -e "${GREEN}✓${NC} $service is up"
    else
        echo -e "${RED}✗${NC} $service is down"
    fi
done

echo ""
echo "2. Checking Service Health Endpoints..."
echo "----------------------------------------"

sleep 5  # Wait for services to fully start

check_service "Context Broker" "http://localhost:8001/health"
check_service "Journal Parser" "http://localhost:8002/health"
check_service "Kafka UI" "http://localhost:8080"
check_service "Prometheus" "http://localhost:9090"

echo ""
echo "3. Checking Database Connection..."
echo "-----------------------------------"

if docker-compose exec -T postgres psql -U postgres -d plos -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} PostgreSQL is accessible"
    
    # Check table count
    table_count=$(docker-compose exec -T postgres psql -U postgres -d plos -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    echo -e "${GREEN}✓${NC} Database has $table_count tables"
else
    echo -e "${RED}✗${NC} PostgreSQL is NOT accessible"
fi

echo ""
echo "4. Checking Redis Connection..."
echo "--------------------------------"

if docker-compose exec -T redis redis-cli -a plos_redis_secure_2025 --no-auth-warning ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is accessible"
else
    echo -e "${RED}✗${NC} Redis is NOT accessible"
fi

echo ""
echo "5. Checking Kafka Topics..."
echo "----------------------------"

topics=$(docker-compose exec -T kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null)
topic_count=$(echo "$topics" | wc -l)

if [ $topic_count -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Kafka has $topic_count topics"
    echo "  Topics:"
    echo "$topics" | head -5 | sed 's/^/    - /'
    if [ $topic_count -gt 5 ]; then
        echo "    ... and $((topic_count - 5)) more"
    fi
else
    echo -e "${RED}✗${NC} No Kafka topics found"
fi

echo ""
echo "6. Testing Gemini API Integration..."
echo "-------------------------------------"

# Check if Gemini API key is set
if docker-compose exec -T journal-parser env | grep -q "GEMINI_API_KEY=AIza"; then
    echo -e "${GREEN}✓${NC} Gemini API key is configured"
else
    echo -e "${YELLOW}⚠${NC} Gemini API key might not be set"
fi

echo ""
echo "7. Summary"
echo "----------"

# Count running services
total_services=$(docker-compose ps --services | wc -l)
running_services=$(docker-compose ps | grep "Up" | wc -l)

echo "Services Running: $running_services / $total_services"
echo ""

if [ $running_services -eq $total_services ]; then
    echo -e "${GREEN}✓ All services are operational!${NC}"
    echo ""
    echo "Access your services:"
    echo "  - API Gateway:     http://localhost:8000"
    echo "  - Context Broker:  http://localhost:8001"
    echo "  - Journal Parser:  http://localhost:8002"
    echo "  - Kafka UI:        http://localhost:8080"
    echo "  - Prometheus:      http://localhost:9090"
    echo "  - Grafana:         http://localhost:3001 (admin/admin)"
    echo ""
    echo "Test Journal Parser:"
    echo '  curl -X POST http://localhost:8002/parse -H "Content-Type: application/json" -d '"'"'{"id":"test","user_id":"user1","content":"I slept 8 hours and ran 5km. Feeling great!","entry_date":"2025-12-28T07:00:00Z"}'"'"
else
    echo -e "${RED}⚠ Some services are not running properly${NC}"
    echo "Check logs with: docker-compose logs -f"
fi

echo ""
echo "========================================"
