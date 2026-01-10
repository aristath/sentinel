#!/bin/bash
#
# API Performance Benchmark Script
# Benchmarks critical API endpoints for the Sentinel portfolio management system
#
# Usage: ./scripts/benchmark_api.sh [base_url] [requests_per_endpoint]
# Example: ./scripts/benchmark_api.sh http://localhost:3000 1000

set -e

BASE_URL="${1:-http://localhost:3000}"
API_URL="${BASE_URL}/api"
REQUESTS="${2:-100}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Sentinel API Performance Benchmark"
echo "=================================================="
echo "Base URL: $BASE_URL"
echo "Requests per endpoint: $REQUESTS"
echo "Benchmarking $(date)"
echo ""

# Check if ApacheBench (ab) is available
if ! command -v ab &> /dev/null; then
    echo "Error: ApacheBench (ab) is required but not installed."
    echo "Install with: brew install httpd (macOS) or apt-get install apache2-utils (Linux)"
    exit 1
fi

# Helper function to benchmark an endpoint
benchmark_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    local concurrent=${5:-10}

    echo -e "${YELLOW}Benchmarking: $description${NC}"

    if [ "$method" = "GET" ]; then
        ab -n "$REQUESTS" -c "$concurrent" -q "$API_URL$endpoint" 2>&1 | grep -E "(Requests per second|Time per request|Transfer rate)" || true
    else
        # For POST endpoints, create temporary file with data
        temp_file=$(mktemp)
        echo "$data" > "$temp_file"
        ab -n "$REQUESTS" -c "$concurrent" -q -p "$temp_file" -T "application/json" "$API_URL$endpoint" 2>&1 | grep -E "(Requests per second|Time per request|Transfer rate)" || true
        rm -f "$temp_file"
    fi

    echo ""
}

# ==================================================
# Critical Read Endpoints (High Frequency)
# ==================================================
echo -e "${GREEN}=== Critical Read Endpoints (High Frequency) ===${NC}"
echo ""

benchmark_endpoint GET "/portfolio/summary" "" "Portfolio Summary"
benchmark_endpoint GET "/portfolio/positions" "" "Portfolio Positions"
benchmark_endpoint GET "/market-hours/status" "" "Market Hours Status"
benchmark_endpoint GET "/opportunities/all" "" "All Opportunities"
benchmark_endpoint GET "/allocation/current" "" "Current Allocation"

# ==================================================
# Data Aggregation Endpoints (Medium Frequency)
# ==================================================
echo -e "${GREEN}=== Data Aggregation Endpoints (Medium Frequency) ===${NC}"
echo ""

benchmark_endpoint GET "/snapshots/portfolio-state" "" "Portfolio State Snapshot"
benchmark_endpoint GET "/snapshots/market-context" "" "Market Context Snapshot"
benchmark_endpoint GET "/risk/portfolio/cvar" "" "Portfolio CVaR"
benchmark_endpoint GET "/ledger/trades?limit=100" "" "Trade History (100 records)"
benchmark_endpoint GET "/historical/prices/daily/US0378331005?limit=30" "" "Daily Prices (30 days)"

# ==================================================
# Computational Endpoints (Lower Frequency, Higher Complexity)
# ==================================================
echo -e "${GREEN}=== Computational Endpoints (Lower Frequency) ===${NC}"
echo ""

benchmark_endpoint GET "/historical/returns/correlation-matrix" "" "Correlation Matrix"
benchmark_endpoint GET "/risk/portfolio/var" "" "Portfolio VaR"
benchmark_endpoint GET "/portfolio/performance/attribution" "" "Performance Attribution"
benchmark_endpoint GET "/allocation/rebalance-needs" "" "Rebalancing Needs"
benchmark_endpoint POST "/sequences/generate/pattern" '{"pattern_type":"opportunity_first"}' "Sequence Generation"

# ==================================================
# Validation Endpoints (Pre-Trade)
# ==================================================
echo -e "${GREEN}=== Validation Endpoints (Pre-Trade) ===${NC}"
echo ""

benchmark_endpoint POST "/trade-validation/validate-trade" '{"symbol":"AAPL","side":"BUY","quantity":10}' "Trade Validation"
benchmark_endpoint POST "/trade-validation/calculate-commission" '{"symbol":"AAPL","side":"BUY","quantity":10,"price":150}' "Commission Calculation"
benchmark_endpoint POST "/trade-validation/check-cash-sufficiency" '{"symbol":"AAPL","side":"BUY","quantity":10,"price":150}' "Cash Sufficiency Check"

# ==================================================
# Heavy Computation Endpoints (Background Jobs)
# ==================================================
echo -e "${GREEN}=== Heavy Computation Endpoints (Background) ===${NC}"
echo ""

benchmark_endpoint POST "/evaluation/evaluate/batch" '{"sequences":[],"evaluation_context":{}}' "Batch Evaluation (Empty)"
benchmark_endpoint POST "/rebalancing/calculate" '{}' "Rebalancing Calculation"
benchmark_endpoint POST "/currency/convert" '{"from":"USD","to":"EUR","amount":1000}' "Currency Conversion"

# ==================================================
# Summary
# ==================================================
echo "=================================================="
echo "Benchmark Complete"
echo "=================================================="
echo "Date: $(date)"
echo ""
echo "Performance Targets:"
echo "  - Critical reads: <50ms p95"
echo "  - Data aggregation: <200ms p95"
echo "  - Computational: <500ms p95"
echo "  - Heavy computation: <2s p95"
echo ""
echo "Note: Run with higher request count for more accurate results:"
echo "  ./scripts/benchmark_api.sh http://localhost:3000 1000"
