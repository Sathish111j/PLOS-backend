# PLOS Infrastructure Verification Script
# Tests all infrastructure components for stability and correctness

$ErrorCount = 0
$WarningCount = 0

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Infrastructure Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: PostgreSQL Database
Write-Host "[1/7] PostgreSQL Database..." -ForegroundColor Yellow
try {
    $pgReady = docker exec plos-postgres pg_isready -U postgres 2>&1
    if ($pgReady -match "accepting connections") {
        Write-Host "  Connection: OK" -ForegroundColor Green
        
        # Check tables
        $tableCount = docker exec plos-postgres psql -U postgres -d plos -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>&1
        $tableCount = $tableCount.Trim()
        
        if ($tableCount -eq "17") {
            Write-Host "  Tables: $tableCount/17 created" -ForegroundColor Green
        } else {
            Write-Host "  Tables: Only $tableCount/17 found!" -ForegroundColor Red
            $ErrorCount++
        }
        
        # Check test user exists
        $userCount = docker exec plos-postgres psql -U postgres -d plos -t -c "SELECT COUNT(*) FROM users;" 2>&1
        $userCount = $userCount.Trim()
        Write-Host "  Test Users: $userCount" -ForegroundColor Green
        
    } else {
        Write-Host "  FAILED: Database not ready" -ForegroundColor Red
        $ErrorCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 2: Redis Cache
Write-Host ""
Write-Host "[2/7] Redis Cache..." -ForegroundColor Yellow
try {
    $redisPing = docker exec plos-redis redis-cli -a plos_redis_secure_2025 ping 2>&1 | Select-String "PONG"
    if ($redisPing) {
        Write-Host "  Connection: OK" -ForegroundColor Green
        
        $redisInfo = docker exec plos-redis redis-cli -a plos_redis_secure_2025 INFO memory 2>&1 | Select-String "used_memory_human"
        Write-Host "  $redisInfo" -ForegroundColor Green
    } else {
        Write-Host "  FAILED: Redis not responding" -ForegroundColor Red
        $ErrorCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 3: Zookeeper
Write-Host ""
Write-Host "[3/7] Zookeeper..." -ForegroundColor Yellow
try {
    # Zookeeper 3.5+ has four-letter-word commands disabled by default for security
    # Check if the process is running instead
    $zkProcess = docker exec plos-zookeeper ps aux 2>&1 | Select-String "zookeeper"
    if ($zkProcess) {
        Write-Host "  Process: Running" -ForegroundColor Green
        
        # Check if Kafka can connect (best indicator Zookeeper is working)
        $kafkaStatus = docker-compose ps kafka --format json | ConvertFrom-Json
        if ($kafkaStatus.Health -eq "healthy") {
            Write-Host "  Kafka Connection: OK" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Kafka not healthy" -ForegroundColor Yellow
            $WarningCount++
        }
    } else {
        Write-Host "  FAILED: Process not running" -ForegroundColor Red
        $ErrorCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 4: Kafka Message Queue
Write-Host ""
Write-Host "[4/7] Kafka Message Queue..." -ForegroundColor Yellow
try {
    $topics = docker exec plos-kafka kafka-topics --bootstrap-server localhost:9092 --list 2>&1 | Where-Object { $_ -notmatch "WARN" }
    $topicCount = ($topics | Measure-Object).Count
    
    if ($topicCount -gt 0) {
        Write-Host "  Topics: $topicCount found" -ForegroundColor Green
        foreach ($topic in $topics) {
            if ($topic -ne "__consumer_offsets") {
                Write-Host "    - $topic" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  WARNING: No topics created yet" -ForegroundColor Yellow
        $WarningCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 5: Qdrant Vector Database
Write-Host ""
Write-Host "[5/7] Qdrant Vector Database..." -ForegroundColor Yellow
try {
    $headers = @{'api-key' = 'qdrant_secure_key_2025'}
    $response = Invoke-WebRequest -Uri http://localhost:6333/collections -Headers $headers -UseBasicParsing
    $collections = ($response.Content | ConvertFrom-Json).result.collections
    
    Write-Host "  Connection: OK" -ForegroundColor Green
    Write-Host "  Collections: $($collections.Count)" -ForegroundColor Green
    foreach ($collection in $collections) {
        Write-Host "    - $($collection.name)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 6: Prometheus
Write-Host ""
Write-Host "[6/7] Prometheus Monitoring..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:9090/-/healthy -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "  Status: Healthy" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Unexpected status" -ForegroundColor Yellow
        $WarningCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 7: Grafana
Write-Host ""
Write-Host "[7/7] Grafana Dashboard..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:3333/api/health -UseBasicParsing
    $health = $response.Content | ConvertFrom-Json
    if ($health.database -eq "ok") {
        Write-Host "  Database: OK" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Database issue" -ForegroundColor Yellow
        $WarningCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Verification Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($ErrorCount -eq 0 -and $WarningCount -eq 0) {
    Write-Host "STATUS: ALL TESTS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "Infrastructure is STABLE and ready for production!" -ForegroundColor Green
    Write-Host ""
    exit 0
} elseif ($ErrorCount -eq 0) {
    Write-Host "STATUS: PASSED WITH WARNINGS" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Warnings: $WarningCount" -ForegroundColor Yellow
    Write-Host "Infrastructure is functional but needs attention" -ForegroundColor Yellow
    Write-Host ""
    exit 0
} else {
    Write-Host "STATUS: FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Errors: $ErrorCount" -ForegroundColor Red
    Write-Host "Warnings: $WarningCount" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Infrastructure has issues that need fixing!" -ForegroundColor Red
    Write-Host ""
    exit 1
}
