param()

$ErrorActionPreference = "Stop"

Write-Host "Running Knowledge Base migration tests in Docker container..." -ForegroundColor Cyan
docker compose --profile test run --rm knowledge-base-test
