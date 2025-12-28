# PLOS Application Services Startup Script
# Starts ONLY the application services (your custom code)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Application Services Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify Infrastructure
Write-Host "[1/3] Verifying infrastructure..." -ForegroundColor Yellow

$infraRunning = docker-compose ps postgres redis kafka --format json 2>$null
if ($LASTEXITCODE -ne 0 -or -not $infraRunning) {
    Write-Host "Infrastructure is not running!" -ForegroundColor Red
    Write-Host "Please run: ./scripts/start-infrastructure.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "Infrastructure is running" -ForegroundColor Green
Write-Host ""

# Step 2: Build Services
Write-Host "[2/3] Building application services..." -ForegroundColor Yellow
docker-compose build context-broker journal-parser knowledge-system api-gateway

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Services built successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Start Services
Write-Host "[3/3] Starting application services..." -ForegroundColor Yellow
docker-compose up -d context-broker journal-parser knowledge-system api-gateway

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start services!" -ForegroundColor Red
    exit 1
}

Write-Host "Application services started" -ForegroundColor Green
Write-Host ""

# Wait and show status
Write-Host "Waiting 10 seconds for initialization..." -ForegroundColor Gray
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Application Services Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose ps context-broker journal-parser knowledge-system api-gateway
Write-Host ""

Write-Host "Services started!" -ForegroundColor Green
Write-Host ""
Write-Host "API Endpoints:" -ForegroundColor Yellow
Write-Host "  API Gateway:       http://localhost:8000" -ForegroundColor White
Write-Host "  Context Broker:    http://localhost:8001/health" -ForegroundColor White
Write-Host "  Journal Parser:    http://localhost:8002/health" -ForegroundColor White
Write-Host "  Knowledge System:  http://localhost:8003/health" -ForegroundColor White
Write-Host ""
Write-Host "Check logs: docker-compose logs -f [service-name]" -ForegroundColor Gray
Write-Host ""
