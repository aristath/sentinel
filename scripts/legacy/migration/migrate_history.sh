#!/bin/bash

# History DB Consolidation Script
# Consolidates history/*.db (65+ files) → history.db

set -euo pipefail

DATA_DIR="${1:-.}"

echo "[History Migration] Starting..."
echo "[History Migration] Data directory: $DATA_DIR"

cd "$DATA_DIR"

# Check if history.db already exists
if [ -f "history.db" ]; then
    echo "[History Migration] WARNING: history.db already exists, will be overwritten"
    rm -f history.db history.db-wal history.db-shm
fi

# Create history.db and run migrations
echo "[History Migration] Creating history.db..."
sqlite3 history.db < /dev/null

# Run the history schema migration
echo "[History Migration] Running schema migration..."
sqlite3 history.db < ../../trader/internal/database/migrations/006_history_schema.sql

# Check if history directory exists
if [ ! -d "history" ]; then
    echo "[History Migration] No history directory found, skipping price data migration"
    echo "[History Migration] ✅ Complete (no data to migrate)"
    exit 0
fi

# Count files to migrate
HISTORY_FILE_COUNT=$(find history -name "*.db" -type f | wc -l)
echo "[History Migration] Found $HISTORY_FILE_COUNT database files to consolidate"

if [ "$HISTORY_FILE_COUNT" -eq 0 ]; then
    echo "[History Migration] No database files found in history directory"
    echo "[History Migration] ✅ Complete (no data to migrate)"
    exit 0
fi

# Migrate each symbol's history database
MIGRATED=0
ERRORS=0

for db_file in history/*.db; do
    # Extract symbol from filename (e.g., "AAPL_US.db" → "AAPL.US")
    filename=$(basename "$db_file" .db)
    symbol=$(echo "$filename" | sed 's/_/./g')

    echo "[History Migration] Processing $symbol..."

    # Check if daily_prices table exists
    if ! sqlite3 "$db_file" "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_prices'" | grep -q daily_prices; then
        echo "[History Migration]   WARNING: No daily_prices table in $db_file, skipping"
        continue
    fi

    # Count rows in source
    SOURCE_COUNT=$(sqlite3 "$db_file" "SELECT COUNT(*) FROM daily_prices" 2>/dev/null || echo "0")

    if [ "$SOURCE_COUNT" -eq 0 ]; then
        echo "[History Migration]   No data for $symbol, skipping"
        continue
    fi

    # Insert data with symbol column
    sqlite3 "$db_file" "SELECT '$symbol', date, close_price, open_price, high_price, low_price, volume, source FROM daily_prices" | \
    sqlite3 history.db "BEGIN TRANSACTION; \
        $(cat <<'SQL'
.mode csv
.import /dev/stdin temp_import
INSERT INTO daily_prices (symbol, date, close_price, open_price, high_price, low_price, volume, source)
SELECT * FROM temp_import;
DROP TABLE temp_import;
COMMIT;
SQL
)" 2>/dev/null

    # Verify data was inserted
    DEST_COUNT=$(sqlite3 history.db "SELECT COUNT(*) FROM daily_prices WHERE symbol = '$symbol'" 2>/dev/null || echo "0")

    if [ "$SOURCE_COUNT" -eq "$DEST_COUNT" ]; then
        echo "[History Migration]   ✅ $symbol: $DEST_COUNT rows migrated"
        ((MIGRATED++))
    else
        echo "[History Migration]   ⚠️  $symbol: Count mismatch (source: $SOURCE_COUNT, dest: $DEST_COUNT)"
        ((ERRORS++))
    fi
done

# Integrity check
INTEGRITY=$(sqlite3 history.db "PRAGMA integrity_check")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[History Migration] ERROR: Integrity check failed: $INTEGRITY"
    exit 1
fi

# Get total row count
TOTAL_ROWS=$(sqlite3 history.db "SELECT COUNT(*) FROM daily_prices")
UNIQUE_SYMBOLS=$(sqlite3 history.db "SELECT COUNT(DISTINCT symbol) FROM daily_prices")

echo "[History Migration] ============================================"
echo "[History Migration] Migration Summary:"
echo "[History Migration] - Symbols migrated: $MIGRATED"
echo "[History Migration] - Errors: $ERRORS"
echo "[History Migration] - Total price records: $TOTAL_ROWS"
echo "[History Migration] - Unique symbols: $UNIQUE_SYMBOLS"
echo "[History Migration] ============================================"

if [ "$ERRORS" -gt 0 ]; then
    echo "[History Migration] ⚠️  Complete with warnings"
    exit 0
else
    echo "[History Migration] ✅ Complete"
fi
