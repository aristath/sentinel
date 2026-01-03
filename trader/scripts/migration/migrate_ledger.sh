#!/bin/bash

# Ledger DB Expansion Script
# Merges dividends.db → ledger.db

set -euo pipefail

DATA_DIR="${1:-.}"

echo "[Ledger Migration] Starting..."
echo "[Ledger Migration] Data directory: $DATA_DIR"

cd "$DATA_DIR"

# Check if ledger.db exists
if [ ! -f "ledger.db" ]; then
    echo "[Ledger Migration] Creating ledger.db..."
    sqlite3 ledger.db < /dev/null
fi

# Run the ledger schema migration
echo "[Ledger Migration] Running schema migration..."
sqlite3 ledger.db < ../../trader/internal/database/migrations/010_ledger_expanded.sql

# Migrate dividend data from dividends.db if it exists
if [ -f "dividends.db" ]; then
    echo "[Ledger Migration] Copying dividend_history from dividends.db..."

    # Check if dividend_history table exists in dividends.db
    if sqlite3 dividends.db "SELECT name FROM sqlite_master WHERE type='table' AND name='dividend_history'" | grep -q dividend_history; then
        sqlite3 dividends.db ".dump dividend_history" | grep -v "^CREATE TABLE" | sqlite3 ledger.db
        DIVIDENDS_COUNT=$(sqlite3 ledger.db "SELECT COUNT(*) FROM dividend_history")
        echo "[Ledger Migration] Dividend history records migrated: $DIVIDENDS_COUNT"
    fi

    # Check for drip_tracking table
    if sqlite3 dividends.db "SELECT name FROM sqlite_master WHERE type='table' AND name='drip_tracking'" | grep -q drip_tracking; then
        echo "[Ledger Migration] Copying drip_tracking from dividends.db..."
        sqlite3 dividends.db ".dump drip_tracking" | grep -v "^CREATE TABLE" | sqlite3 ledger.db
        DRIP_COUNT=$(sqlite3 ledger.db "SELECT COUNT(*) FROM drip_tracking")
        echo "[Ledger Migration] DRIP tracking records migrated: $DRIP_COUNT"
    fi
else
    echo "[Ledger Migration] No dividends.db found, skipping dividend migration"
fi

# Verify trades table exists and has data
TRADES_COUNT=$(sqlite3 ledger.db "SELECT COUNT(*) FROM trades" 2>/dev/null || echo "0")
echo "[Ledger Migration] Trades in ledger.db: $TRADES_COUNT"

# Integrity check
INTEGRITY=$(sqlite3 ledger.db "PRAGMA integrity_check")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[Ledger Migration] ERROR: Integrity check failed: $INTEGRITY"
    exit 1
fi

echo "[Ledger Migration] ✅ Complete"
