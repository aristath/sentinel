#!/bin/bash

# Database Backup Script for Sentinel
# This script creates backups of all 7 databases with verification

set -e  # Exit on error

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$HOME/sentinel-backups}"
DATA_DIR="${DATA_DIR:-$HOME/sentinel-data}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_SUBDIR="$BACKUP_DIR/backup_$TIMESTAMP"

# Database files
DATABASES=(
    "universe.db"
    "config.db"
    "ledger.db"
    "portfolio.db"
    "agents.db"
    "history.db"
    "cache.db"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Sentinel Database Backup"
echo "=========================================="
echo "Timestamp: $TIMESTAMP"
echo "Source: $DATA_DIR"
echo "Destination: $BACKUP_SUBDIR"
echo ""

# Create backup directory
mkdir -p "$BACKUP_SUBDIR"

# Function to backup a single database
backup_database() {
    local db_name=$1
    local source_path="$DATA_DIR/$db_name"
    local backup_path="$BACKUP_SUBDIR/$db_name"

    echo -n "Backing up $db_name... "

    if [ ! -f "$source_path" ]; then
        echo -e "${YELLOW}SKIP${NC} (file not found)"
        return 0
    fi

    # Create backup using SQLite backup API (online backup)
    sqlite3 "$source_path" ".backup '$backup_path'"

    if [ $? -eq 0 ]; then
        # Verify backup integrity
        if sqlite3 "$backup_path" "PRAGMA integrity_check;" | grep -q "ok"; then
            local source_size=$(stat -f%z "$source_path" 2>/dev/null || stat -c%s "$source_path" 2>/dev/null)
            local backup_size=$(stat -f%z "$backup_path" 2>/dev/null || stat -c%s "$backup_path" 2>/dev/null)
            echo -e "${GREEN}OK${NC} ($source_size bytes -> $backup_size bytes)"
        else
            echo -e "${RED}FAIL${NC} (integrity check failed)"
            return 1
        fi
    else
        echo -e "${RED}FAIL${NC} (backup command failed)"
        return 1
    fi
}

# Backup each database
echo "Backing up databases:"
echo ""

backup_count=0
skip_count=0
fail_count=0

for db in "${DATABASES[@]}"; do
    if backup_database "$db"; then
        if [ -f "$BACKUP_SUBDIR/$db" ]; then
            ((backup_count++))
        else
            ((skip_count++))
        fi
    else
        ((fail_count++))
    fi
done

echo ""
echo "=========================================="
echo "Backup Summary"
echo "=========================================="
echo "Successfully backed up: $backup_count databases"
echo "Skipped (not found): $skip_count databases"
echo "Failed: $fail_count databases"
echo "Backup location: $BACKUP_SUBDIR"
echo ""

# Create backup manifest
cat > "$BACKUP_SUBDIR/MANIFEST.txt" << EOF
Sentinel Database Backup
========================
Timestamp: $TIMESTAMP
Source Directory: $DATA_DIR
Backup Directory: $BACKUP_SUBDIR

Databases Backed Up: $backup_count
Databases Skipped: $skip_count
Databases Failed: $fail_count

Files:
EOF

for db in "${DATABASES[@]}"; do
    if [ -f "$BACKUP_SUBDIR/$db" ]; then
        size=$(stat -f%z "$BACKUP_SUBDIR/$db" 2>/dev/null || stat -c%s "$BACKUP_SUBDIR/$db" 2>/dev/null)
        echo "  - $db ($size bytes)" >> "$BACKUP_SUBDIR/MANIFEST.txt"
    fi
done

# Create compressed archive (optional)
if command -v tar &> /dev/null; then
    echo "Creating compressed archive..."
    tar -czf "$BACKUP_SUBDIR.tar.gz" -C "$BACKUP_DIR" "backup_$TIMESTAMP"

    if [ $? -eq 0 ]; then
        archive_size=$(stat -f%z "$BACKUP_SUBDIR.tar.gz" 2>/dev/null || stat -c%s "$BACKUP_SUBDIR.tar.gz" 2>/dev/null)
        echo -e "${GREEN}Archive created${NC}: $BACKUP_SUBDIR.tar.gz ($archive_size bytes)"
        echo ""
        echo "You can safely delete the uncompressed backup directory:"
        echo "  rm -rf '$BACKUP_SUBDIR'"
    else
        echo -e "${YELLOW}Archive creation failed${NC}"
    fi
fi

echo ""

# Cleanup old backups (keep last 7 days)
if [ "$1" != "--no-cleanup" ]; then
    echo "Cleaning up old backups (keeping last 7 days)..."
    find "$BACKUP_DIR" -name "backup_*" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -exec rm -f {} + 2>/dev/null || true
    echo "Cleanup complete"
    echo ""
fi

# Exit with appropriate code
if [ $fail_count -gt 0 ]; then
    echo -e "${RED}Backup completed with errors${NC}"
    exit 1
else
    echo -e "${GREEN}Backup completed successfully${NC}"
    exit 0
fi
