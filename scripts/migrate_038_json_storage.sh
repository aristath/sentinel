#!/bin/bash
# Migration 038: Securities JSON Storage
# Migrates securities table from 15+ columns to 4 columns with JSON storage

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB="data/universe.db"
BACKUP_DIR="data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="$BACKUP_DIR/universe.db.backup.$TIMESTAMP"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_query() {
    local query="$1"
    local description="$2"

    if [ -n "$description" ]; then
        log_info "$description"
    fi

    sqlite3 "$DB" "$query"
}

check_result() {
    local result="$1"
    local expected="$2"
    local message="$3"

    if [ "$result" != "$expected" ]; then
        log_error "$message"
        log_error "Expected: $expected, Got: $result"
        exit 1
    fi
}

# Print header
echo ""
echo "========================================="
echo "  Securities JSON Storage Migration"
echo "  Migration 038"
echo "  Timestamp: $(date)"
echo "========================================="
echo ""

# Check if database exists
if [ ! -f "$DB" ]; then
    log_error "Database not found: $DB"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Step 1: Create Backup
log_info "[1/9] Creating backup..."
cp "$DB" "$BACKUP"
sqlite3 "$BACKUP" "PRAGMA integrity_check;" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    log_error "Backup integrity check failed"
    exit 1
fi
log_success "Backup created: $BACKUP"

# Step 2: Pre-migration checks
echo ""
log_info "[2/9] Running pre-migration checks..."

# Check for inactive securities with positions
INACTIVE_WITH_POS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities s JOIN positions p ON s.isin = p.isin WHERE s.active = 0 AND p.quantity != 0;")
check_result "$INACTIVE_WITH_POS" "0" "Found inactive securities with positions - cannot proceed"
log_success "No inactive securities with positions"

# Check for securities without ISINs
NO_ISIN=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities WHERE isin IS NULL OR isin = '';")
check_result "$NO_ISIN" "0" "Found securities without ISINs - cannot proceed"
log_success "All securities have ISINs"

# Get active security count for later verification
ACTIVE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities WHERE active = 1;")
log_info "Active securities: $ACTIVE_COUNT"

# Test JSON functions
JSON_TEST=$(sqlite3 "$DB" "SELECT json_object('test', 'value');")
if [ "$JSON_TEST" != '{"test":"value"}' ]; then
    log_error "JSON functions not working properly"
    exit 1
fi
log_success "JSON functions verified"

# Step 3: Delete inactive securities
echo ""
log_info "[3/9] Deleting inactive securities..."
run_query "DELETE FROM securities WHERE active = 0 AND isin NOT IN (SELECT DISTINCT isin FROM positions WHERE quantity != 0);"
REMAINING_INACTIVE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities WHERE active = 0;")
check_result "$REMAINING_INACTIVE" "0" "Failed to delete all inactive securities"
log_success "Inactive securities deleted"

# Step 4: Create new table
echo ""
log_info "[4/9] Creating new securities table..."
run_query "
CREATE TABLE securities_new (
    isin TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    data TEXT NOT NULL CHECK (json_valid(data)),
    last_synced INTEGER
) STRICT;
"
run_query "CREATE INDEX idx_securities_new_symbol ON securities_new(symbol);"
log_success "New table created"

# Step 5: Migrate data to JSON
echo ""
log_info "[5/9] Migrating data to JSON format..."
log_info "This may take a moment..."

sqlite3 "$DB" <<'SQL'
INSERT INTO securities_new (isin, symbol, data, last_synced)
SELECT
    isin,
    symbol,
    json_object(
        'name', COALESCE(name, ''),
        'product_type', COALESCE(product_type, 'EQUITY'),
        'industry', COALESCE(industry, ''),
        'geography', COALESCE(geography, ''),
        'fullExchangeName', COALESCE(fullExchangeName, ''),
        'market_code', COALESCE(market_code, ''),
        'currency', COALESCE(currency, 'USD'),
        'min_lot', COALESCE(min_lot, 1),
        'min_portfolio_target', COALESCE(min_portfolio_target, 0.0),
        'max_portfolio_target', COALESCE(max_portfolio_target, 0.15),
        'tradernet_raw', json_object()
    ) as data,
    CASE
        WHEN last_synced IS NOT NULL AND last_synced != ''
        THEN CAST(strftime('%s', last_synced) AS INTEGER)
        ELSE NULL
    END as last_synced
