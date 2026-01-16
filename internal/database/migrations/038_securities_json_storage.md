# Migration 038: Securities JSON Storage

## Purpose
Migrate from 15+ column schema to JSON storage (4 columns: isin, symbol, data, last_synced).
Remove active column (hard delete only), remove created_at/updated_at.
Store complete Tradernet API response as JSON blob.

## Impact
- **Breaking**: Changes securities table schema from 15+ columns to 4 columns
- **Data Migration**: All existing data migrated to JSON format
- **No Rollback**: One-way migration (backup required)
- **Downtime**: Estimated 1-5 seconds (depends on number of securities)

## Pre-Migration Checks

Run these queries to verify data integrity before migration:

```sql
-- Check for inactive securities with positions
SELECT s.isin, s.symbol, p.quantity
FROM securities s
JOIN positions p ON s.isin = p.isin
WHERE s.active = 0 AND p.quantity != 0;
-- MUST return 0 rows (no inactive securities with open positions)

-- Check total active security count
SELECT COUNT(*) FROM securities WHERE active = 1;
-- Note this count for verification after migration

-- Check for securities without ISINs
SELECT symbol FROM securities WHERE isin IS NULL OR isin = '';
-- MUST return 0 rows (all securities need ISINs)

-- Check JSON validity test (pre-flight)
SELECT json_object('test', 'value') as test;
-- MUST return valid JSON: {"test":"value"}
```

## Migration Steps

### Step 1: Delete Inactive Securities

```sql
-- Delete inactive securities that have no positions
DELETE FROM securities
WHERE active = 0
AND isin NOT IN (SELECT DISTINCT isin FROM positions WHERE quantity != 0);

-- Verify deletion
SELECT COUNT(*) FROM securities WHERE active = 0;
-- Should return 0
```

### Step 2: Create New Table

```sql
CREATE TABLE securities_new (
    isin TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    data TEXT NOT NULL,
    last_synced INTEGER
) STRICT;

CREATE INDEX idx_securities_new_symbol ON securities_new(symbol);
```

### Step 3: Migrate Data to JSON

```sql
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
```

### Step 4: Verify Migration

```sql
-- Row counts must match
SELECT
    (SELECT COUNT(*) FROM securities WHERE active = 1) as old_count,
    (SELECT COUNT(*) FROM securities_new) as new_count;
-- Both counts must be equal

-- All JSON must be valid
SELECT COUNT(*) FROM securities_new WHERE json_valid(data) = 0;
-- MUST return 0 (all JSON valid)

-- Spot check: verify data integrity for a few securities
SELECT
    isin,
    symbol,
    json_extract(data, '$.name') as name,
    json_extract(data, '$.geography') as geography,
    json_extract(data, '$.product_type') as product_type,
    json_extract(data, '$.min_lot') as min_lot
FROM securities_new LIMIT 10;
-- Review output to ensure data looks correct
```

### Step 5: Atomic Cutover

```sql
BEGIN TRANSACTION;

-- Drop old table
DROP TABLE securities;

-- Rename new table
ALTER TABLE securities_new RENAME TO securities;

-- Verify foreign key integrity
SELECT COUNT(*) FROM security_overrides o
LEFT JOIN securities s ON o.isin = s.isin
WHERE s.isin IS NULL;
-- MUST return 0 (all overrides reference valid securities)

-- Verify positions reference valid securities
SELECT COUNT(*) FROM positions p
LEFT JOIN securities s ON p.isin = s.isin
WHERE s.isin IS NULL AND p.quantity > 0;
-- MUST return 0 (all positions reference valid securities)

COMMIT;
```

### Step 6: Post-Migration Verification

```sql
-- Verify schema
PRAGMA table_info(securities);
-- Should show: isin, symbol, data, last_synced

-- Verify indexes
PRAGMA index_list(securities);
-- Should show: sqlite_autoindex_securities_1 (PRIMARY KEY), idx_securities_symbol

-- Verify row count matches pre-migration count
SELECT COUNT(*) FROM securities;

-- Test JSON extraction works
SELECT
    symbol,
    json_extract(data, '$.name') as name,
    json_extract(data, '$.geography') as geography
FROM securities LIMIT 5;

-- Test repository still works (via application)
-- This should be tested by starting the application and verifying:
-- 1. Securities list endpoint returns data
-- 2. Positions page loads
-- 3. Tradernet metadata sync runs successfully
```

## Rollback Plan

**CRITICAL**: This is a one-way migration. The only rollback is to restore from backup.

```bash
# Stop application
systemctl stop sentinel

# Restore from backup
cp data/universe.db.backup.TIMESTAMP data/universe.db

# Verify backup integrity
sqlite3 data/universe.db "PRAGMA integrity_check;"

# Restart application with old code
systemctl start sentinel
```

## Expected Results

**Before Migration**:
- Table: securities with 15+ columns (isin, symbol, name, product_type, industry, geography, currency, market_code, fullExchangeName, min_lot, min_portfolio_target, max_portfolio_target, active, created_at, updated_at, last_synced)
- Active securities: N rows
- Inactive securities: M rows

**After Migration**:
- Table: securities with 4 columns (isin, symbol, data, last_synced)
- Total securities: N rows (only active)
- All inactive securities: deleted
- All JSON valid: 100%
- Application: fully functional

## Testing Checklist

After migration, verify:
- [ ] Application starts without errors
- [ ] GET /api/securities returns securities list
- [ ] Securities have correct data (name, geography, industry visible in UI)
- [ ] Positions page loads correctly
- [ ] Optimization runs successfully
- [ ] Tradernet metadata sync runs and updates securities
- [ ] New securities can be added
- [ ] Security overrides still work
- [ ] No database integrity errors in logs

## Notes

- Migration is idempotent - safe to re-run if interrupted
- All inactive securities are permanently deleted
- active, created_at, updated_at columns are removed
- All data now stored as JSON in data column
- last_synced converted from TEXT to INTEGER (Unix timestamp)
- Tradernet API responses will be stored in tradernet_raw nested object
- Application code already updated to use repository pattern exclusively
