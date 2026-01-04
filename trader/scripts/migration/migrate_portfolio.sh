#!/bin/bash

# Portfolio DB Consolidation Script
# Consolidates state.db + calculations.db + snapshots.db → portfolio.db

set -euo pipefail

DATA_DIR="${1:-.}"

echo "[Portfolio Migration] Starting..."
echo "[Portfolio Migration] Data directory: $DATA_DIR"

cd "$DATA_DIR"

# Check if portfolio.db already exists
if [ -f "portfolio.db" ]; then
    echo "[Portfolio Migration] WARNING: portfolio.db already exists, will be overwritten"
    rm -f portfolio.db portfolio.db-wal portfolio.db-shm
fi

# Create portfolio.db and run migrations
echo "[Portfolio Migration] Creating portfolio.db..."
sqlite3 portfolio.db < /dev/null

# Run the portfolio schema migration
echo "[Portfolio Migration] Running schema migration..."
sqlite3 portfolio.db < ../../trader/internal/database/migrations/004_portfolio_schema.sql

# Migrate positions from state.db
if [ -f "state.db" ]; then
    echo "[Portfolio Migration] Copying positions from state.db..."
    if sqlite3 state.db "SELECT name FROM sqlite_master WHERE type='table' AND name='positions'" | grep -q positions; then
        sqlite3 state.db ".dump positions" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        POSITIONS_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM positions")
        echo "[Portfolio Migration] Positions migrated: $POSITIONS_COUNT"
    fi
fi

# Migrate scores from state.db or calculations.db
if [ -f "state.db" ]; then
    echo "[Portfolio Migration] Copying scores from state.db..."
    if sqlite3 state.db "SELECT name FROM sqlite_master WHERE type='table' AND name='scores'" | grep -q scores; then
        sqlite3 state.db ".dump scores" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        SCORES_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM scores")
        echo "[Portfolio Migration] Scores migrated: $SCORES_COUNT"
    fi
elif [ -f "calculations.db" ]; then
    echo "[Portfolio Migration] Copying scores from calculations.db..."
    if sqlite3 calculations.db "SELECT name FROM sqlite_master WHERE type='table' AND name='scores'" | grep -q scores; then
        sqlite3 calculations.db ".dump scores" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        SCORES_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM scores")
        echo "[Portfolio Migration] Scores migrated: $SCORES_COUNT"
    fi
fi

# Migrate calculated_metrics from calculations.db
if [ -f "calculations.db" ]; then
    echo "[Portfolio Migration] Copying calculated_metrics from calculations.db..."
    if sqlite3 calculations.db "SELECT name FROM sqlite_master WHERE type='table' AND name='calculated_metrics'" | grep -q calculated_metrics; then
        sqlite3 calculations.db ".dump calculated_metrics" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        METRICS_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM calculated_metrics")
        echo "[Portfolio Migration] Calculated metrics migrated: $METRICS_COUNT"
    fi
fi

# Migrate portfolio_snapshots from snapshots.db or state.db
if [ -f "snapshots.db" ]; then
    echo "[Portfolio Migration] Copying portfolio_snapshots from snapshots.db..."
    if sqlite3 snapshots.db "SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio_snapshots'" | grep -q portfolio_snapshots; then
        sqlite3 snapshots.db ".dump portfolio_snapshots" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        SNAPSHOTS_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM portfolio_snapshots")
        echo "[Portfolio Migration] Snapshots migrated: $SNAPSHOTS_COUNT"
    fi
elif [ -f "state.db" ]; then
    echo "[Portfolio Migration] Copying portfolio_snapshots from state.db..."
    if sqlite3 state.db "SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio_snapshots'" | grep -q portfolio_snapshots; then
        sqlite3 state.db ".dump portfolio_snapshots" | grep -v "^CREATE TABLE" | sqlite3 portfolio.db
        SNAPSHOTS_COUNT=$(sqlite3 portfolio.db "SELECT COUNT(*) FROM portfolio_snapshots")
        echo "[Portfolio Migration] Snapshots migrated: $SNAPSHOTS_COUNT"
    fi
fi

# Integrity check
INTEGRITY=$(sqlite3 portfolio.db "PRAGMA integrity_check")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[Portfolio Migration] ERROR: Integrity check failed: $INTEGRITY"
    exit 1
fi

echo "[Portfolio Migration] ✅ Complete"
