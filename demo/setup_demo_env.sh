#!/usr/bin/env bash
# =============================================================================
# Pre-Demo Environment Setup
# =============================================================================
# One-command setup for the Business Observability concept demo.
# Generates historical data, loads to Tempo/Loki, imports dashboards,
# and creates concept demo tasks.
#
# Usage:
#   ./demo/setup_demo_env.sh              # Full setup
#   ./demo/setup_demo_env.sh --check      # Verify prerequisites only
#   ./demo/setup_demo_env.sh --skip-data  # Skip data generation (use existing)
#   ./demo/setup_demo_env.sh --verbose    # Verbose output
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEV_ROOT="${CONTEXTCORE_DEV_ROOT:-$(dirname "$PROJECT_DIR")}"
CONTEXTCORE_DIR="${CONTEXTCORE_ROOT:-$DEV_ROOT/ContextCore}"

# Configuration
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_AUTH="${GRAFANA_AUTH:-admin:admin}"
TEMPO_URL="${TEMPO_URL:-http://localhost:3200}"
LOKI_URL="${LOKI_URL:-http://localhost:3100}"
DEMO_SEED=42

# Parse arguments
CHECK_ONLY=false
SKIP_DATA=false
VERBOSE=false

for arg in "$@"; do
    case $arg in
        --check) CHECK_ONLY=true ;;
        --skip-data) SKIP_DATA=true ;;
        --verbose|-v) VERBOSE=true ;;
        --help|-h)
            echo "Usage: $0 [--check] [--skip-data] [--verbose]"
            echo ""
            echo "Options:"
            echo "  --check      Verify prerequisites only, don't set up"
            echo "  --skip-data  Skip data generation (use existing demo data)"
            echo "  --verbose    Verbose output"
            echo "  --help       Show this help message"
            exit 0
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_ok() {
    echo -e "${GREEN}  [OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "       $1"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check prerequisites
# ─────────────────────────────────────────────────────────────────────────────

check_prerequisites() {
    local all_ok=true

    log_step "Checking prerequisites..."

    # Check ContextCore directory
    if [ -d "$CONTEXTCORE_DIR" ]; then
        log_ok "ContextCore found: $CONTEXTCORE_DIR"
    else
        log_fail "ContextCore not found: $CONTEXTCORE_DIR"
        log_info "Set CONTEXTCORE_ROOT or CONTEXTCORE_DEV_ROOT env var"
        all_ok=false
    fi

    # Check ContextCore CLI
    if command -v contextcore &> /dev/null; then
        local version
        version=$(contextcore --version 2>/dev/null || echo "unknown")
        log_ok "ContextCore CLI: $version"
    else
        log_warn "ContextCore CLI not found (some features may not work)"
    fi

    # Check Python
    if command -v python3 &> /dev/null; then
        log_ok "Python3 available"
    else
        log_fail "Python3 not found"
        all_ok=false
    fi

    # Check Grafana
    if curl -sf "${GRAFANA_URL}/api/health" > /dev/null 2>&1; then
        log_ok "Grafana healthy: $GRAFANA_URL"
    else
        log_fail "Grafana not reachable: $GRAFANA_URL"
        all_ok=false
    fi

    # Check Tempo
    if curl -sf "${TEMPO_URL}/ready" > /dev/null 2>&1; then
        log_ok "Tempo healthy: $TEMPO_URL"
    else
        log_fail "Tempo not reachable: $TEMPO_URL"
        all_ok=false
    fi

    # Check Loki
    if curl -sf "${LOKI_URL}/ready" > /dev/null 2>&1; then
        log_ok "Loki healthy: $LOKI_URL"
    else
        log_warn "Loki not reachable: $LOKI_URL (LogQL queries will not work)"
    fi

    # Check OTLP endpoint
    local otlp_port=""
    if nc -z localhost 4317 2>/dev/null; then
        otlp_port=4317
    elif nc -z localhost 14317 2>/dev/null; then
        otlp_port=14317
    fi

    if [ -n "$otlp_port" ]; then
        log_ok "OTLP endpoint: localhost:$otlp_port"
    else
        log_fail "OTLP endpoint not found (tried ports 4317, 14317)"
        all_ok=false
    fi

    echo ""
    if [ "$all_ok" = true ]; then
        log_ok "All prerequisites met"
    else
        log_fail "Some prerequisites missing (see above)"
    fi

    echo ""
    return $([ "$all_ok" = true ] && echo 0 || echo 1)
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Generate historical demo data
# ─────────────────────────────────────────────────────────────────────────────

generate_demo_data() {
    log_step "Generating historical demo data (3 months, seed=$DEMO_SEED)..."

    cd "$CONTEXTCORE_DIR"

    if [ -f "demo_output/demo_spans.json" ] && [ "$SKIP_DATA" = true ]; then
        log_ok "Using existing demo data: demo_output/demo_spans.json"
        return 0
    fi

    if command -v contextcore &> /dev/null; then
        contextcore demo generate --project online-boutique --seed $DEMO_SEED --months 3
        log_ok "Demo data generated"
    else
        # Fallback: use Python module directly
        python3 -c "
from contextcore.demo import generate_demo_data
data = generate_demo_data(project='online-boutique', seed=$DEMO_SEED, months=3)
print(f'Generated {len(data)} spans')
" 2>/dev/null || {
            log_warn "Could not generate data via CLI or Python module"
            log_info "Ensure ContextCore is installed: pip install -e $CONTEXTCORE_DIR"
            return 1
        }
        log_ok "Demo data generated (via Python module)"
    fi

    if [ -f "demo_output/demo_spans.json" ]; then
        local span_count
        span_count=$(python3 -c "import json; print(len(json.load(open('demo_output/demo_spans.json'))))" 2>/dev/null || echo "unknown")
        log_ok "Spans generated: $span_count"
    fi

    cd "$PROJECT_DIR"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Load data to Tempo
# ─────────────────────────────────────────────────────────────────────────────

load_to_tempo() {
    log_step "Loading spans to Tempo..."

    # Determine OTLP port
    local otlp_port=""
    if nc -z localhost 4317 2>/dev/null; then
        otlp_port=4317
    elif nc -z localhost 14317 2>/dev/null; then
        otlp_port=14317
    fi

    if [ -z "$otlp_port" ]; then
        log_fail "No OTLP endpoint found"
        return 1
    fi

    cd "$CONTEXTCORE_DIR"

    if [ ! -f "demo_output/demo_spans.json" ]; then
        log_fail "No demo data found. Run without --skip-data first."
        return 1
    fi

    if command -v contextcore &> /dev/null; then
        contextcore demo load --file ./demo_output/demo_spans.json --endpoint "localhost:$otlp_port" --insecure
        log_ok "Spans loaded to Tempo via localhost:$otlp_port"
    else
        python3 -c "
from contextcore.demo import load_to_tempo
load_to_tempo(file='demo_output/demo_spans.json', endpoint='localhost:$otlp_port', insecure=True)
" 2>/dev/null || {
            log_warn "Could not load data via CLI or Python module"
            return 1
        }
        log_ok "Spans loaded to Tempo (via Python module)"
    fi

    # Verify data in Tempo
    local verify
    verify=$(curl -sf -u "$GRAFANA_AUTH" \
        "${GRAFANA_URL}/api/datasources/proxy/uid/tempo/api/search?tags=project.id%3Donline-boutique&limit=3" 2>/dev/null || echo "")

    if [ -n "$verify" ] && echo "$verify" | python3 -c "import sys, json; d=json.load(sys.stdin); sys.exit(0 if d.get('traces') else 1)" 2>/dev/null; then
        log_ok "Verified: traces found in Tempo"
    else
        log_warn "Could not verify traces in Tempo (may need a moment to index)"
    fi

    cd "$PROJECT_DIR"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Import Grafana dashboards
# ─────────────────────────────────────────────────────────────────────────────

import_dashboards() {
    log_step "Importing Grafana dashboards..."

    local imported=0
    local errors=0

    # Import from demo/dashboards/
    if [ -d "$CONTEXTCORE_DIR/demo/dashboards" ]; then
        for dashboard in "$CONTEXTCORE_DIR"/demo/dashboards/*.json; do
            [ -f "$dashboard" ] || continue
            local name
            name=$(basename "$dashboard")
            local result
            result=$(curl -sf -X POST \
                -H "Content-Type: application/json" \
                -u "$GRAFANA_AUTH" \
                -d "{\"dashboard\": $(cat "$dashboard"), \"overwrite\": true}" \
                "${GRAFANA_URL}/api/dashboards/db" 2>/dev/null || echo "ERROR")

            if echo "$result" | grep -q "success\|uid"; then
                log_info "Imported: $name"
                ((imported++))
            else
                log_warn "Failed to import: $name"
                ((errors++))
            fi
        done
    fi

    # Import from grafana/provisioning/dashboards/json/
    if [ -d "$CONTEXTCORE_DIR/grafana/provisioning/dashboards/json" ]; then
        for dashboard in "$CONTEXTCORE_DIR"/grafana/provisioning/dashboards/json/*.json; do
            [ -f "$dashboard" ] || continue
            local name
            name=$(basename "$dashboard")
            local result
            result=$(curl -sf -X POST \
                -H "Content-Type: application/json" \
                -u "$GRAFANA_AUTH" \
                -d "{\"dashboard\": $(cat "$dashboard"), \"overwrite\": true}" \
                "${GRAFANA_URL}/api/dashboards/db" 2>/dev/null || echo "ERROR")

            if echo "$result" | grep -q "success\|uid"; then
                log_info "Imported: $name"
                ((imported++))
            else
                log_warn "Failed to import: $name"
                ((errors++))
            fi
        done
    fi

    if [ "$imported" -gt 0 ]; then
        log_ok "Dashboards imported: $imported"
    else
        log_warn "No dashboards imported (check dashboard directories)"
    fi

    if [ "$errors" -gt 0 ]; then
        log_warn "Dashboard import errors: $errors"
    fi

    # List imported dashboards
    if [ "$VERBOSE" = true ]; then
        echo ""
        log_info "Installed dashboards:"
        curl -sf -u "$GRAFANA_AUTH" "${GRAFANA_URL}/api/search?type=dash-db" 2>/dev/null \
            | python3 -c "
import sys, json
dashboards = json.load(sys.stdin)
for d in dashboards:
    print(f'  - {d[\"title\"]} ({d.get(\"uid\", \"\")})')
" 2>/dev/null || log_info "(could not list dashboards)"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Create concept demo tasks
# ─────────────────────────────────────────────────────────────────────────────

create_concept_tasks() {
    log_step "Creating concept demo tasks..."

    python3 "$PROJECT_DIR/demo/setup_demo_tasks.py" --clean --concept-mode --verbose 2>/dev/null && {
        log_ok "Concept demo tasks created"
        return 0
    }

    # Fallback: create full demo tasks if --concept-mode not yet implemented
    python3 "$PROJECT_DIR/demo/setup_demo_tasks.py" --clean --verbose 2>/dev/null && {
        log_ok "Demo tasks created (full mode)"
        return 0
    }

    log_warn "Could not create demo tasks"
    return 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Final verification
# ─────────────────────────────────────────────────────────────────────────────

verify_setup() {
    log_step "Verifying setup..."

    local all_ok=true

    # Check Grafana dashboards
    local dashboard_count
    dashboard_count=$(curl -sf -u "$GRAFANA_AUTH" "${GRAFANA_URL}/api/search?type=dash-db" 2>/dev/null \
        | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    if [ "$dashboard_count" -gt 0 ]; then
        log_ok "Grafana dashboards: $dashboard_count"
    else
        log_warn "No dashboards found in Grafana"
        all_ok=false
    fi

    # Check demo task files
    local task_count
    task_count=$(ls ~/.contextcore/state/ecosystem-demo/*.json 2>/dev/null | wc -l | tr -d ' ')

    if [ "$task_count" -gt 0 ]; then
        log_ok "Demo tasks: $task_count"
    else
        log_warn "No demo tasks found"
        all_ok=false
    fi

    # Check Tempo data
    local trace_check
    trace_check=$(curl -sf -u "$GRAFANA_AUTH" \
        "${GRAFANA_URL}/api/datasources/proxy/uid/tempo/api/search?tags=project.id%3Donline-boutique&limit=1" 2>/dev/null || echo "")

    if [ -n "$trace_check" ]; then
        log_ok "Tempo data verified"
    else
        log_warn "Could not verify Tempo data"
        all_ok=false
    fi

    echo ""
    if [ "$all_ok" = true ]; then
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN} Demo environment ready!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "  Grafana:   $GRAFANA_URL"
        echo "  Portfolio: $GRAFANA_URL/d/portfolio/project-portfolio-overview"
        echo ""
        echo "  Start with: demo/CONCEPT_DEMO_RUNBOOK.md"
        echo "  Queries:    demo/DEMO_QUERIES.md"
        echo "  Personas:   demo/persona-views/"
    else
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW} Demo environment partially ready${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo ""
        echo "  Some components are not fully configured."
        echo "  Check warnings above and re-run as needed."
    fi
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

echo "========================================"
echo " Business Observability: Demo Setup"
echo "========================================"
echo ""
echo "  Project:      $PROJECT_DIR"
echo "  ContextCore:  $CONTEXTCORE_DIR"
echo "  Dev Root:     $DEV_ROOT"
echo ""

if [ "$CHECK_ONLY" = true ]; then
    check_prerequisites
    exit $?
fi

check_prerequisites || {
    echo ""
    log_fail "Prerequisites not met. Fix the issues above and re-run."
    exit 1
}

echo ""

if [ "$SKIP_DATA" = false ]; then
    generate_demo_data
fi

load_to_tempo
import_dashboards
create_concept_tasks
verify_setup
