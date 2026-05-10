#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# Kolliq — Local Test Runner
# Runs the full test suite using docker-compose.test.yml
#
# Usage:
#   chmod +x run_tests.sh
#   ./run_tests.sh                    # full suite
#   ./run_tests.sh test_scoring       # single module
#   ./run_tests.sh test_escrow -v     # verbose
# ══════════════════════════════════════════════════════════════════

set -e

COMPOSE_FILE="docker-compose.test.yml"
SERVICE="test-runner"

# Colours
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Kolliq Test Suite Runner        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

# ── Build images ──────────────────────────────────────────────────
echo -e "${YELLOW}▶ Building images...${NC}"
docker-compose -f $COMPOSE_FILE build --quiet

# ── Start test DB and Redis ───────────────────────────────────────
echo -e "${YELLOW}▶ Starting test services (DB + Redis)...${NC}"
docker-compose -f $COMPOSE_FILE up -d test-db test-redis

# Wait for health checks
echo -e "${YELLOW}▶ Waiting for services to be healthy...${NC}"
timeout 30 bash -c '
  until docker-compose -f docker-compose.test.yml ps test-db | grep -q "healthy"; do
    sleep 2
  done
'

# ── Determine what to run ─────────────────────────────────────────
if [ -n "$1" ]; then
  # Specific test module passed as argument
  TEST_PATH="tests/${1}.py"
  EXTRA_ARGS="${@:2}"
  echo -e "${YELLOW}▶ Running: ${TEST_PATH} ${EXTRA_ARGS}${NC}"
  TEST_CMD="pytest ${TEST_PATH} --tb=short -v ${EXTRA_ARGS}"
else
  # Full suite
  echo -e "${YELLOW}▶ Running full test suite...${NC}"
  TEST_CMD="pytest tests/ --tb=short --cov=apps --cov-report=term-missing --cov-fail-under=70 -v"
fi

echo ""

# ── Run tests ─────────────────────────────────────────────────────
docker-compose -f $COMPOSE_FILE run --rm \
  -e "TEST_CMD=${TEST_CMD}" \
  $SERVICE \
  sh -c "
    python manage.py wait_for_db &&
    python manage.py migrate --noinput -v 0 &&
    ${TEST_CMD}
  "

EXIT_CODE=$?

# ── Cleanup ───────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}▶ Cleaning up test containers...${NC}"
docker-compose -f $COMPOSE_FILE down -v --remove-orphans 2>/dev/null

# ── Result ────────────────────────────────────────────────────────
echo ""
if [ $EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}╔══════════════════════════════╗${NC}"
  echo -e "${GREEN}║    ✅  All tests passed!      ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════╝${NC}"
else
  echo -e "${RED}╔══════════════════════════════╗${NC}"
  echo -e "${RED}║    ❌  Tests failed.          ║${NC}"
  echo -e "${RED}╚══════════════════════════════╝${NC}"
fi

exit $EXIT_CODE