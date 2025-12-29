#!/bin/bash
# PLOS Clean Script - Linux/Mac
# For Windows, use: ./scripts/stop.ps1 -CleanVolumes

set -e

echo "=========================================="
echo "  PLOS - Cleanup"
echo "=========================================="
echo ""

read -p "WARNING: This will remove ALL data (databases, cache). Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Stopping and removing all containers and volumes..."
docker-compose down -v

echo ""
echo "[OK] Cleanup complete!"
echo ""
echo "To start fresh:"
echo "  ./scripts/start-all.sh    (if exists)"
echo "  OR"
echo "  docker-compose up -d postgres redis kafka zookeeper qdrant"
echo "  sleep 30"
echo "  docker-compose up -d context-broker journal-parser knowledge-system"
echo ""
