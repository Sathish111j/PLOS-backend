#!/bin/bash
# PLOS Backend - Initial Setup Script
# Validates prerequisites and prepares the .env file.
# Run once before starting the stack for the first time.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
fail() { echo -e "${RED}[ERROR]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

echo ""
echo "=========================================="
echo "  PLOS - Initial Setup"
echo "=========================================="
echo ""

# -- Prerequisites ----------------------------------------------------------

echo "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    fail "Docker is not installed. Please install Docker Desktop or Docker Engine."
    exit 1
fi

# Accept both 'docker compose' (plugin) and 'docker-compose' (standalone)
if docker compose version &>/dev/null 2>&1; then
    ok "Docker Engine and Compose plugin found"
elif command -v docker-compose &>/dev/null; then
    ok "Docker and docker-compose (standalone) found"
else
    fail "Docker Compose is not available. Install the Compose plugin: https://docs.docker.com/compose/install/"
    exit 1
fi

echo ""

# -- Environment file -------------------------------------------------------

if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        fail ".env.example not found. Cannot create .env."
        exit 1
    fi
    cp .env.example .env
    ok ".env created from .env.example"
    warn "GEMINI_API_KEY is not yet set. Edit .env before starting the stack."
else
    ok ".env already exists"
fi

# Warn if GEMINI_API_KEY is missing or is the placeholder value
# shellcheck disable=SC1091
GEMINI_KEY=$(grep -E '^GEMINI_API_KEY=' .env | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$GEMINI_KEY" ] || [ "$GEMINI_KEY" = "your_gemini_api_key_here" ]; then
    warn "GEMINI_API_KEY is not configured in .env. Gemini-dependent features will not work."
fi

echo ""
echo "=========================================="
echo "  Setup Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Set GEMINI_API_KEY in .env (if not done)"
echo "  2. Start all services:     ./scripts/start/dev.sh"
echo "  3. Verify infrastructure:  ./scripts/verify/verify-infrastructure.sh"
echo ""
echo "Other commands:"
echo "  ./scripts/setup/migrate.sh          - Run DB migrations only"
echo "  ./scripts/setup/seed.sh             - Seed initial data"
echo "  ./scripts/stop/stop.sh              - Stop all services (keep data)"
echo "  ./scripts/stop/stop.sh --clean      - Stop and delete all volumes"
echo "  ./scripts/verify/smoke-e2e.sh       - End-to-end API smoke test"
echo ""
