#!/bin/bash

# Migration Verification Script
# Comprehensive verification of data migration accuracy

set -euo pipefail

DATA_DIR="${1:-.}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}Database Migration Verification${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

cd "$DATA_DIR"

ERRORS=0
WARNINGS=0

# Helper functions
check_count() {
    local db="$1"
    local table="$2"
    local description="$3"

    if [ ! -f "$db" ]; then
        echo -e "${RED}✗ $db not found${NC}"
        ((ERRORS++))
        return
    fi

    local count=$(sqlite3 "$db" "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "ERROR")

    if [ "$count" == "ERROR" ]; then
        echo -e "${RED}✗ $description: Table $table not found in $db${NC}"
        ((ERRORS++))
    elif [ "$count" -eq 0 ]; then
        echo -e "${YELLOW}⚠ $description: 0 rows (might be expected)${NC}"
        ((WARNINGS++))
    else
        echo -e "${GREEN}✓ $description: $count rows${NC}"
    fi
}

check_integrity() {
    local db="$1"

    if [ ! -f "$db" ]; then
        echo -e "${RED}✗ $db not found${NC}"
        ((ERRORS++))
        return
    fi

    local result=$(sqlite3 "$db" "PRAGMA integrity_check" 2>/dev/null || echo "ERROR")

    if [ "$result" == "ok" ]; then
        echo -e "${GREEN}✓ $db integrity: OK${NC}"
    else
        echo -e "${RED}✗ $db integrity check failed: $result${NC}"
        ((ERRORS++))
    fi
}

compare_counts() {
    local old_db="$1"
    local old_table="$2"
    local new_db="$3"
    local new_table="$4"
    local description="$5"

    if [ ! -f "$old_db" ]; then
        echo -e "${YELLOW}⚠ $description: Source database $old_db not found (skipping comparison)${NC}"
        ((WARNINGS++))
        return
    fi

    local old_count=$(sqlite3 "$old_db" "SELECT COUNT(*) FROM $old_table" 2>/dev/null || echo "0")
    local new_count=$(sqlite3 "$new_db" "SELECT COUNT(*) FROM $new_table" 2>/dev/null || echo "0")

    if [ "$old_count" -eq "$new_count" ]; then
        echo -e "${GREEN}✓ $description: $old_count → $new_count (match)${NC}"
    else
        echo -e "${RED}✗ $description: $old_count → $new_count (MISMATCH)${NC}"
        ((ERRORS++))
    fi
}

echo -e "${BLUE}=== 1. UNIVERSE.DB ===${NC}"
check_integrity "universe.db"
check_count "universe.db" "securities" "Securities"
check_count "universe.db" "country_groups" "Country groups"
check_count "universe.db" "industry_groups" "Industry groups"
compare_counts "config.db" "securities" "universe.db" "securities" "Securities migration"
echo ""

echo -e "${BLUE}=== 2. CONFIG.DB ===${NC}"
check_integrity "config.db"
check_count "config.db" "settings" "Settings"
check_count "config.db" "allocation_targets" "Allocation targets"
echo ""

echo -e "${BLUE}=== 3. LEDGER.DB ===${NC}"
check_integrity "ledger.db"
check_count "ledger.db" "trades" "Trades"
check_count "ledger.db" "cash_flows" "Cash flows"
check_count "ledger.db" "dividend_history" "Dividend history"
compare_counts "dividends.db" "dividend_history" "ledger.db" "dividend_history" "Dividend migration"
echo ""

echo -e "${BLUE}=== 4. PORTFOLIO.DB ===${NC}"
check_integrity "portfolio.db"
check_count "portfolio.db" "positions" "Positions"
check_count "portfolio.db" "scores" "Scores"
check_count "portfolio.db" "portfolio_snapshots" "Portfolio snapshots"
compare_counts "state.db" "positions" "portfolio.db" "positions" "Positions migration"
compare_counts "state.db" "scores" "portfolio.db" "scores" "Scores migration"
echo ""

echo -e "${BLUE}=== 5. SATELLITES.DB ===${NC}"
check_integrity "satellites.db"
check_count "satellites.db" "buckets" "Buckets"
check_count "satellites.db" "bucket_balances" "Bucket balances"
echo ""

echo -e "${BLUE}=== 6. AGENTS.DB ===${NC}"
check_integrity "agents.db"
check_count "agents.db" "agent_configs" "Agent configs"
check_count "agents.db" "sequences" "Sequences"
echo ""

echo -e "${BLUE}=== 7. HISTORY.DB ===${NC}"
check_integrity "history.db"
check_count "history.db" "daily_prices" "Daily prices"

if [ -f "history.db" ]; then
    UNIQUE_SYMBOLS=$(sqlite3 history.db "SELECT COUNT(DISTINCT symbol) FROM daily_prices" 2>/dev/null || echo "0")
    echo -e "${GREEN}  Unique symbols: $UNIQUE_SYMBOLS${NC}"

    if [ -d "history" ]; then
        HISTORY_FILE_COUNT=$(find history -name "*.db" -type f | wc -l)
        echo -e "${BLUE}  Source files: $HISTORY_FILE_COUNT${NC}"

        if [ "$UNIQUE_SYMBOLS" -ne "$HISTORY_FILE_COUNT" ]; then
            echo -e "${YELLOW}  ⚠ Symbol count doesn't match file count${NC}"
            ((WARNINGS++))
        fi
    fi
fi
echo ""

echo -e "${BLUE}=== 8. CACHE.DB ===${NC}"
check_integrity "cache.db"
check_count "cache.db" "recommendations" "Recommendations"
echo ""

# Summary
echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}=======================================${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}✓ Passed with $WARNINGS warnings${NC}"
    exit 0
else
    echo -e "${RED}✗ Failed with $ERRORS errors and $WARNINGS warnings${NC}"
    exit 1
fi
