#!/bin/bash

# Universe DB Migration Script
# Splits config.db → universe.db (securities, groups) + config.db (settings, targets)

set -euo pipefail

DATA_DIR="${1:-.}"

echo "[Universe Migration] Starting..."
echo "[Universe Migration] Data directory: $DATA_DIR"

cd "$DATA_DIR"

# Check if source database exists
if [ ! -f "config.db" ]; then
    echo "[Universe Migration] ERROR: config.db not found"
    exit 1
fi

# Check if universe.db already exists
if [ -f "universe.db" ]; then
    echo "[Universe Migration] WARNING: universe.db already exists, will be overwritten"
    rm -f universe.db universe.db-wal universe.db-shm
fi

# Create universe.db and run migrations
echo "[Universe Migration] Creating universe.db..."
sqlite3 universe.db < /dev/null

# Run the universe schema migration
echo "[Universe Migration] Running schema migration..."
sqlite3 universe.db < ../../trader/internal/database/migrations/003_universe_schema.sql

# Copy securities data from config.db to universe.db
echo "[Universe Migration] Copying securities table..."
sqlite3 config.db ".dump securities" | grep -v "^CREATE TABLE" | sqlite3 universe.db

# Copy country_groups if it exists
if sqlite3 config.db "SELECT name FROM sqlite_master WHERE type='table' AND name='country_groups'" | grep -q country_groups; then
    echo "[Universe Migration] Copying country_groups table..."
    sqlite3 config.db ".dump country_groups" | grep -v "^CREATE TABLE" | sqlite3 universe.db
fi

# Copy industry_groups if it exists
if sqlite3 config.db "SELECT name FROM sqlite_master WHERE type='table' AND name='industry_groups'" | grep -q industry_groups; then
    echo "[Universe Migration] Copying industry_groups table..."
    sqlite3 config.db ".dump industry_groups" | grep -v "^CREATE TABLE" | sqlite3 universe.db
fi

# Verify data copied correctly
SECURITIES_COUNT_SOURCE=$(sqlite3 config.db "SELECT COUNT(*) FROM securities" 2>/dev/null || echo "0")
SECURITIES_COUNT_DEST=$(sqlite3 universe.db "SELECT COUNT(*) FROM securities" 2>/dev/null || echo "0")

echo "[Universe Migration] Source securities: $SECURITIES_COUNT_SOURCE"
echo "[Universe Migration] Destination securities: $SECURITIES_COUNT_DEST"

if [ "$SECURITIES_COUNT_SOURCE" != "$SECURITIES_COUNT_DEST" ]; then
    echo "[Universe Migration] ERROR: Row count mismatch!"
    exit 1
fi

# Integrity check
INTEGRITY=$(sqlite3 universe.db "PRAGMA integrity_check")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[Universe Migration] ERROR: Integrity check failed: $INTEGRITY"
    exit 1
fi

echo "[Universe Migration] ✅ Complete"
echo "[Universe Migration] Securities migrated: $SECURITIES_COUNT_DEST"
