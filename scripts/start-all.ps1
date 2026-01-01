# PLOS Complete System Startup
# Starts infrastructure first, then application services

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS - Complete System Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start Infrastructure
Write-Host "Step 1: Starting Infrastructure..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot/start-infrastructure.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Infrastructure startup failed!" -ForegroundColor Red
    exit 1
}

# Step 2: Verify Infrastructure Health
Write-Host ""
Write-Host "Step 2: Verifying Infrastructure Health..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot/verify-infrastructure.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Infrastructure health check failed!" -ForegroundColor Red
    exit 1
}

# Step 3: Start Application Services
Write-Host ""
Write-Host "Step 3: Starting Application Services..." -ForegroundColor Yellow
Write-Host ""
& "$PSScriptRoot/start-services.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Application services startup failed!" -ForegroundColor Red
    Write-Host "Infrastructure is still running." -ForegroundColor Yellow
    Write-Host "Fix the issue and run: ./scripts/start-services.ps1" -ForegroundColor Yellow
    exit 1
}

# Step 4: Verify Services Health
Write-Host ""
Write-Host "Step 4: Verifying Services Health..." -ForegroundColor Yellow
Write-Host ""
Start-Sleep -Seconds 30  # Wait for services to fully start

# Quick health check for services
$servicesHealthy = $true
$serviceUrls = @(
    "http://localhost:8444/status",  # Kong admin health
    "http://localhost:8001/health", 
    "http://localhost:8002/health",
    "http://localhost:8003/health"
)

foreach ($url in $serviceUrls) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        if ($response.StatusCode -ne 200) {
            Write-Host "  $url - FAILED (Status: $($response.StatusCode))" -ForegroundColor Red
            $servicesHealthy = $false
        } else {
            Write-Host "  $url - OK" -ForegroundColor Green
        }
    } catch {
        Write-Host "  $url - FAILED ($($_.Exception.Message))" -ForegroundColor Red
        $servicesHealthy = $false
    }
}

if (-not $servicesHealthy) {
    Write-Host ""
    Write-Host "Services health check failed!" -ForegroundColor Red
    Write-Host "Some services may still be starting. Check logs with: docker-compose logs -f" -ForegroundColor Yellow
    exit 1
}

# Database is already initialized via init.sql when postgres container starts

# Success
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SYSTEM READY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "All services are running!" -ForegroundColor Green
Write-Host ""
Write-Host "Infrastructure:" -ForegroundColor Cyan
Write-Host "  Supabase Studio: http://localhost:3000" -ForegroundColor White
Write-Host "  Kafka UI:        http://localhost:8080" -ForegroundColor White
Write-Host "  Grafana:         http://localhost:3333" -ForegroundColor White
Write-Host "  Prometheus:      http://localhost:9090" -ForegroundColor White
Write-Host ""
Write-Host "APIs:" -ForegroundColor Cyan
Write-Host "  API Gateway: http://localhost:8000" -ForegroundColor White
Write-Host "  Context:     http://localhost:8001/health" -ForegroundColor White
Write-Host "  Journal:     http://localhost:8002/health" -ForegroundColor White
Write-Host "  Knowledge:   http://localhost:8003/health" -ForegroundColor White
Write-Host ""
Write-Host "Stop: ./scripts/stop.ps1" -ForegroundColor Gray
Write-Host ""
