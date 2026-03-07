#!/bin/bash
set -e

# PLOS System Shutdown Script

CLEAN=false

for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=true ;;
        *)       echo "Unknown flag: $arg"; exit 1 ;;
    esac
done

echo ""
echo "========================================"
echo "  PLOS System Shutdown"
echo "========================================"
echo ""

if [ "$CLEAN" = true ]; then
    echo "WARNING: This will DELETE all data!"
    echo "Press Ctrl+C to cancel..."
    sleep 5
    echo ""

    echo "Stopping and removing all data..."
    docker compose down -v

    echo ""
    echo "All services stopped and data cleaned"
else
    echo "Stopping all services (keeping data)..."
    docker compose down

    echo ""
    echo "All services stopped"
    echo ""
    echo "Data preserved in Docker volumes"
    echo "To also remove data: ./scripts/stop/stop.sh --clean"
fi

echo ""
echo "To start: ./scripts/start/dev.sh"
echo ""
