# PLOS Infrastructure Startup Script
# Starts ONLY the infrastructure layer (databases, cache, etc.)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Infrastructure Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start Core Infrastructure
Write-Host "[1/3] Starting Core Infrastructure (Supabase DB, Redis, Kafka, Qdrant)..." -ForegroundColor Yellow
docker-compose up -d supabase-db redis zookeeper kafka qdrant

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start core infrastructure!" -ForegroundColor Red
    exit 1
}

Write-Host "Core infrastructure containers started" -ForegroundColor Green
Write-Host ""

# Step 2: Wait for database to be ready
Write-Host "[2/3] Waiting 30 seconds for health checks..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Step 3: Start Supabase Studio and Monitoring
Write-Host "[3/3] Starting Supabase Studio & Monitoring..." -ForegroundColor Yellow
docker-compose up -d supabase-meta supabase-studio prometheus grafana kafka-ui

Write-Host "Supabase Studio and Monitoring services started" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Infrastructure Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose ps supabase-db supabase-meta supabase-studio redis kafka zookeeper qdrant prometheus grafana kafka-ui
Write-Host ""

Write-Host "Infrastructure is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next step:" -ForegroundColor Yellow
Write-Host "  Run: ./scripts/start-services.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Access Points:" -ForegroundColor Yellow
Write-Host "  Supabase Studio: http://localhost:3000" -ForegroundColor White
Write-Host "  Kafka UI:        http://localhost:8080" -ForegroundColor White
Write-Host "  Grafana:         http://localhost:3333" -ForegroundColor White
Write-Host "  Prometheus:      http://localhost:9090" -ForegroundColor White
Write-Host "  Qdrant:          http://localhost:6333/dashboard" -ForegroundColor White
Write-Host ""
