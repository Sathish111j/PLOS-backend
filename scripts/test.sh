#!/bin/bash
# PLOS Test Runner - Linux/Mac
# For Windows: pytest services/ shared/ -v

set -e

echo "=========================================="
echo "  PLOS - Test Suite"
echo "=========================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "[ERROR] pytest not found. Installing..."
    pip install pytest pytest-asyncio pytest-cov httpx
fi

# Check for virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "[OK] Using virtual environment: .venv"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "[OK] Using virtual environment: venv"
else
    echo "[INFO] No virtual environment found, using system Python"
fi

echo ""
echo "Running tests..."
echo ""

# Run tests with coverage
pytest services/ shared/ -v --cov=services --cov=shared --cov-report=term-missing --cov-report=html

echo ""
echo "=========================================="
echo "  Test Results"
echo "=========================================="
echo ""
echo "Coverage report: htmlcov/index.html"
echo ""
