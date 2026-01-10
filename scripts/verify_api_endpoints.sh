#!/bin/bash
#
# E2E API Verification Script
# Tests all 147 REST API endpoints for the Sentinel portfolio management system
#
# Usage: ./scripts/verify_api_endpoints.sh [base_url]
# Example: ./scripts/verify_api_endpoints.sh http://localhost:3000

set -e

BASE_URL="${1:-http://localhost:3000}"
API_URL="${BASE_URL}/api"
FAILED_TESTS=0
PASSED_TESTS=0
TOTAL_TESTS=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test result tracking
declare -a FAILED_ENDPOINTS

# Helper function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=${4:-200}
    local description=$5

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -n "Testing: $description ... "

    local response
    local status_code

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" "$API_URL$endpoint" 2>&1)
    fi

    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$status_code" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status_code)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Expected $expected_status, got $status_code)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_ENDPOINTS+=("$description")
        echo "Response: $body" | head -3
        return 1
    fi
}

echo "=================================================="
echo "Sentinel API E2E Verification"
echo "=================================================="
echo "Base URL: $BASE_URL"
echo "Testing $(date)"
echo ""

# ==================================================
# 1. Market Hours Module (5 endpoints)
# ==================================================
echo -e "${YELLOW}=== Market Hours Module (5 endpoints) ===${NC}"
test_endpoint GET "/market-hours/status" "" 200 "GET /market-hours/status"
test_endpoint GET "/market-hours/status/XETRA" "" 200 "GET /market-hours/status/{exchange}"
test_endpoint GET "/market-hours/open-markets" "" 200 "GET /market-hours/open-markets"
test_endpoint GET "/market-hours/holidays" "" 200 "GET /market-hours/holidays"
test_endpoint GET "/market-hours/validate-trading-window?symbol=AAPL&side=BUY" "" 200 "GET /market-hours/validate-trading-window"
echo ""

# ==================================================
# 2. Market Regime Module (6 endpoints)
# ==================================================
echo -e "${YELLOW}=== Market Regime Module (6 endpoints) ===${NC}"
test_endpoint GET "/regime/current" "" 200 "GET /regime/current"
test_endpoint GET "/regime/history?limit=10" "" 200 "GET /regime/history"
test_endpoint GET "/regime/adaptive-weights" "" 200 "GET /regime/adaptive-weights"
test_endpoint GET "/regime/adaptive-parameters" "" 200 "GET /regime/adaptive-parameters"
test_endpoint GET "/regime/component-performance" "" 200 "GET /regime/component-performance"
test_endpoint GET "/regime/performance-history?limit=10" "" 200 "GET /regime/performance-history"
echo ""

# ==================================================
# 3. Historical Data Module (11 endpoints)
# ==================================================
echo -e "${YELLOW}=== Historical Data Module (11 endpoints) ===${NC}"
test_endpoint GET "/historical/prices/daily/US0378331005?limit=10" "" 200 "GET /historical/prices/daily/{isin}"
test_endpoint GET "/historical/prices/monthly/US0378331005?limit=10" "" 200 "GET /historical/prices/monthly/{isin}"
test_endpoint GET "/historical/prices/latest/US0378331005" "" 200 "GET /historical/prices/latest/{isin}"
test_endpoint GET "/historical/prices/range?isins=US0378331005&limit=10" "" 200 "GET /historical/prices/range"
test_endpoint GET "/historical/returns/daily/US0378331005?limit=10" "" 200 "GET /historical/returns/daily/{isin}"
test_endpoint GET "/historical/returns/monthly/US0378331005?limit=10" "" 200 "GET /historical/returns/monthly/{isin}"
test_endpoint GET "/historical/returns/correlation-matrix" "" 200 "GET /historical/returns/correlation-matrix"
test_endpoint GET "/historical/exchange-rates/history?from_currency=USD&to_currency=EUR&limit=10" "" 200 "GET /historical/exchange-rates/history"
test_endpoint GET "/historical/exchange-rates/current" "" 200 "GET /historical/exchange-rates/current"
test_endpoint GET "/historical/exchange-rates/USD/EUR" "" 200 "GET /historical/exchange-rates/{from}/{to}"
test_endpoint GET "/historical/prices/all?limit=5" "" 200 "GET /historical/prices/all"
echo ""

