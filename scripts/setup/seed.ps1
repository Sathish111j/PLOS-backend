# PLOS Database Seeding Script
# Seeds the database with initial data after schema is initialized

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Database Seeding" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$dbContainer = "plos-supabase-db"
$seedFile = Join-Path $PSScriptRoot "..\..\infrastructure\database\seed.sql"

# Check if database is ready
Write-Host "Checking database connection..." -ForegroundColor Yellow
try {
    $pgReady = docker exec $dbContainer pg_isready -U postgres 2>&1
    if ($pgReady -match "accepting connections") {
        Write-Host "Database is ready" -ForegroundColor Green
    } else {
        Write-Host "Database not ready!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error connecting to database: $_" -ForegroundColor Red
    exit 1
}

# Seed the database
Write-Host ""
Write-Host "Seeding database..." -ForegroundColor Yellow
try {
    if (-not (Test-Path $seedFile)) {
        Write-Host "Seed file not found at $seedFile" -ForegroundColor Red
        exit 1
    }

    $seedContent = Get-Content $seedFile -Raw
    $seedContent | docker exec -i $dbContainer psql -U postgres -d plos
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Database seeded successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to seed database!" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error seeding database: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Database seeding complete!" -ForegroundColor Green