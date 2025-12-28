# ============================================================================
# PLOS Backend Services Verification Script
# ============================================================================
# Tests all services and their connections

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PLOS Backend Service Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to test HTTP endpoint
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host " $Name - " -ForegroundColor Green -NoNewline
        Write-Host "Status: $($response.StatusCode)" -ForegroundColor White
        if ($response.Content.Length -lt 200) {
            Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
        }
        return $true
    }
    catch {
        Write-Host " $Name - " -ForegroundColor Red -NoNewline
        Write-Host "Failed: $($_.Exception.Message)" -ForegroundColor White
        return $false
    }
}

# Test Infrastructure Services
Write-Host "`n Infrastructure Services" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

$postgres = Test-Endpoint "PostgreSQL (5432)" "http://localhost:5432"
$redis = Test-Endpoint "Redis (6379)" "http://localhost:6379"
Test-Endpoint "Kafka UI (8080)" "http://localhost:8080"
Test-Endpoint "Prometheus (9090)" "http://localhost:9090"
Test-Endpoint "Grafana (3333)" "http://localhost:3333"

# Test Core Services
Write-Host "`n🚀 Core Services" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

$contextBroker = Test-Endpoint "Context Broker (8001)" "http://localhost:8001/health"
$journalParser = Test-Endpoint "Journal Parser (8002)" "http://localhost:8002/health"
$apiGateway = Test-Endpoint "API Gateway (8000)" "http://localhost:8000"

# Test Service Stats
Write-Host "`n Service Statistics" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

if ($contextBroker) {
    try {
        $stats = Invoke-WebRequest -Uri "http://localhost:8001/stats" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
        Write-Host "Context Broker Stats:" -ForegroundColor Cyan
        Write-Host "  Total Contexts: $($stats.total_contexts)" -ForegroundColor White
        Write-Host "  Cache Hit Rate: $($stats.cache_hit_rate)%" -ForegroundColor White
    }
    catch {
        Write-Host "  Context Broker stats endpoint not available" -ForegroundColor Yellow
    }
}

# Test Journal Parser with sample entry
Write-Host "`n Testing Gemini AI Integration" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

if ($journalParser) {
    try {
        $testEntry = @{
            id = "test-verify-001"
            user_id = "test-user"
            content = "Woke up feeling great! Had 8 hours of sleep. Did a 30 minute run. Mood is excellent today at 9/10."
            entry_date = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
        } | ConvertTo-Json

        $parseResponse = Invoke-WebRequest -Uri "http://localhost:8002/parse" `
            -Method POST `
            -Body $testEntry `
            -ContentType "application/json" `
            -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json

        Write-Host " Journal Parser AI Processing:" -ForegroundColor Green
        Write-Host "  Mood Score: $($parseResponse.mood_score)" -ForegroundColor White
        Write-Host "  Energy Level: $($parseResponse.energy_level)" -ForegroundColor White
        Write-Host "  Sleep Hours: $($parseResponse.sleep_hours)" -ForegroundColor White
        Write-Host "  Exercise Minutes: $($parseResponse.exercise_minutes)" -ForegroundColor White
        Write-Host "  Tags: $($parseResponse.tags -join ', ')" -ForegroundColor White
    }
    catch {
        Write-Host "  Journal Parser test failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Docker Container Status
Write-Host "`n🐳 Docker Container Status" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

docker-compose ps

# Summary
Write-Host "`n📋 Verification Summary" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

$totalServices = 8
$healthyServices = 0
if ($contextBroker) { $healthyServices++ }
if ($journalParser) { $healthyServices++ }
if ($apiGateway) { $healthyServices++ }

Write-Host "`nCore Services: $healthyServices/3 healthy" -ForegroundColor $(if ($healthyServices -eq 3) { "Green" } else { "Yellow" })
Write-Host ""
Write-Host "✨ Verification Complete!" -ForegroundColor Cyan
Write-Host ""
