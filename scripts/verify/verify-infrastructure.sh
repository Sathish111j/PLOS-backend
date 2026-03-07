#!/bin/bash
set -e

# PLOS Infrastructure Verification Script
# Tests all infrastructure components for stability and correctness.

ERROR_COUNT=0
WARNING_COUNT=0

PG_USER="${POSTGRES_USER:-postgres}"
REDIS_PASSWORD="${REDIS_PASSWORD:-plos_redis_secure_2025}"

echo ""
echo "========================================"
echo "  PLOS Infrastructure Verification"
echo "========================================"
echo ""

# ---- Test 1: Supabase PostgreSQL Database ----
echo "[1/9] Supabase PostgreSQL Database..."
PG_READY=$(docker exec plos-supabase-db pg_isready -U "$PG_USER" 2>&1 || true)
if echo "$PG_READY" | grep -q "accepting connections"; then
    echo "  Connection: OK"
else
    echo "  FAILED: Database not ready"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 2: Supabase Studio ----
echo ""
echo "[2/9] Supabase Studio..."
STUDIO_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:3000/api/profile 2>/dev/null || echo "000")
if [ "$STUDIO_CODE" = "200" ]; then
    echo "  Status: OK"
else
    echo "  WARNING: Studio may still be starting (HTTP $STUDIO_CODE)"
    WARNING_COUNT=$((WARNING_COUNT + 1))
fi

# ---- Test 3: Redis Cache ----
echo ""
echo "[3/9] Redis Cache..."
REDIS_PONG=$(docker exec plos-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning ping 2>&1 || true)
if echo "$REDIS_PONG" | grep -q "PONG"; then
    echo "  Connection: OK"
    REDIS_MEM=$(docker exec plos-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning INFO memory 2>&1 | grep "used_memory_human" || true)
    if [ -n "$REDIS_MEM" ]; then
        echo "  $REDIS_MEM"
    fi
else
    echo "  FAILED: Redis not responding"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 4: Qdrant Vector DB ----
echo ""
echo "[4/9] Qdrant Vector DB..."
QDRANT_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:6333/healthz 2>/dev/null || echo "000")
if [ "$QDRANT_CODE" = "200" ]; then
    echo "  Status: Healthy"
else
    echo "  ERROR: Qdrant not healthy (HTTP $QDRANT_CODE)"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 5: Zookeeper ----
echo ""
echo "[5/9] Zookeeper..."
ZK_PROC=$(docker exec plos-zookeeper ps aux 2>&1 | grep -i "zookeeper" || true)
if [ -n "$ZK_PROC" ]; then
    echo "  Process: Running"
    # Check Kafka health as proxy for Zookeeper connectivity
    KAFKA_HEALTH=$(docker compose ps kafka --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || true)
    if [ "$KAFKA_HEALTH" = "healthy" ]; then
        echo "  Kafka Connection: OK"
    else
        echo "  WARNING: Kafka not healthy"
        WARNING_COUNT=$((WARNING_COUNT + 1))
    fi
else
    echo "  FAILED: Process not running"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 6: Kafka Message Queue ----
echo ""
echo "[6/9] Kafka Message Queue..."
TOPICS=$(docker exec plos-kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1 | grep -v "WARN" || true)
TOPIC_COUNT=$(echo "$TOPICS" | grep -c . 2>/dev/null || echo "0")
if [ "$TOPIC_COUNT" -gt 0 ]; then
    echo "  Topics: $TOPIC_COUNT found"
    while IFS= read -r topic; do
        [ -z "$topic" ] && continue
        if [ "$topic" != "__consumer_offsets" ]; then
            echo "    - $topic"
        fi
    done <<< "$TOPICS"
else
    echo "  WARNING: No topics created yet"
    WARNING_COUNT=$((WARNING_COUNT + 1))
fi

# ---- Test 7: Prometheus Monitoring ----
echo ""
echo "[7/9] Prometheus Monitoring..."
PROM_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:9090/-/healthy 2>/dev/null || echo "000")
if [ "$PROM_CODE" = "200" ]; then
    echo "  Status: Healthy"
else
    echo "  ERROR: Prometheus not healthy (HTTP $PROM_CODE)"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 8: Grafana Dashboard ----
echo ""
echo "[8/9] Grafana Dashboard..."
GRAFANA_HEALTHY=false
for attempt in 1 2 3 4 5; do
    GRAFANA_RESP=$(curl -s --max-time 5 http://localhost:3333/api/health 2>/dev/null || true)
    GRAFANA_DB=$(echo "$GRAFANA_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('database',''))" 2>/dev/null || true)
    if [ "$GRAFANA_DB" = "ok" ]; then
        echo "  Database: OK"
        GRAFANA_HEALTHY=true
        break
    fi
    echo "  WARNING: Grafana not ready (attempt $attempt/5)"
    sleep 5
done

if [ "$GRAFANA_HEALTHY" = false ]; then
    echo "  ERROR: Grafana health check failed"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Test 9: Knowledge Base Service ----
echo ""
echo "[9/9] Knowledge Base Service..."
KB_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:8003/health 2>/dev/null || echo "000")
if [ "$KB_CODE" = "200" ]; then
    echo "  Status: Healthy"
else
    echo "  ERROR: Knowledge Base not healthy (HTTP $KB_CODE)"
    ERROR_COUNT=$((ERROR_COUNT + 1))
fi

# ---- Summary ----
echo ""
echo "========================================"
echo "  Verification Summary"
echo "========================================"
echo ""

if [ "$ERROR_COUNT" -eq 0 ] && [ "$WARNING_COUNT" -eq 0 ]; then
    echo "STATUS: ALL TESTS PASSED"
    echo ""
    echo "Infrastructure is STABLE and ready for production!"
    echo ""
    exit 0
elif [ "$ERROR_COUNT" -eq 0 ]; then
    echo "STATUS: PASSED WITH WARNINGS"
    echo ""
    echo "Warnings: $WARNING_COUNT"
    echo "Infrastructure is functional but needs attention"
    echo ""
    exit 0
else
    echo "STATUS: FAILED"
    echo ""
    echo "Errors: $ERROR_COUNT"
    echo "Warnings: $WARNING_COUNT"
    echo ""
    echo "Infrastructure has issues that need fixing!"
    echo ""
    exit 1
fi
