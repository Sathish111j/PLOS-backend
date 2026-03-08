#!/usr/bin/env bash
# ============================================================================
# PLOS - Run All Tests Inside Docker
# ============================================================================
# Spins up all infrastructure + services, then runs every test
# (unit, integration, e2e) inside a dedicated test-runner container.
#
# Usage:
#   ./scripts/test/run-all-docker.sh                  # all tests
#   ./scripts/test/run-all-docker.sh -m e2e           # only E2E tests
#   ./scripts/test/run-all-docker.sh tests/test_e2e_journal_parser.py -v
#   ./scripts/test/run-all-docker.sh --build           # force rebuild
#
# The script forwards any extra arguments to pytest inside the container.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colour helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

# ---------------------------------------------------------------------------
# Parse arguments: split our flags from pytest args
# ---------------------------------------------------------------------------
BUILD_FLAG=""
PYTEST_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --build)
            BUILD_FLAG="--build"
            ;;
        *)
            PYTEST_ARGS+=("$arg")
            ;;
    esac
done

# If no pytest args supplied, default to all tests verbose
if [ ${#PYTEST_ARGS[@]} -eq 0 ]; then
    PYTEST_ARGS=("-v" "--tb=short" "-p" "no:cacheprovider" "tests/")
fi

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.test.yml"

# ---------------------------------------------------------------------------
# Step 1: Ensure infrastructure + services are up
# ---------------------------------------------------------------------------
echo -e "${CYAN}[1/4] Ensuring infrastructure and services are running...${NC}"
docker compose $COMPOSE_FILES up -d --wait \
    supabase-db redis kafka qdrant meilisearch minio zookeeper kafka-init \
    api-gateway context-broker journal-parser knowledge-base 2>&1 | \
    tail -5

# ---------------------------------------------------------------------------
# Step 2: Build the test runner image
# ---------------------------------------------------------------------------
echo -e "${CYAN}[2/4] Building test-runner image...${NC}"
docker compose $COMPOSE_FILES build $BUILD_FLAG test-runner 2>&1 | tail -5

# ---------------------------------------------------------------------------
# Step 3: Run the tests
# ---------------------------------------------------------------------------
echo -e "${CYAN}[3/4] Running tests inside Docker...${NC}"
echo -e "${YELLOW}  pytest ${PYTEST_ARGS[*]}${NC}"
echo ""

EXIT_CODE=0
docker compose $COMPOSE_FILES run --rm test-runner "${PYTEST_ARGS[@]}" || EXIT_CODE=$?

# ---------------------------------------------------------------------------
# Step 4: Report
# ---------------------------------------------------------------------------
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests passed.${NC}"
elif [ $EXIT_CODE -eq 5 ]; then
    echo -e "${YELLOW}No tests were collected (exit code 5). Check your markers/paths.${NC}"
else
    echo -e "${RED}Some tests failed (exit code $EXIT_CODE).${NC}"
fi

exit $EXIT_CODE