FROM securities
WHERE active = 1;
SQL

log_success "Data migrated to JSON format"

# Step 6: Verify migration
echo ""
log_info "[6/9] Verifying migration..."

NEW_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities_new;")
check_result "$NEW_COUNT" "$ACTIVE_COUNT" "Row count mismatch after migration"
log_success "Row count verified: $NEW_COUNT rows"

INVALID_JSON=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities_new WHERE json_valid(data) = 0;")
check_result "$INVALID_JSON" "0" "Found invalid JSON entries"
log_success "All JSON entries valid"

# Spot check data
log_info "Sample data check:"
sqlite3 "$DB" "SELECT isin, symbol, json_extract(data, '\$.name') as name, json_extract(data, '\$.geography') as geography FROM securities_new LIMIT 3;"

# Step 7: Atomic cutover
echo ""
log_info "[7/9] Performing atomic cutover..."

sqlite3 "$DB" <<'SQL'
BEGIN TRANSACTION;

DROP TABLE securities;
ALTER TABLE securities_new RENAME TO securities;

COMMIT;
SQL

log_success "Table replaced successfully"

# Step 8: Verify foreign keys
echo ""
log_info "[8/9] Verifying foreign key integrity..."

ORPHAN_OVERRIDES=$(sqlite3 "$DB" "SELECT COUNT(*) FROM security_overrides o LEFT JOIN securities s ON o.isin = s.isin WHERE s.isin IS NULL;")
check_result "$ORPHAN_OVERRIDES" "0" "Found orphaned security overrides"
log_success "No orphaned security overrides"

ORPHAN_POSITIONS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM positions p LEFT JOIN securities s ON p.isin = s.isin WHERE s.isin IS NULL AND p.quantity > 0;")
check_result "$ORPHAN_POSITIONS" "0" "Found orphaned positions"
log_success "No orphaned positions"

# Step 9: Post-migration verification
echo ""
log_info "[9/9] Post-migration verification..."

# Verify schema
log_info "Verifying table schema..."
COLUMN_COUNT=$(sqlite3 "$DB" "PRAGMA table_info(securities);" | wc -l)
check_result "$COLUMN_COUNT" "4" "Schema has wrong number of columns"
log_success "Schema verified (4 columns)"

# Verify indexes
INDEX_COUNT=$(sqlite3 "$DB" "PRAGMA index_list(securities);" | wc -l)
if [ "$INDEX_COUNT" -lt "2" ]; then
    log_warning "Expected at least 2 indexes, found $INDEX_COUNT"
fi
log_success "Indexes verified"

# Final count check
FINAL_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities;")
check_result "$FINAL_COUNT" "$ACTIVE_COUNT" "Final row count doesn't match active count"
log_success "Final row count verified: $FINAL_COUNT"

# Test JSON extraction
log_info "Testing JSON extraction..."
TEST_RESULT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM securities WHERE json_extract(data, '\$.name') IS NOT NULL;")
if [ "$TEST_RESULT" = "0" ]; then
    log_error "JSON extraction test failed"
    exit 1
fi
log_success "JSON extraction working ($TEST_RESULT securities with names)"

# Database integrity check
log_info "Running database integrity check..."
INTEGRITY=$(sqlite3 "$DB" "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    log_error "Database integrity check failed: $INTEGRITY"
    exit 1
fi
log_success "Database integrity verified"

# Summary
echo ""
echo "========================================="
log_success "Migration completed successfully!"
echo "========================================="
echo ""
echo "Summary:"
echo "  - Active securities migrated: $ACTIVE_COUNT"
echo "  - Final security count: $FINAL_COUNT"
echo "  - Backup location: $BACKUP"
echo "  - Migration time: $(date)"
echo ""
echo "Next steps:"
echo "  1. Start the application: systemctl start sentinel"
echo "  2. Verify application logs for errors"
echo "  3. Test the following:"
echo "     - GET /api/securities endpoint"
echo "     - Securities list in UI"
echo "     - Positions page"
echo "     - Tradernet metadata sync job"
echo ""
echo "Rollback instructions (if needed):"
echo "  systemctl stop sentinel"
echo "  cp $BACKUP data/universe.db"
echo "  systemctl start sentinel"
echo ""
