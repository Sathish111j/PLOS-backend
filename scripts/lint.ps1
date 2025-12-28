# Lint script for LifeOS Backend
# This script runs all linting and formatting checks from the CI pipeline
# Can be run from anywhere - automatically uses the correct Python environment

param(
    [switch]$Fix,        # Apply fixes instead of just checking
    [switch]$Install,    # Install linting dependencies
    [switch]$Check       # Only check, don't fix (default)
)

# Get the script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project root
Set-Location $ProjectRoot

Write-Host "LifeOS Backend Linter" -ForegroundColor Cyan
Write-Host "=====================`n" -ForegroundColor Cyan

# Detect Python executable
$PythonCmd = $null

# Try to find Python in virtual environment first
if (Test-Path "venv\Scripts\python.exe") {
    $PythonCmd = ".\venv\Scripts\python.exe"
    Write-Host "Using virtual environment Python: $PythonCmd" -ForegroundColor Green
}
elseif (Test-Path ".venv\Scripts\python.exe") {
    $PythonCmd = ".\.venv\Scripts\python.exe"
    Write-Host "Using virtual environment Python: $PythonCmd" -ForegroundColor Green
}
else {
    # Fall back to system Python
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($PythonPath) {
        $PythonCmd = "python"
        Write-Host "Using system Python: $PythonPath" -ForegroundColor Yellow
    }
    else {
        Write-Host "Error: Python not found. Please install Python or create a virtual environment." -ForegroundColor Red
        exit 1
    }
}

# Install dependencies if requested
if ($Install) {
    Write-Host "`nInstalling linting dependencies..." -ForegroundColor Cyan
    & $PythonCmd -m pip install --upgrade pip
    & $PythonCmd -m pip install black ruff isort flake8 mypy bandit safety
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Dependencies installed successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    exit 0
}

# Determine mode
$Mode = if ($Fix) { "fix" } else { "check" }
Write-Host "Mode: $Mode`n" -ForegroundColor Cyan

$ErrorCount = 0

# Run Black
Write-Host "Running Black (Code Formatter)..." -ForegroundColor Yellow
if ($Fix) {
    & $PythonCmd -m black services/ shared/
}
else {
    & $PythonCmd -m black --check services/ shared/
}
if ($LASTEXITCODE -ne 0) { $ErrorCount++ }

Write-Host ""

# Run isort
Write-Host "Running isort (Import Sorter)..." -ForegroundColor Yellow
if ($Fix) {
    & $PythonCmd -m isort services/ shared/
}
else {
    & $PythonCmd -m isort --check-only services/ shared/
}
if ($LASTEXITCODE -ne 0) { $ErrorCount++ }

Write-Host ""

# Run Ruff
Write-Host "Running Ruff (Linter)..." -ForegroundColor Yellow
if ($Fix) {
    & $PythonCmd -m ruff check services/ shared/ --fix
}
else {
    & $PythonCmd -m ruff check services/ shared/
}
if ($LASTEXITCODE -ne 0) { $ErrorCount++ }

Write-Host ""

# Summary
Write-Host "=====================" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "All checks passed!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "Found issues in $ErrorCount check(s)" -ForegroundColor Red
    if (-not $Fix) {
        Write-Host "Run with -Fix flag to automatically fix issues: .\scripts\lint.ps1 -Fix" -ForegroundColor Yellow
    }
    exit 1
}
