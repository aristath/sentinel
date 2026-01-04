#!/bin/bash
# Apply Risk Parameter Migration
# This script applies the risk parameter migration to the satellites database

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Find satellites database
find_satellites_db() {
    # Try common locations
    local locations=(
        "${PROJECT_ROOT}/trader-go/satellites.db"
        "${PROJECT_ROOT}/satellites.db"
        "${HOME}/.arduino-trader/satellites.db"
        "/opt/arduino-trader/satellites.db"
    )

    for loc in "${locations[@]}"; do
        if [ -f "$loc" ]; then
            echo "$loc"
            return 0
        fi
    done

    return 1
}

# Check if migration already applied
check_if_applied() {
    local db_path=$1

    # Check if risk_free_rate column exists
    local result=$(sqlite3 "$db_path" "PRAGMA table_info(satellite_settings);" | grep -c "risk_free_rate" || true)

    if [ "$result" -gt 0 ]; then
        return 0  # Already applied
    else
        return 1  # Not applied
    fi
}

# Backup database
backup_database() {
    local db_path=$1
    local backup_path="${db_path}.backup.$(date +%Y%m%d_%H%M%S)"

    log_info "Creating backup: $backup_path"
    cp "$db_path" "$backup_path"
    log_success "Backup created successfully"
    echo "$backup_path"
}

# Apply migration
apply_migration() {
    local db_path=$1
    local migration_file="${SCRIPT_DIR}/../migrations/001_add_risk_parameters.sql"

    if [ ! -f "$migration_file" ]; then
        log_error "Migration file not found: $migration_file"
        exit 1
    fi

    log_info "Applying migration..."
    sqlite3 "$db_path" < "$migration_file"
    log_success "Migration applied successfully"
}

# Verify migration
verify_migration() {
    local db_path=$1

    log_info "Verifying migration..."

    # Check all new columns exist
    local columns=("risk_free_rate" "sortino_mar" "evaluation_period_days" "volatility_window")
    local all_found=true

    for col in "${columns[@]}"; do
        local result=$(sqlite3 "$db_path" "PRAGMA table_info(satellite_settings);" | grep -c "$col" || true)
        if [ "$result" -eq 0 ]; then
            log_error "Column not found: $col"
            all_found=false
        else
            log_success "Column verified: $col"
        fi
    done

    # Check allocation_settings defaults
    local settings=("default_risk_free_rate" "default_sortino_mar" "default_evaluation_days")
    for setting in "${settings[@]}"; do
        local result=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM allocation_settings WHERE key='$setting';")
        if [ "$result" -eq 0 ]; then
            log_error "Default setting not found: $setting"
            all_found=false
        else
            log_success "Default setting verified: $setting"
        fi
    done

    # Check schema version
    local version=$(sqlite3 "$db_path" "SELECT version FROM schema_version WHERE version=2;" || echo "0")
    if [ "$version" = "2" ]; then
        log_success "Schema version updated to 2"
    else
        log_warn "Schema version not updated (this may be okay if already at higher version)"
    fi

    if [ "$all_found" = true ]; then
        log_success "Migration verification passed!"
        return 0
    else
        log_error "Migration verification failed!"
        return 1
    fi
}

# Show current satellite settings
show_current_settings() {
    local db_path=$1

    log_header "Current Satellite Settings"

    sqlite3 -header -column "$db_path" "
        SELECT
            satellite_id,
            risk_free_rate,
            sortino_mar,
            evaluation_period_days,
            volatility_window
        FROM satellite_settings
        ORDER BY satellite_id;
    " 2>/dev/null || log_warn "No satellite settings found (this is normal for new installations)"
}

# Main script
main() {
    log_header "Risk Parameter Migration Tool"

    # Find database
    log_info "Searching for satellites database..."
    DB_PATH=$(find_satellites_db)

    if [ -z "$DB_PATH" ]; then
        log_error "Could not find satellites.db in common locations"
        log_info "Please specify database path:"
        read -r DB_PATH

        if [ ! -f "$DB_PATH" ]; then
            log_error "Database not found: $DB_PATH"
            exit 1
        fi
    fi

    log_success "Found database: $DB_PATH"

    # Check if already applied
    if check_if_applied "$DB_PATH"; then
        log_warn "Migration appears to already be applied!"
        log_info "Risk parameters already exist in satellite_settings table"
        echo ""

        read -p "Show current settings? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            show_current_settings "$DB_PATH"
        fi

        read -p "Re-apply migration anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Migration cancelled"
            exit 0
        fi
    fi

    # Confirm before proceeding
    echo ""
    log_warn "This will modify the database: $DB_PATH"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Migration cancelled"
        exit 0
    fi

    # Backup database
    BACKUP_PATH=$(backup_database "$DB_PATH")

    # Apply migration
    if apply_migration "$DB_PATH"; then
        log_success "Migration completed!"
    else
        log_error "Migration failed!"
        log_info "Restoring from backup: $BACKUP_PATH"
        cp "$BACKUP_PATH" "$DB_PATH"
        log_success "Database restored from backup"
        exit 1
    fi

    # Verify
    echo ""
    if verify_migration "$DB_PATH"; then
        log_success "Migration successful and verified!"
    else
        log_error "Migration verification failed"
        log_warn "Backup available at: $BACKUP_PATH"
        exit 1
    fi

    # Show updated settings
    echo ""
    show_current_settings "$DB_PATH"

    # Success summary
    log_header "Migration Complete"
    log_success "Risk parameter migration applied successfully"
    log_info "Backup saved to: $BACKUP_PATH"
    log_info ""
    log_info "All satellites now have default risk parameters:"
    log_info "  - Risk-free rate: 3.5%"
    log_info "  - Sortino MAR: 5%"
    log_info "  - Evaluation period: 90 days"
    log_info "  - Volatility window: 60 days"
    log_info ""
    log_info "You can customize these per satellite via:"
    log_info "  PUT /api/satellites/:satellite_id/settings"
    log_info ""
    log_info "See docs/risk-parameter-configuration.md for details"
    echo ""
}

# Run main function
main
