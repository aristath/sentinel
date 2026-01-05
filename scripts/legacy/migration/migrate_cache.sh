#!/bin/bash

# Cache DB Migration Script
# Moves recommendations from config.db → cache.db

set -euo pipefail

DATA_DIR="${1:-.}"

echo "[Cache Migration] Starting..."
echo "[Cache Migration] Data directory: $DATA_DIR"

cd "$DATA_DIR"

# Check if cache.db already exists
if [ -f "cache.db" ]; then
    echo "[Cache Migration] WARNING: cache.db already exists, will be overwritten"
    rm -f cache.db cache.db-wal cache.db-shm
fi

# Create cache.db and run migrations
echo "[Cache Migration] Creating cache.db..."
sqlite3 cache.db < /dev/null

# Run the cache schema migration
echo "[Cache Migration] Running schema migration..."
sqlite3 cache.db < ../../trader/internal/database/migrations/008_cache_schema.sql

# Check if recommendations exist in config.db
if [ -f "config.db" ]; then
    if sqlite3 config.db "SELECT name FROM sqlite_master WHERE type='table' AND name='recommendations'" | grep -q recommendations; then
        echo "[Cache Migration] Copying recommendations from config.db..."
        sqlite3 config.db ".dump recommendations" | grep -v "^CREATE TABLE" | sqlite3 cache.db
        RECOMMENDATIONS_COUNT=$(sqlite3 cache.db "SELECT COUNT(*) FROM recommendations")
        echo "[Cache Migration] Recommendations migrated: $RECOMMENDATIONS_COUNT"
    else
        echo "[Cache Migration] No recommendations table found in config.db"
    fi
fi

# Check if recommendations.db exists (old standalone file)
if [ -f "recommendations.db" ]; then
    echo "[Cache Migration] Found standalone recommendations.db..."
    if sqlite3 recommendations.db "SELECT name FROM sqlite_master WHERE type='table' AND name='recommendations'" | grep -q recommendations; then
        echo "[Cache Migration] Copying recommendations from recommendations.db..."
        # Clear any existing data first
        sqlite3 cache.db "DELETE FROM recommendations"
        sqlite3 recommendations.db ".dump recommendations" | grep -v "^CREATE TABLE" | sqlite3 cache.db
        RECOMMENDATIONS_COUNT=$(sqlite3 cache.db "SELECT COUNT(*) FROM recommendations")
        echo "[Cache Migration] Recommendations migrated: $RECOMMENDATIONS_COUNT"
    fi
fi

# Integrity check
INTEGRITY=$(sqlite3 cache.db "PRAGMA integrity_check")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[Cache Migration] ERROR: Integrity check failed: $INTEGRITY"
    exit 1
fi

echo "[Cache Migration] ✅ Complete"
