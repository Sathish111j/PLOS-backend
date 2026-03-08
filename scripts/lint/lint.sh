#!/bin/bash
set -e

# Lint script for LifeOS Backend
# Runs all linting and formatting checks from the CI pipeline.
# Can be run from anywhere - automatically uses the correct Python environment.

MODE="check"
INSTALL=false

for arg in "$@"; do
    case "$arg" in
        --fix)    MODE="fix" ;;
        --install) INSTALL=true ;;
        --check)  MODE="check" ;;
        *)        echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

# Resolve project root (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "LifeOS Backend Linter"
echo "====================="
echo ""

# Detect Python executable
PYTHON_CMD=""

if [ -x ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
    echo "Using virtual environment Python: $PYTHON_CMD"
elif [ -x "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
    echo "Using virtual environment Python: $PYTHON_CMD"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    echo "Using system Python: $(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
    echo "Using system Python: $(command -v python)"
else
    echo "Error: Python not found. Please install Python or create a virtual environment."
    exit 1
fi

# Install dependencies if requested
if [ "$INSTALL" = true ]; then
    echo ""
    echo "Installing linting dependencies..."
    "$PYTHON_CMD" -m pip install --upgrade pip
    "$PYTHON_CMD" -m pip install black ruff isort flake8 mypy bandit safety

    echo "Dependencies installed successfully!"
    exit 0
fi

echo "Mode: $MODE"
echo ""

ERROR_COUNT=0

# Run Black
echo "Running Black (Code Formatter)..."
set +e
if [ "$MODE" = "fix" ]; then
    "$PYTHON_CMD" -m black services/ shared/
else
    "$PYTHON_CMD" -m black --check services/ shared/
fi || ERROR_COUNT=$((ERROR_COUNT + 1))
set -e

echo ""

# Run isort
echo "Running isort (Import Sorter)..."
set +e
if [ "$MODE" = "fix" ]; then
    "$PYTHON_CMD" -m isort services/ shared/
else
    "$PYTHON_CMD" -m isort --check-only services/ shared/
fi || ERROR_COUNT=$((ERROR_COUNT + 1))
set -e

echo ""

# Run Ruff
echo "Running Ruff (Linter)..."
set +e
if [ "$MODE" = "fix" ]; then
    "$PYTHON_CMD" -m ruff check services/ shared/ --fix
else
    "$PYTHON_CMD" -m ruff check services/ shared/
fi || ERROR_COUNT=$((ERROR_COUNT + 1))
set -e

echo ""

# Summary
echo "====================="
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "All checks passed!"
    exit 0
else
    echo "Found issues in $ERROR_COUNT check(s)"
    if [ "$MODE" != "fix" ]; then
        echo "Run with --fix flag to automatically fix issues: ./scripts/lint/lint.sh --fix"
    fi
    exit 1
fi