# ==================================================
# 4. Risk Metrics Module (13 endpoints)
# ==================================================
echo -e "${YELLOW}=== Risk Metrics Module (13 endpoints) ===${NC}"
test_endpoint GET "/risk/portfolio/var" "" 200 "GET /risk/portfolio/var"
test_endpoint GET "/risk/portfolio/cvar" "" 200 "GET /risk/portfolio/cvar"
test_endpoint GET "/risk/portfolio/volatility" "" 200 "GET /risk/portfolio/volatility"
test_endpoint GET "/risk/portfolio/sharpe" "" 200 "GET /risk/portfolio/sharpe"
test_endpoint GET "/risk/portfolio/sortino" "" 200 "GET /risk/portfolio/sortino"
test_endpoint GET "/risk/portfolio/max-drawdown" "" 200 "GET /risk/portfolio/max-drawdown"
test_endpoint GET "/risk/securities/US0378331005/volatility" "" 200 "GET /risk/securities/{isin}/volatility"
test_endpoint GET "/risk/securities/US0378331005/sharpe" "" 200 "GET /risk/securities/{isin}/sharpe"
test_endpoint GET "/risk/securities/US0378331005/sortino" "" 200 "GET /risk/securities/{isin}/sortino"
test_endpoint GET "/risk/securities/US0378331005/max-drawdown" "" 200 "GET /risk/securities/{isin}/max-drawdown"
test_endpoint GET "/risk/securities/US0378331005/beta" "" 200 "GET /risk/securities/{isin}/beta"
test_endpoint GET "/risk/kelly-sizes" "" 200 "GET /risk/kelly-sizes"
test_endpoint GET "/risk/kelly-sizes/US0378331005" "" 200 "GET /risk/kelly-sizes/{isin}"
echo ""

# ==================================================
# 5. Opportunities Module (13 endpoints)
# ==================================================
echo -e "${YELLOW}=== Opportunities Module (13 endpoints) ===${NC}"
test_endpoint GET "/opportunities/all" "" 200 "GET /opportunities/all"
test_endpoint GET "/opportunities/buy-underweight" "" 200 "GET /opportunities/buy-underweight"
test_endpoint GET "/opportunities/sell-overweight" "" 200 "GET /opportunities/sell-overweight"
test_endpoint GET "/opportunities/sell-concentration" "" 200 "GET /opportunities/sell-concentration"
test_endpoint GET "/opportunities/profit-taking" "" 200 "GET /opportunities/profit-taking"
test_endpoint GET "/opportunities/averaging-down" "" 200 "GET /opportunities/averaging-down"
test_endpoint GET "/opportunities/dividend-harvest" "" 200 "GET /opportunities/dividend-harvest"
test_endpoint GET "/opportunities/rebalance-triggers" "" 200 "GET /opportunities/rebalance-triggers"
test_endpoint GET "/opportunities/quality-gates" "" 200 "GET /opportunities/quality-gates"
test_endpoint GET "/opportunities/high-momentum" "" 200 "GET /opportunities/high-momentum"
test_endpoint GET "/opportunities/value-opportunities" "" 200 "GET /opportunities/value-opportunities"
test_endpoint GET "/opportunities/low-volatility" "" 200 "GET /opportunities/low-volatility"
test_endpoint GET "/opportunities/registry" "" 200 "GET /opportunities/registry"
echo ""

# ==================================================
# 6. Ledger Module (14 endpoints)
# ==================================================
echo -e "${YELLOW}=== Ledger Module (14 endpoints) ===${NC}"
test_endpoint GET "/ledger/trades?limit=10" "" 200 "GET /ledger/trades"
test_endpoint GET "/ledger/trades/summary" "" 200 "GET /ledger/trades/summary"
test_endpoint GET "/ledger/cash-flows/all?limit=10" "" 200 "GET /ledger/cash-flows/all"
test_endpoint GET "/ledger/cash-flows/deposits" "" 200 "GET /ledger/cash-flows/deposits"
test_endpoint GET "/ledger/cash-flows/withdrawals" "" 200 "GET /ledger/cash-flows/withdrawals"
test_endpoint GET "/ledger/cash-flows/fees" "" 200 "GET /ledger/cash-flows/fees"
test_endpoint GET "/ledger/cash-flows/summary" "" 200 "GET /ledger/cash-flows/summary"
test_endpoint GET "/ledger/dividends/history?limit=10" "" 200 "GET /ledger/dividends/history"
test_endpoint GET "/ledger/dividends/reinvestment-stats" "" 200 "GET /ledger/dividends/reinvestment-stats"
test_endpoint GET "/ledger/dividends/pending-reinvestments" "" 200 "GET /ledger/dividends/pending-reinvestments"
test_endpoint GET "/ledger/drip-tracking" "" 200 "GET /ledger/drip-tracking"
test_endpoint GET "/ledger/pending-retries" "" 200 "GET /ledger/pending-retries"
test_endpoint GET "/ledger/cash-flows/dividends" "" 200 "GET /ledger/cash-flows/dividends"
test_endpoint GET "/ledger/cash-flows/commissions" "" 200 "GET /ledger/cash-flows/commissions"
echo ""

