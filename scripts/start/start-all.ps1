param()

$ErrorActionPreference = "Stop"

$DbContainer = "plos-supabase-db"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$MigrationDir = Join-Path $ProjectRoot "infrastructure\database\migrations"
$SeedScript = Join-Path $ProjectRoot "scripts\setup\seed.ps1"

$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "postgres" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "plos" }

function Wait-DatabaseReady {
    Write-Host "Waiting for database readiness..." -ForegroundColor Yellow
    $maxAttempts = 60
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            $ready = docker exec $DbContainer pg_isready -U $pgUser -d $pgDb 2>&1
            if ($ready -match "accepting connections") {
                Write-Host "Database is ready." -ForegroundColor Green
                return
            }
        } catch {
            # ignore until timeout
        }
        Start-Sleep -Seconds 2
    }

    throw "Database did not become ready in time."
}

function Apply-AppMigrations {
    if (-not (Test-Path $MigrationDir)) {
        Write-Host "Migration directory not found: $MigrationDir" -ForegroundColor Yellow
        return
    }

    $migrationFiles = Get-ChildItem -Path $MigrationDir -Filter *.sql | Sort-Object Name
    if ($migrationFiles.Count -eq 0) {
        Write-Host "No migration SQL files found." -ForegroundColor Yellow
        return
    }

    Write-Host "Applying app migrations..." -ForegroundColor Yellow
    foreach ($file in $migrationFiles) {
        Write-Host "  -> $($file.Name)" -ForegroundColor Gray
        Get-Content $file.FullName -Raw | docker exec -i $DbContainer psql -v ON_ERROR_STOP=1 -U $pgUser -d $pgDb | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Migration failed: $($file.Name)"
        }
    }
    Write-Host "Migrations applied." -ForegroundColor Green
}

function Run-Seed {
    if (-not (Test-Path $SeedScript)) {
        throw "Seed script not found: $SeedScript"
    }
    Write-Host "Running seed script..." -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File $SeedScript
    if ($LASTEXITCODE -ne 0) {
        throw "Seed script failed."
    }
}

Write-Host "" 
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PLOS Start-All" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$infraServices = @(
    "supabase-db",
    "supabase-meta",
    "supabase-studio",
    "redis",
    "zookeeper",
    "kafka",
    "prometheus",
    "grafana"
)

$coreServices = @(
    "context-broker",
    "journal-parser",
    "api-gateway"
)

Write-Host "Starting infrastructure services..." -ForegroundColor Yellow
docker compose --profile studio up -d @infraServices

Write-Host "Waiting for infrastructure to settle..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Wait-DatabaseReady
Apply-AppMigrations
Run-Seed

Write-Host "Starting application services..." -ForegroundColor Yellow
docker compose up -d @coreServices

Write-Host "" 
Write-Host "Startup complete." -ForegroundColor Green
Write-Host "Run verify script:" -ForegroundColor Gray
Write-Host "  .\scripts\verify\verify-infrastructure.ps1" -ForegroundColor Gray
