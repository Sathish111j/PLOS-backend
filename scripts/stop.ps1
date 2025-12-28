# PLOS System Shutdown Script

param(
    [switch]$CleanVolumes = $false
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS System Shutdown" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($CleanVolumes) {
    Write-Host "WARNING: This will DELETE all data!" -ForegroundColor Red
    Write-Host "Press Ctrl+C to cancel..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    Write-Host ""
    
    Write-Host "Stopping and removing all data..." -ForegroundColor Yellow
    docker-compose down -v
    
    Write-Host ""
    Write-Host "All services stopped and data cleaned" -ForegroundColor Green
} else {
    Write-Host "Stopping all services (keeping data)..." -ForegroundColor Yellow
    docker-compose down
    
    Write-Host ""
    Write-Host "All services stopped" -ForegroundColor Green
    Write-Host ""
    Write-Host "Data preserved in Docker volumes" -ForegroundColor Yellow
    Write-Host "To also remove data: ./scripts/stop.ps1 -CleanVolumes" -ForegroundColor Gray
}

Write-Host ""
Write-Host "To start: ./scripts/start-all.ps1" -ForegroundColor Gray
Write-Host ""
