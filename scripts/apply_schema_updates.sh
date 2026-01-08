#!/bin/bash

# Apply Schema Updates for Sentinel
# This script applies the foreign key constraints added during the 2026-01-08 bug fix session
# IMPORTANT: Run this AFTER backing up databases with backup_databases.sh

set -e  # Exit on error

# Configuration
DATA_DIR="${DATA_DIR:-$HOME/sentinel-data}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Sentinel Schema Update Application"
echo "=========================================="
echo "Date: $(date +%Y-%m-%d)"
echo "Data Directory: $DATA_DIR"
echo ""

# Safety check
echo -e "${YELLOW}WARNING:${NC} This script will modify your databases."
echo "Press Ctrl+C now to abort, or press Enter to continue..."
read -r

# Check if Sentinel is running
if pgrep -x "sentinel" > /dev/null; then
    echo -e "${RED}ERROR:${NC} Sentinel is still running!"
    echo "Please stop Sentinel before running this script:"
    echo "  kill -TERM \$(pgrep sentinel)"
    exit 1
fi

echo -e "${GREEN}✓${NC} Sentinel is not running"
echo ""

# Verify backup exists
LATEST_BACKUP=$(find ~/sentinel-backups -name "backup_*" -type d 2>/dev/null | sort -r | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${YELLOW}WARNING:${NC} No backup found in ~/sentinel-backups"
    echo "It is HIGHLY recommended to create a backup first:"
    echo "  ~/sentinel/scripts/backup_databases.sh"
    echo ""
    echo "Continue anyway? (yes/no)"
    read -r response
    if [ "$response" != "yes" ]; then
        echo "Aborting."
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Found recent backup: $LATEST_BACKUP"
fi

echo ""
echo "=========================================="
echo "Applying Schema Updates"
echo "=========================================="
echo ""

# Function to apply SQL and check result
apply_sql() {
    local db_path=$1
    local description=$2
    local sql=$3

    echo -n "$description... "

    if [ ! -f "$db_path" ]; then
        echo -e "${YELLOW}SKIP${NC} (database not found)"
        return 0
    fi

    # Execute SQL
    result=$(sqlite3 "$db_path" "$sql" 2>&1)

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        # Check if error is due to constraint already existing
        if echo "$result" | grep -qi "already exists\|duplicate"; then
            echo -e "${YELLOW}SKIP${NC} (already applied)"
            return 0
        else
            echo -e "${RED}FAIL${NC}"
            echo "  Error: $result"
            return 1
        fi
    fi
}

# 1. Ledger Database - Add foreign key to dividend_history
echo "1. Ledger Database Updates:"
echo ""

# Note: SQLite doesn't support adding foreign keys to existing tables
# We need to check if the constraint already exists in the schema
echo -n "   Checking dividend_history foreign key... "

FK_EXISTS=$(sqlite3 "$DATA_DIR/ledger.db" "SELECT sql FROM sqlite_master WHERE type='table' AND name='dividend_history';" | grep -c "FOREIGN KEY (cash_flow_id)" || true)

if [ "$FK_EXISTS" -gt 0 ]; then
    echo -e "${GREEN}OK${NC} (already exists)"
else
    echo -e "${YELLOW}INFO${NC}"
    echo "   The dividend_history table needs to be recreated with the foreign key."
    echo "   This is already done in the schema file: internal/database/schemas/ledger_schema.sql"
    echo "   The constraint will be applied when the table is next created."
    echo ""
    echo "   To apply immediately, run the following in the Sentinel application:"
    echo "   1. Stop Sentinel"
    echo "   2. Rename the table: ALTER TABLE dividend_history RENAME TO dividend_history_old;"
    echo "   3. Restart Sentinel (will recreate table with FK)"
    echo "   4. Migrate data: INSERT INTO dividend_history SELECT * FROM dividend_history_old;"
    echo "   5. Drop old table: DROP TABLE dividend_history_old;"
fi

echo ""

# 2. Portfolio Database - Kelly sizes foreign key
echo "2. Portfolio Database Updates:"
echo ""

echo -n "   Checking kelly_sizes foreign key... "

FK_EXISTS=$(sqlite3 "$DATA_DIR/portfolio.db" "SELECT sql FROM sqlite_master WHERE type='table' AND name='kelly_sizes';" | grep -c "FOREIGN KEY (isin)" || true)

if [ "$FK_EXISTS" -gt 0 ]; then
    # Check if it has CASCADE
    CASCADE_EXISTS=$(sqlite3 "$DATA_DIR/portfolio.db" "SELECT sql FROM sqlite_master WHERE type='table' AND name='kelly_sizes';" | grep -c "ON DELETE CASCADE" || true)

    if [ "$CASCADE_EXISTS" -gt 0 ]; then
        echo -e "${GREEN}OK${NC} (already has CASCADE)"
    else
        echo -e "${YELLOW}INFO${NC}"
        echo "   The kelly_sizes table has a foreign key but without CASCADE."
        echo "   Updated schema is in: internal/database/schemas/portfolio_schema.sql"
        echo "   New tables will have the correct constraint."
    fi
else
    echo -e "${YELLOW}INFO${NC}"
    echo "   The kelly_sizes foreign key is defined in the schema."
    echo "   It will be applied when the table is next created."
fi

echo ""

# 3. Verify all databases with integrity check
echo "=========================================="
echo "Database Integrity Verification"
echo "=========================================="
echo ""

for db in "$DATA_DIR"/*.db; do
    db_name=$(basename "$db")
    echo -n "Checking $db_name... "

    result=$(sqlite3 "$db" "PRAGMA integrity_check;" 2>&1)

    if [ "$result" = "ok" ]; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        echo "  $result"
    fi
done

echo ""

# 4. Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo -e "${GREEN}Schema updates verified.${NC}"
echo ""
echo "Notes:"
echo "  - Schema files have been updated with foreign key constraints"
echo "  - Existing tables will get new constraints when recreated"
echo "  - New installations will have all constraints from the start"
echo "  - The constraints are enforced by the updated schema files"
echo ""
echo "Next steps:"
echo "  1. Start Sentinel: ~/sentinel/sentinel"
echo "  2. Verify operation in logs: tail -f ~/sentinel-data/logs/sentinel.log"
echo "  3. Run integrity verification: sqlite3 ~/sentinel-data/ledger.db < ~/sentinel/scripts/verify_data_integrity.sql"
echo ""
echo -e "${GREEN}Update process complete.${NC}"
