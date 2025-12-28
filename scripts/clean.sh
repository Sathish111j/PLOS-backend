#!/bin/bash
# PLOS Clean Script
# Clean all Docker containers, volumes, and build cache

set -e

echo "=========================================="
echo "  PLOS - Cleanup"
echo "=========================================="
echo ""

read -p "⚠️  This will remove ALL containers, volumes, and images. Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "🧹 Stopping all containers..."
docker-compose down

echo ""
echo "🗑️  Removing volumes..."
docker-compose down -v

echo ""
echo "🔥 Removing Docker images..."
docker-compose down --rmi all

echo ""
echo "✓ Cleanup complete!"
echo ""
echo "To start fresh, run: ./scripts/setup.sh"
echo ""
