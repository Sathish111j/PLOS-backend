# PLOS Infrastructure Verification Script
# Tests all infrastructure components for stability and correctness

$ErrorCount = 0
$WarningCount = 0

$pgUser = $env:POSTGRES_USER
if (-not $pgUser) {
    $pgUser = "postgres"
}

$redisPassword = $env:REDIS_PASSWORD
if (-not $redisPassword) {
    $redisPassword = "plos_redis_secure_2025"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Infrastructure Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Supabase PostgreSQL Database
Write-Host "[1/9] Supabase PostgreSQL Database..." -ForegroundColor Yellow
try {
    $pgReady = docker exec plos-supabase-db pg_isready -U $pgUser 2>&1
    if ($pgReady -match "accepting connections") {
        Write-Host "  Connection: OK" -ForegroundColor Green
    } else {
        Write-Host "  FAILED: Database not ready" -ForegroundColor Red
        $ErrorCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 2: Supabase Studio
Write-Host ""
Write-Host "[2/9] Supabase Studio..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:3000/api/profile -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "  Status: OK" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Unexpected status" -ForegroundColor Yellow
        $WarningCount++
    }
} catch {
    Write-Host "  WARNING: Studio may still be starting - $_" -ForegroundColor Yellow
    $WarningCount++
}

# Test 3: Redis Cache
Write-Host ""
Write-Host "[3/9] Redis Cache..." -ForegroundColor Yellow
try {
    $redisPing = docker exec plos-redis redis-cli -a $redisPassword --no-auth-warning ping 2>&1 | Select-String "PONG"
    if ($redisPing) {
        Write-Host "  Connection: OK" -ForegroundColor Green
        
        $redisInfo = docker exec plos-redis redis-cli -a $redisPassword --no-auth-warning INFO memory 2>&1 | Select-String "used_memory_human"
        Write-Host "  $redisInfo" -ForegroundColor Green
    } else {
        Write-Host "  FAILED: Redis not responding" -ForegroundColor Red
        $ErrorCount++
    }
} catch {
    Write-Host "  ERROR: $_" -ForegroundColor Red
    $ErrorCount++
}

# Test 4: Qdrant
Write-Host ""
Write-Host "[4/9] Qdrant Vector DB..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:6333/healthz -UseBasicParsing -TimeoutSec 10
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

# Test 5: Zookeeper
Write-Host ""
Write-Host "[5/9] Zookeeper..." -ForegroundColor Yellow
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

# Test 6: Kafka Message Queue
Write-Host ""
Write-Host "[6/9] Kafka Message Queue..." -ForegroundColor Yellow
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

# Test 7: Prometheus
Write-Host ""
Write-Host "[7/9] Prometheus Monitoring..." -ForegroundColor Yellow
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

# Test 8: Grafana
Write-Host ""
Write-Host "[8/9] Grafana Dashboard..." -ForegroundColor Yellow
$grafanaHealthy = $false
for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri http://localhost:3333/api/health -UseBasicParsing -TimeoutSec 5
        $health = $response.Content | ConvertFrom-Json
        if ($health.database -eq "ok") {
            Write-Host "  Database: OK" -ForegroundColor Green
            $grafanaHealthy = $true
            break
        }
        Write-Host "  WARNING: Database issue (attempt $attempt/5)" -ForegroundColor Yellow
    } catch {
        Write-Host "  WARNING: Grafana not ready (attempt $attempt/5)" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 5
}

if (-not $grafanaHealthy) {
    Write-Host "  ERROR: Grafana health check failed" -ForegroundColor Red
    $ErrorCount++
}

# Test 9: Knowledge Base service
Write-Host ""
Write-Host "[9/9] Knowledge Base Service..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri http://localhost:8003/health -UseBasicParsing -TimeoutSec 10
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
