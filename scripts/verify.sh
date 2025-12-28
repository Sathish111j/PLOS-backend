#!/bin/bash
# PLOS Backend - Service Verification Script (Linux/Mac)
# For Windows, use: ./scripts/verify-infrastructure.ps1

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
    echo -e "${RED}✗${NC} No services running. Start with: ./scripts/dev.sh"
    exit 1
fi

echo "Infrastructure Services:"
echo "------------------------"

# PostgreSQL
if docker exec plos-postgres pg_isready -U postgres &>/dev/null; then
    echo -e "${GREEN}✓${NC} PostgreSQL"
else
    echo -e "${RED}✗${NC} PostgreSQL"
fi

# Redis
if docker exec plos-redis redis-cli -a plos_redis_secure_2025 ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✓${NC} Redis"
else
    echo -e "${RED}✗${NC} Redis"
fi

# Kafka
if docker exec plos-kafka kafka-topics --bootstrap-server localhost:9092 --list &>/dev/null; then
    echo -e "${GREEN}✓${NC} Kafka"
else
    echo -e "${RED}✗${NC} Kafka"
fi

# Qdrant
if curl -s -H "api-key: qdrant_secure_key_2025" http://localhost:6333/collections &>/dev/null; then
    echo -e "${GREEN}✓${NC} Qdrant"
else
    echo -e "${RED}✗${NC} Qdrant"
fi

echo ""
echo "Application Services:"
echo "---------------------"

# Context Broker
if curl -s http://localhost:8001/health &>/dev/null; then
    echo -e "${GREEN}✓${NC} Context Broker (http://localhost:8001/health)"
else
    echo -e "${RED}✗${NC} Context Broker"
fi

# Journal Parser  
if curl -s http://localhost:8002/health &>/dev/null; then
    echo -e "${GREEN}✓${NC} Journal Parser (http://localhost:8002/health)"
else
    echo -e "${RED}✗${NC} Journal Parser"
fi

# Knowledge System
if curl -s http://localhost:8003/health &>/dev/null; then
    echo -e "${GREEN}✓${NC} Knowledge System (http://localhost:8003/health)"
else
    echo -e "${RED}✗${NC} Knowledge System"
fi

echo ""
echo "=========================================="
echo "For detailed verification, use:"
echo "  ./scripts/verify-infrastructure.ps1 (Windows)"
echo "=========================================="
echo ""
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