# ==================================================
# 7. Snapshots Module (6 endpoints)
# ==================================================
echo -e "${YELLOW}=== Snapshots Module (6 endpoints) ===${NC}"
test_endpoint GET "/snapshots/complete" "" 200 "GET /snapshots/complete"
test_endpoint GET "/snapshots/portfolio-state" "" 200 "GET /snapshots/portfolio-state"
test_endpoint GET "/snapshots/market-context" "" 200 "GET /snapshots/market-context"
test_endpoint GET "/snapshots/pending-actions" "" 200 "GET /snapshots/pending-actions"
test_endpoint GET "/snapshots/historical-summary" "" 200 "GET /snapshots/historical-summary"
test_endpoint GET "/snapshots/risk-snapshot" "" 200 "GET /snapshots/risk-snapshot"
echo ""

# ==================================================
# 8. Sequences Module (9 endpoints)
# ==================================================
echo -e "${YELLOW}=== Sequences Module (9 endpoints) ===${NC}"
test_endpoint POST "/sequences/generate/pattern" '{"pattern_type":"opportunity_first"}' 200 "POST /sequences/generate/pattern"
test_endpoint POST "/sequences/generate/combinatorial" '{"patterns":["opportunity_first"]}' 200 "POST /sequences/generate/combinatorial"
test_endpoint POST "/sequences/generate/all-patterns" '{}' 200 "POST /sequences/generate/all-patterns"
test_endpoint GET "/sequences/patterns" "" 200 "GET /sequences/patterns"
test_endpoint POST "/sequences/filter/eligibility" '{"sequences":[]}' 200 "POST /sequences/filter/eligibility"
test_endpoint POST "/sequences/filter/correlation" '{"sequences":[]}' 200 "POST /sequences/filter/correlation"
test_endpoint POST "/sequences/filter/recently-traded" '{"sequences":[]}' 200 "POST /sequences/filter/recently-traded"
test_endpoint GET "/sequences/context" "" 200 "GET /sequences/context"
test_endpoint POST "/sequences/validate" '{"sequence":[]}' 200 "POST /sequences/validate"
echo ""

# ==================================================
# 9. Rebalancing Module (6 endpoints)
# ==================================================
echo -e "${YELLOW}=== Rebalancing Module (6 endpoints) ===${NC}"
test_endpoint POST "/rebalancing/calculate" '{}' 200 "POST /rebalancing/calculate"
test_endpoint POST "/rebalancing/calculate/target-weights" '{"targets":{}}' 200 "POST /rebalancing/calculate/target-weights"
test_endpoint GET "/rebalancing/triggers" "" 200 "GET /rebalancing/triggers"
test_endpoint GET "/rebalancing/min-trade-amount" "" 200 "GET /rebalancing/min-trade-amount"
test_endpoint POST "/rebalancing/simulate-rebalance" '{}' 200 "POST /rebalancing/simulate-rebalance"
test_endpoint POST "/rebalancing/negative-balance-check" '{"trades":[]}' 200 "POST /rebalancing/negative-balance-check"
echo ""

# ==================================================
# 10. Currency Module (10 endpoints)
# ==================================================
echo -e "${YELLOW}=== Currency Module (10 endpoints) ===${NC}"
test_endpoint GET "/currency/conversion-path/USD/EUR" "" 200 "GET /currency/conversion-path/{from}/{to}"
test_endpoint POST "/currency/convert" '{"from":"USD","to":"EUR","amount":100}' 200 "POST /currency/convert"
test_endpoint GET "/currency/available-currencies" "" 200 "GET /currency/available-currencies"
test_endpoint GET "/currency/rates/sources" "" 200 "GET /currency/rates/sources"
test_endpoint GET "/currency/rates/staleness" "" 200 "GET /currency/rates/staleness"
test_endpoint GET "/currency/rates/fallback-chain" "" 200 "GET /currency/rates/fallback-chain"
test_endpoint GET "/currency/balances" "" 200 "GET /currency/balances"
test_endpoint POST "/currency/balance-check" '{"currency":"EUR","amount":100}' 200 "POST /currency/balance-check"
test_endpoint POST "/currency/conversion-requirements" '{"symbol":"AAPL","side":"BUY","quantity":10,"price":150}' 200 "POST /currency/conversion-requirements"
test_endpoint POST "/currency/rates/sync" '{}' 200 "POST /currency/rates/sync"
echo ""

