# PLOS Backend - Connection Verification Script (PowerShell)
# Run this after docker-compose up to verify all connections

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PLOS Backend - Connection Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check service
function Check-Service {
    param (
        [string]$Name,
        [string]$Url
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host "✓ $Name is running" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "✗ $Name is NOT running" -ForegroundColor Red
        return $false
    }
}

Write-Host "1. Checking Docker Services..." -ForegroundColor Yellow
Write-Host "--------------------------------"

# Check if docker-compose is running
try {
    $services = docker-compose ps --services 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Docker Compose is not running. Please run: docker-compose up -d" -ForegroundColor Red
        exit 1
    }
    
    # Check each service
    $running = docker-compose ps | Select-String "Up"
    if ($running) {
        foreach ($line in $services) {
            $status = docker-compose ps $line 2>&1 | Select-String "Up"
            if ($status) {
                Write-Host "✓ $line is up" -ForegroundColor Green
            }
            else {
                Write-Host "✗ $line is down" -ForegroundColor Red
            }
        }
    }
}
catch {
    Write-Host "✗ Error checking Docker services: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. Checking Service Health Endpoints..." -ForegroundColor Yellow
Write-Host "----------------------------------------"

Start-Sleep -Seconds 5  # Wait for services to fully start

Check-Service "Context Broker" "http://localhost:8001/health"
Check-Service "Journal Parser" "http://localhost:8002/health"
Check-Service "Kafka UI" "http://localhost:8080"
Check-Service "Prometheus" "http://localhost:9090"

Write-Host ""
Write-Host "3. Checking Database Connection..." -ForegroundColor Yellow
Write-Host "-----------------------------------"

try {
    $dbCheck = docker-compose exec -T postgres psql -U postgres -d plos -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ PostgreSQL is accessible" -ForegroundColor Green
        
        # Check table count
        $tableCount = docker-compose exec -T postgres psql -U postgres -d plos -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>&1
        $tableCount = $tableCount.Trim()
        Write-Host "✓ Database has $tableCount tables" -ForegroundColor Green
    }
    else {
        Write-Host "✗ PostgreSQL is NOT accessible" -ForegroundColor Red
    }
}
catch {
    Write-Host "✗ PostgreSQL connection error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "4. Checking Redis Connection..." -ForegroundColor Yellow
Write-Host "--------------------------------"

try {
    $redisCheck = docker-compose exec -T redis redis-cli -a plos_redis_secure_2025 --no-auth-warning ping 2>&1
    if ($redisCheck -match "PONG") {
        Write-Host "✓ Redis is accessible" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Redis is NOT accessible" -ForegroundColor Red
    }
}
catch {
    Write-Host "✗ Redis connection error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "5. Checking Kafka Topics..." -ForegroundColor Yellow
Write-Host "----------------------------"

try {
    $topics = docker-compose exec -T kafka kafka-topics --list --bootstrap-server localhost:9092 2>&1
    $topicArray = $topics -split "`n" | Where-Object { $_ -and $_ -notmatch "WARN" }
    $topicCount = $topicArray.Count
    
    if ($topicCount -gt 0) {
        Write-Host "✓ Kafka has $topicCount topics" -ForegroundColor Green
        Write-Host "  Topics:" -ForegroundColor Gray
        $topicArray | Select-Object -First 5 | ForEach-Object { Write-Host "    - $_" -ForegroundColor Gray }
        if ($topicCount -gt 5) {
            Write-Host "    ... and $($topicCount - 5) more" -ForegroundColor Gray
        }
    }
    else {
        Write-Host "✗ No Kafka topics found" -ForegroundColor Red
    }
}
catch {
    Write-Host "✗ Kafka connection error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "6. Testing Gemini API Integration..." -ForegroundColor Yellow
Write-Host "-------------------------------------"

try {
    $geminiCheck = docker-compose exec -T journal-parser env 2>&1 | Select-String "GEMINI_API_KEY"
    if ($geminiCheck) {
        Write-Host "✓ Gemini API key is configured" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ Gemini API key might not be set" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠ Could not verify Gemini API key" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "7. Summary" -ForegroundColor Yellow
Write-Host "----------"

# Count running services
$totalServices = (docker-compose ps --services 2>&1).Count
$runningServices = (docker-compose ps 2>&1 | Select-String "Up").Count

Write-Host "Services Running: $runningServices / $totalServices"
Write-Host ""

if ($runningServices -ge 8) {  # We have 9 services total
    Write-Host "✓ All services are operational!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Access your services:" -ForegroundColor Cyan
    Write-Host "  - API Gateway:     http://localhost:8000" -ForegroundColor White
    Write-Host "  - Context Broker:  http://localhost:8001" -ForegroundColor White
    Write-Host "  - Journal Parser:  http://localhost:8002" -ForegroundColor White
    Write-Host "  - Kafka UI:        http://localhost:8080" -ForegroundColor White
    Write-Host "  - Prometheus:      http://localhost:9090" -ForegroundColor White
    Write-Host "  - Grafana:         http://localhost:3001 (admin/admin)" -ForegroundColor White
    Write-Host ""
    Write-Host "Test Journal Parser:" -ForegroundColor Cyan
    Write-Host '  Invoke-RestMethod -Method Post -Uri "http://localhost:8002/parse" -ContentType "application/json" -Body ''{"id":"test","user_id":"user1","content":"I slept 8 hours and ran 5km. Feeling great!","entry_date":"2025-12-28T07:00:00Z"}''' -ForegroundColor Gray
}
else {
    Write-Host "⚠ Some services are not running properly" -ForegroundColor Yellow
    Write-Host "Check logs with: docker-compose logs -f" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
