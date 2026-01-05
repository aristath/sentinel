#!/bin/bash

# Database Migration Script - 15+ databases → 8 databases
# This script orchestrates the complete data migration for the Arduino Trader system
#
# CRITICAL: This manages real retirement funds - execute with extreme caution
#
# Usage: ./migrate_databases.sh [--dry-run] [--verify-only]
#
# Flags:
#   --dry-run      Simulate migration without making changes
#   --verify-only  Only verify data, skip migration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="../../../data"
BACKUP_DIR="../../../data/backups/migration_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SCRIPT_DIR}/migration_$(date +%Y%m%d_%H%M%S).log"

DRY_RUN=false
VERIFY_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
            ;;
        --verify-only)
            VERIFY_ONLY=true
            echo -e "${BLUE}VERIFY ONLY MODE${NC}"
            ;;
    esac
done

# Logging function
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# Check if database exists
check_db_exists() {
    local db_path="$1"
    if [ -f "$db_path" ]; then
        return 0
    else
        return 1
    fi
}

# Get database size
get_db_size() {
    local db_path="$1"
    if [ -f "$db_path" ]; then
        du -h "$db_path" | cut -f1
    else
        echo "0"
    fi
}

# Get row count from table
get_row_count() {
    local db_path="$1"
    local table="$2"
    if [ -f "$db_path" ]; then
        sqlite3 "$db_path" "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Integrity check
check_integrity() {
    local db_path="$1"
    if [ -f "$db_path" ]; then
        local result=$(sqlite3 "$db_path" "PRAGMA integrity_check" 2>/dev/null || echo "error")
        if [ "$result" == "ok" ]; then
            return 0
        else
            log_error "Integrity check failed for $db_path: $result"
            return 1
        fi
    fi
    return 0
}

# Create backup
create_backup() {
    log_info "Creating backup in $BACKUP_DIR"

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create backup directory"
        return 0
    fi

    mkdir -p "$BACKUP_DIR"

    # Backup all existing databases
    cd "$DATA_DIR"
    for db in *.db; do
        if [ -f "$db" ]; then
            log_info "Backing up $db ($(get_db_size "$db"))"
            cp "$db" "$BACKUP_DIR/"

            # Also backup WAL and SHM files if they exist
            [ -f "${db}-wal" ] && cp "${db}-wal" "$BACKUP_DIR/"
            [ -f "${db}-shm" ] && cp "${db}-shm" "$BACKUP_DIR/"
        fi
    done

    # Backup history directory
    if [ -d "history" ]; then
        log_info "Backing up history directory"
        cp -r history "$BACKUP_DIR/"
    fi

    log_success "Backup created: $BACKUP_DIR"
}

# Pre-migration verification
verify_source_databases() {
    log_info "=== Pre-Migration Verification ==="

    local errors=0

    cd "$DATA_DIR"

    # Check critical databases exist
    local critical_dbs=("config.db" "ledger.db")
    for db in "${critical_dbs[@]}"; do
        if ! check_db_exists "$db"; then
            log_error "Critical database missing: $db"
            ((errors++))
        else
            log_success "Found $db ($(get_db_size "$db"))"

            # Integrity check
            if ! check_integrity "$db"; then
                log_error "Integrity check failed: $db"
                ((errors++))
            fi
        fi
    done

    # Check optional databases
    local optional_dbs=("state.db" "calculations.db" "snapshots.db" "dividends.db")
    for db in "${optional_dbs[@]}"; do
        if check_db_exists "$db"; then
            log_info "Found optional database: $db ($(get_db_size "$db"))"
            check_integrity "$db" || log_warning "Integrity issue in $db"
        else
            log_warning "Optional database not found: $db (will be skipped)"
        fi
    done

    # Check history directory
    if [ -d "history" ]; then
        local history_count=$(find history -name "*.db" -type f | wc -l)
        log_info "Found history directory with $history_count database files"
    else
        log_warning "No history directory found"
    fi

    if [ $errors -gt 0 ]; then
        log_error "Pre-migration verification failed with $errors errors"
        return 1
    fi

    log_success "Pre-migration verification passed"
    return 0
}

# Execute migration step
execute_migration() {
    local step_name="$1"
    local script_path="$2"

    log_info "=== Executing: $step_name ==="

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would execute: $script_path"
        return 0
    fi

    if [ ! -f "$script_path" ]; then
        log_error "Migration script not found: $script_path"
        return 1
    fi

    # Execute the migration script
    if bash "$script_path" "$DATA_DIR"; then
        log_success "$step_name completed"
        return 0
    else
        log_error "$step_name failed"
        return 1
    fi
}

# Post-migration verification
verify_migration() {
    log_info "=== Post-Migration Verification ==="

    cd "$DATA_DIR"

    local errors=0

    # Check new databases exist and have data
    declare -A expected_dbs=(
        ["universe.db"]="securities"
        ["config.db"]="settings"
        ["ledger.db"]="trades"
        ["portfolio.db"]="positions"
        ["satellites.db"]="buckets"
        ["agents.db"]="agent_configs"
        ["history.db"]="daily_prices"
        ["cache.db"]="cache_data"
    )

    for db in "${!expected_dbs[@]}"; do
        local table="${expected_dbs[$db]}"

        if ! check_db_exists "$db"; then
            log_error "New database missing: $db"
            ((errors++))
            continue
        fi

        log_info "Checking $db ($(get_db_size "$db"))"

        # Integrity check
        if ! check_integrity "$db"; then
            log_error "Integrity check failed: $db"
            ((errors++))
        fi

        # Check table exists and has data
        local count=$(get_row_count "$db" "$table")
        if [ "$count" == "0" ]; then
            log_warning "$db.$table has no rows (might be expected)"
        else
            log_success "$db.$table has $count rows"
        fi
    done

    if [ $errors -gt 0 ]; then
        log_error "Post-migration verification failed with $errors errors"
        return 1
    fi

    log_success "Post-migration verification passed"
    return 0
}

# Main execution
main() {
    log_info "========================================"
    log_info "Arduino Trader Database Migration"
    log_info "15+ databases → 8 databases"
    log_info "========================================"
    log_info ""
    log_info "Data Directory: $DATA_DIR"
    log_info "Backup Directory: $BACKUP_DIR"
    log_info "Log File: $LOG_FILE"
    log_info ""

    # Change to data directory
    cd "$DATA_DIR" || {
        log_error "Failed to access data directory: $DATA_DIR"
        exit 1
    }

    # Step 1: Pre-migration verification
    if ! verify_source_databases; then
        log_error "Pre-migration verification failed. Aborting."
        exit 1
    fi

    if [ "$VERIFY_ONLY" = true ]; then
        log_info "Verification complete. Exiting (--verify-only mode)"
        exit 0
    fi

    # Step 2: Create backup
    if ! create_backup; then
        log_error "Backup creation failed. Aborting."
        exit 1
    fi

    # Step 3: Execute migrations
    log_info ""
    log_info "=== Starting Data Migration ==="
    log_info ""

    # Migration 1: Split config.db → universe.db + config.db
    execute_migration "Universe DB Migration" "${SCRIPT_DIR}/migrate_universe.sh" || {
        log_error "Universe migration failed. Check logs and backup at: $BACKUP_DIR"
        exit 1
    }

    # Migration 2: Consolidate state.db + calculations.db + snapshots.db → portfolio.db
    execute_migration "Portfolio DB Consolidation" "${SCRIPT_DIR}/migrate_portfolio.sh" || {
        log_error "Portfolio consolidation failed. Check logs and backup at: $BACKUP_DIR"
        exit 1
    }

    # Migration 3: Merge dividends.db → ledger.db
    execute_migration "Ledger DB Expansion" "${SCRIPT_DIR}/migrate_ledger.sh" || {
        log_error "Ledger expansion failed. Check logs and backup at: $BACKUP_DIR"
        exit 1
    }

    # Migration 4: Consolidate history/*.db → history.db
    execute_migration "History DB Consolidation" "${SCRIPT_DIR}/migrate_history.sh" || {
        log_error "History consolidation failed. Check logs and backup at: $BACKUP_DIR"
        exit 1
    }

    # Migration 5: Move recommendations → cache.db
    execute_migration "Cache DB Migration" "${SCRIPT_DIR}/migrate_cache.sh" || {
        log_error "Cache migration failed. Check logs and backup at: $BACKUP_DIR"
        exit 1
    }

    # Step 4: Post-migration verification
    log_info ""
    if ! verify_migration; then
        log_error "Post-migration verification failed!"
        log_error "Backup available at: $BACKUP_DIR"
        log_error "Review logs at: $LOG_FILE"
        exit 1
    fi

    # Step 5: Success
    log_info ""
    log_info "========================================"
    log_success "✅ DATABASE MIGRATION COMPLETE"
    log_info "========================================"
    log_info ""
    log_info "Next steps:"
    log_info "1. Review migration log: $LOG_FILE"
    log_info "2. Test the application thoroughly"
    log_info "3. If everything works, old databases can be archived"
    log_info "4. Backup is available at: $BACKUP_DIR"
    log_info ""
}

# Run main function
main