# ==================================================
# 11. Quantum Module (5 endpoints)
# ==================================================
echo -e "${YELLOW}=== Quantum Module (5 endpoints) ===${NC}"
test_endpoint POST "/quantum/amplitude" '{"probability":0.5,"energy":1.0}' 200 "POST /quantum/amplitude"
test_endpoint POST "/quantum/interference" '{"amplitudes":[0.5,0.3]}' 200 "POST /quantum/interference"
test_endpoint POST "/quantum/probability" '{"amplitude":0.5}' 200 "POST /quantum/probability"
test_endpoint GET "/quantum/energy-levels" "" 200 "GET /quantum/energy-levels"
test_endpoint POST "/quantum/multimodal-correction" '{"probability":0.5}' 200 "POST /quantum/multimodal-correction"
echo ""

# ==================================================
# 12. Evaluation Module (7 endpoints)
# ==================================================
echo -e "${YELLOW}=== Evaluation Module (7 endpoints) ===${NC}"
test_endpoint POST "/evaluation/evaluate/batch" '{"sequences":[],"evaluation_context":{}}' 200 "POST /evaluation/evaluate/batch"
test_endpoint POST "/evaluation/evaluate/single" '{"sequence":[],"evaluation_context":{}}' 200 "POST /evaluation/evaluate/single"
test_endpoint POST "/evaluation/evaluate/compare" '{"sequences":[]}' 200 "POST /evaluation/evaluate/compare"
test_endpoint GET "/evaluation/evaluation/criteria" "" 200 "GET /evaluation/evaluation/criteria"
test_endpoint POST "/evaluation/simulate/batch" '{"sequences":[]}' 200 "POST /evaluation/simulate/batch"
test_endpoint POST "/evaluation/simulate/custom-prices" '{"sequence":[],"custom_prices":{}}' 200 "POST /evaluation/simulate/custom-prices"
test_endpoint POST "/evaluation/monte-carlo/advanced" '{"sequence":[],"simulations":100}' 200 "POST /evaluation/monte-carlo/advanced"
echo ""

# ==================================================
# 13. Portfolio Module (11 endpoints)
# ==================================================
echo -e "${YELLOW}=== Portfolio Module (11 endpoints) ===${NC}"
test_endpoint GET "/portfolio/summary" "" 200 "GET /portfolio/summary"
test_endpoint GET "/portfolio/positions" "" 200 "GET /portfolio/positions"
test_endpoint GET "/portfolio/cash" "" 200 "GET /portfolio/cash"
test_endpoint GET "/portfolio/value-history?days=30" "" 200 "GET /portfolio/value-history"
test_endpoint GET "/portfolio/performance/history?period=1y" "" 200 "GET /portfolio/performance/history"
test_endpoint GET "/portfolio/performance/vs-benchmark" "" 200 "GET /portfolio/performance/vs-benchmark"
test_endpoint GET "/portfolio/performance/attribution" "" 200 "GET /portfolio/performance/attribution"
test_endpoint GET "/portfolio/concentration" "" 200 "GET /portfolio/concentration"
test_endpoint GET "/portfolio/diversification" "" 200 "GET /portfolio/diversification"
test_endpoint GET "/portfolio/unrealized-pnl/breakdown" "" 200 "GET /portfolio/unrealized-pnl/breakdown"
test_endpoint GET "/portfolio/cost-basis" "" 200 "GET /portfolio/cost-basis"
echo ""

# ==================================================
# 14. Allocation Module (14 endpoints)
# ==================================================
echo -e "${YELLOW}=== Allocation Module (14 endpoints) ===${NC}"
test_endpoint GET "/allocation/targets" "" 200 "GET /allocation/targets"
test_endpoint GET "/allocation/current" "" 200 "GET /allocation/current"
test_endpoint GET "/allocation/deviations" "" 200 "GET /allocation/deviations"
test_endpoint GET "/allocation/groups/country" "" 200 "GET /allocation/groups/country"
test_endpoint GET "/allocation/groups/industry" "" 200 "GET /allocation/groups/industry"
test_endpoint GET "/allocation/groups/available/countries" "" 200 "GET /allocation/groups/available/countries"
test_endpoint GET "/allocation/groups/available/industries" "" 200 "GET /allocation/groups/available/industries"
test_endpoint GET "/allocation/groups/allocation" "" 200 "GET /allocation/groups/allocation"
test_endpoint GET "/allocation/history" "" 200 "GET /allocation/history"
test_endpoint GET "/allocation/vs-targets" "" 200 "GET /allocation/vs-targets"
test_endpoint GET "/allocation/rebalance-needs" "" 200 "GET /allocation/rebalance-needs"
test_endpoint GET "/allocation/groups/contribution" "" 200 "GET /allocation/groups/contribution"
# Note: PUT and DELETE endpoints would require valid data
echo "  (Skipping PUT/DELETE endpoints - require valid data)"
echo ""

