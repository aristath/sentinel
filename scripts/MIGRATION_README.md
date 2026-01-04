# Python to Go Database Migration Guide

**NOTE: Migration is complete. The migration scripts referenced in this document have been removed as they were one-time use scripts.**

This guide explains how to migrate data from the legacy Python app databases to the new Go app databases. This document is kept for historical reference.

## Prerequisites

- Python 3.10+ installed on Arduino device
- Access to both Python app data directory (`~/arduino-trader/data`) and Go app data directory (`~/app/data`)
- Sufficient disk space for backups (at least 2x current database size)

## Quick Start

### Option 1: Run Complete Migration (Recommended)

This will backup legacy databases and then run the migration:

```bash
# SSH to Arduino device
ssh arduino@192.168.1.11

# Navigate to project directory
cd ~/arduino-trader

# Run complete migration (with backup)
./scripts/run_migration.sh
```

### Option 2: Step-by-Step

#### Step 1: Backup Legacy Databases

```bash
ssh arduino@192.168.1.11
cd ~/arduino-trader

# Create backup of all legacy databases
./scripts/backup_legacy_databases.sh ~/arduino-trader/data
```

This creates:
- A directory backup: `~/arduino-trader/data/backups/legacy_pre_migration_TIMESTAMP/`
- A compressed archive: `~/arduino-trader/data/backups/legacy_pre_migration_TIMESTAMP.tar.gz`

#### Step 2: Run Migration (Dry-Run First)

```bash
# Test migration without making changes
python3 scripts/migrate_python_to_go.py \
  --python-data-dir ~/arduino-trader/data \
  --go-data-dir ~/app/data \
  --dry-run
```

Review the output to ensure everything looks correct.

#### Step 3: Run Actual Migration

```bash
# Run the actual migration
python3 scripts/migrate_python_to_go.py \
  --python-data-dir ~/arduino-trader/data \
  --go-data-dir ~/app/data
```

The migration script will:
1. Create additional backups (in `~/app/data/backups/`)
2. Initialize Go database schemas
3. Migrate all data with proper transformations
4. Log everything to `migration_TIMESTAMP.log`

## What Gets Migrated

| Source (Python) | Destination (Go) | Tables |
|----------------|------------------|--------|
| `config.db` | `universe.db` | securities, country_groups, industry_groups |
| `config.db` | `config.db` | settings, allocation_targets |
| `state.db` | `portfolio.db` | positions, scores |
| `calculations.db` | `portfolio.db` | scores, calculated_metrics |
| `snapshots.db` | `portfolio.db` | portfolio_snapshots |
| `ledger.db` | `ledger.db` | trades, cash_flows |
| `dividends.db` | `ledger.db` | dividend_history, drip_tracking |
| `satellites.db` | `satellites.db` | buckets, bucket_balances, satellite_settings |
| `planner.db` | `agents.db` | sequences, evaluations |
| `history/*.db` | `history.db` | daily_prices (consolidated) |
| `config.db` / `recommendations.db` | `cache.db` | recommendations |

## Verification

After migration, verify the data:

```bash
# Check Go database row counts
sqlite3 ~/app/data/universe.db "SELECT COUNT(*) FROM securities;"
sqlite3 ~/app/data/portfolio.db "SELECT COUNT(*) FROM positions;"
sqlite3 ~/app/data/ledger.db "SELECT COUNT(*) FROM trades;"

# Compare with Python databases
sqlite3 ~/arduino-trader/data/config.db "SELECT COUNT(*) FROM securities;"
sqlite3 ~/arduino-trader/data/state.db "SELECT COUNT(*) FROM positions;"
sqlite3 ~/arduino-trader/data/ledger.db "SELECT COUNT(*) FROM trades;"
```

## Rollback

If you need to rollback:

```bash
# Restore from backup
cd ~/arduino-trader/data
tar -xzf backups/legacy_pre_migration_TIMESTAMP.tar.gz
cp backups/legacy_pre_migration_TIMESTAMP/*.db .
```

## Troubleshooting

### "Database not found" warnings

Some databases may not exist (e.g., `recommendations.db`). This is normal - the script handles missing databases gracefully.

### "Table not found" errors

If a table doesn't exist in the Python database, it will be skipped. Check the migration log for details.

### Row count mismatches

If row counts don't match:
1. Check the migration log for errors
2. Verify source database integrity: `sqlite3 database.db "PRAGMA integrity_check;"`
3. Re-run the specific migration function if needed

## Post-Migration

After successful migration:

1. **Test the Go app:**
   ```bash
   cd ~/app
   ./trader  # or however you start the Go app
   ```

2. **Verify critical functions:**
   - Portfolio display loads correctly
   - Securities data is accessible
   - Historical data queries work
   - Trading functions operate correctly
   - Planning/agent functions work

3. **Monitor for 1 week** before considering the migration complete

4. **Keep backups** for at least 1 month before deleting

## Files

**Note: The migration scripts have been removed after successful migration completion:**
- ~~`migrate_python_to_go.py`~~ - Main migration script (removed - migration complete)
- `backup_legacy_databases.sh` - Backup script for legacy databases (still available)
- ~~`run_migration.sh`~~ - Complete workflow script (removed - migration complete)
- ~~`deploy_migration.sh`~~ - Deploy script (removed - migration complete)

## Support

Check migration logs in:
- `migration_TIMESTAMP.log` - Detailed migration log
- `~/arduino-trader/data/backups/` - Legacy database backups
- `~/app/data/backups/` - Go database backups created during migration