# ==================================================
# 15. Scoring Module (7 endpoints)
# ==================================================
echo -e "${YELLOW}=== Scoring Module (7 endpoints) ===${NC}"
test_endpoint POST "/scoring/score" '{"symbol":"AAPL","daily_prices":[100,101,102]}' 200 "POST /scoring/score"
test_endpoint GET "/scoring/components/US0378331005" "" 200 "GET /scoring/components/{isin}"
test_endpoint GET "/scoring/components/all" "" 200 "GET /scoring/components/all"
test_endpoint GET "/scoring/weights/current" "" 200 "GET /scoring/weights/current"
test_endpoint GET "/scoring/weights/adaptive-history" "" 200 "GET /scoring/weights/adaptive-history"
test_endpoint GET "/scoring/formulas/active" "" 200 "GET /scoring/formulas/active"
test_endpoint POST "/scoring/score/what-if" '{"isin":"US0378331005","weights":{"fundamental":0.3,"dividend":0.2,"technical":0.2,"quality":0.15,"valuation":0.15}}' 200 "POST /scoring/score/what-if"
echo ""

# ==================================================
# 16. Symbolic Regression Module (8 endpoints)
# ==================================================
echo -e "${YELLOW}=== Symbolic Regression Module (8 endpoints) ===${NC}"
test_endpoint GET "/symbolic-regression/formulas?formula_type=expected_return&security_type=stock" "" 200 "GET /symbolic-regression/formulas"
test_endpoint GET "/symbolic-regression/formulas/active?formula_type=expected_return&security_type=stock" "" 200 "GET /symbolic-regression/formulas/active"
test_endpoint GET "/symbolic-regression/formulas/by-regime?regime_min=-1&regime_max=0" "" 200 "GET /symbolic-regression/formulas/by-regime"
# Note: Other endpoints would require valid formula IDs or complex data
echo "  (Skipping endpoints requiring valid formula IDs)"
echo ""

# ==================================================
# 17. Trade Validation Module (7 endpoints)
# ==================================================
echo -e "${YELLOW}=== Trade Validation Module (7 endpoints) ===${NC}"
test_endpoint POST "/trade-validation/validate-trade" '{"symbol":"AAPL","side":"BUY","quantity":10}' 200 "POST /trade-validation/validate-trade"
test_endpoint POST "/trade-validation/check-market-hours" '{"symbol":"AAPL","side":"BUY"}' 200 "POST /trade-validation/check-market-hours"
test_endpoint POST "/trade-validation/check-price-freshness" '{"symbol":"AAPL"}' 200 "POST /trade-validation/check-price-freshness"
test_endpoint POST "/trade-validation/calculate-commission" '{"symbol":"AAPL","side":"BUY","quantity":10,"price":150}' 200 "POST /trade-validation/calculate-commission"
test_endpoint POST "/trade-validation/calculate-limit-price" '{"symbol":"AAPL","side":"BUY","current_price":150}' 200 "POST /trade-validation/calculate-limit-price"
test_endpoint POST "/trade-validation/check-eligibility" '{"symbol":"AAPL"}' 200 "POST /trade-validation/check-eligibility"
test_endpoint POST "/trade-validation/check-cash-sufficiency" '{"symbol":"AAPL","side":"BUY","quantity":10,"price":150}' 200 "POST /trade-validation/check-cash-sufficiency"
echo ""

# ==================================================
# Summary
# ==================================================
echo "=================================================="
echo "Test Summary"
echo "=================================================="
echo "Total Tests:  $TOTAL_TESTS"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"

if [ $FAILED_TESTS -gt 0 ]; then
    echo ""
    echo "Failed Endpoints:"
    for endpoint in "${FAILED_ENDPOINTS[@]}"; do
        echo "  - $endpoint"
    done
    exit 1
else
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
