# Database Migration Scripts

This directory contains scripts to migrate the Arduino Trader database architecture from 15+ databases to a clean 8-database system.

## ⚠️ CRITICAL WARNING

**This migration affects real retirement funds.** Execute with extreme caution and only after:
1. Full system backup
2. Testing in a copy of production data
3. Verification of all migration scripts
4. Understanding of rollback procedures

## Architecture Overview

### Before (15+ databases):
- config.db
- state.db
- calculations.db
- snapshots.db
- dividends.db
- ledger.db
- satellites.db
- planner.db
- recommendations.db
- rates.db
- history/{SYMBOL}.db (65+ files)
- cache.db
- + several empty/unused databases

### After (8 databases):
1. **universe.db** - Securities and groups
2. **config.db** - Settings and allocation targets (REDUCED)
3. **ledger.db** - Financial audit trail (EXPANDED)
4. **portfolio.db** - Current state (NEW consolidation)
5. **satellites.db** - Multi-bucket system
6. **agents.db** - Strategy management (RENAMED)
7. **history.db** - Time-series data (CONSOLIDATED)
8. **cache.db** - Ephemeral data

## Migration Scripts

### 1. Main Orchestrator
**File:** `migrate_databases.sh`

Master script that coordinates the entire migration process.

```bash
# Dry run (recommended first step)
./migrate_databases.sh --dry-run

# Verify source databases only
./migrate_databases.sh --verify-only

# Execute migration (CREATES AUTOMATIC BACKUP)
./migrate_databases.sh
```

**What it does:**
1. Verifies source databases exist and are valid
2. Creates timestamped backup of all databases
3. Executes individual migration scripts in order
4. Verifies migration success
5. Logs everything to timestamped log file

### 2. Individual Migration Scripts

#### migrate_universe.sh
Splits config.db → universe.db + config.db

- Copies `securities`, `country_groups`, `industry_groups` to universe.db
- Leaves `settings` and `allocation_targets` in config.db
- Verifies row counts match

#### migrate_portfolio.sh
Consolidates state.db + calculations.db + snapshots.db → portfolio.db

- Migrates `positions` from state.db
- Migrates `scores` from state.db or calculations.db
- Migrates `calculated_metrics` from calculations.db
- Migrates `portfolio_snapshots` from snapshots.db or state.db
- Handles missing source databases gracefully

#### migrate_ledger.sh
Expands ledger.db with dividend data

- Migrates `dividend_history` from dividends.db
- Migrates `drip_tracking` from dividends.db
- Preserves existing trades and cash_flows

#### migrate_history.sh
Consolidates 65+ history/{SYMBOL}.db → single history.db

- Processes each per-symbol database
- Adds symbol column to consolidated table
- Verifies row counts for each symbol
- Reports migration summary

#### migrate_cache.sh
Moves recommendations to cache.db

- Migrates `recommendations` from config.db
- Also checks standalone recommendations.db if it exists
- Creates ephemeral cache structure

### 3. Verification Script
**File:** `verify_migration.sh`

Comprehensive post-migration verification.

```bash
./verify_migration.sh ../../../data
```

**Checks:**
- Database integrity (PRAGMA integrity_check)
- Table existence and row counts
- Data migration accuracy (source vs destination counts)
- Cross-database consistency

## Migration Process

### Pre-Migration Checklist

- [ ] Review all migration scripts
- [ ] Test on copy of production data
- [ ] Verify go application compiles with new architecture
- [ ] Ensure sufficient disk space (at least 2x current usage)
- [ ] Stop all running trader processes
- [ ] Document current database sizes

### Step 1: Verification

```bash
cd /Users/aristath/arduino-trader/trader/scripts/migration

# Verify source databases
./migrate_databases.sh --verify-only
```

Expected output:
- ✅ All critical databases found
- ✅ Integrity checks pass
- ⚠️ Warnings about optional databases are OK

### Step 2: Dry Run

```bash
# Simulate migration without changes
./migrate_databases.sh --dry-run
```

This shows what would happen without actually modifying anything.

### Step 3: Backup (Manual - Recommended)

```bash
# Create manual backup before migration
cd /Users/aristath/arduino-trader/data
tar -czf ~/backups/trader_pre_migration_$(date +%Y%m%d).tar.gz *.db history/
```

### Step 4: Execute Migration

```bash
cd /Users/aristath/arduino-trader/trader/scripts/migration

# Execute migration (creates automatic backup)
./migrate_databases.sh
```

The script will:
1. Create backup in `data/backups/migration_TIMESTAMP/`
2. Execute all migrations
3. Verify results
4. Report success or failure

### Step 5: Verify Results

```bash
# Run verification script
./verify_migration.sh ../../../data
```

Expected output:
- ✅ All 8 databases pass integrity checks
- ✅ Row counts match between source and destination
- ✅ No critical errors

### Step 6: Test Application

```bash
cd /Users/aristath/arduino-trader/trader

# Build application
go build -o /tmp/trader-test ./cmd/server

# Run with new databases
./trader-test
```

Test critical functions:
- Portfolio display loads
- Securities data accessible
- Historical data queries work
- Planning functions operate correctly

## Rollback Procedure

If migration fails or issues are discovered:

### Option 1: Restore from Automatic Backup

```bash
cd /Users/aristath/arduino-trader/data

# Find the backup directory
ls -la backups/migration_*

# Restore from most recent backup
rm -f *.db *.db-wal *.db-shm
rm -rf history/
cp backups/migration_TIMESTAMP/*.db .
cp -r backups/migration_TIMESTAMP/history .
```

### Option 2: Restore from Manual Backup

```bash
cd /Users/aristath/arduino-trader/data
tar -xzf ~/backups/trader_pre_migration_TIMESTAMP.tar.gz
```

## Troubleshooting

### "Row count mismatch"

**Cause:** Data didn't copy completely
**Action:**
1. Check log file for specific table
2. Verify source database integrity
3. Re-run specific migration script
4. Or restore from backup and re-execute

### "Integrity check failed"

**Cause:** Database corruption
**Action:**
1. DO NOT PROCEED
2. Restore from backup
3. Check source database integrity
4. Report issue for investigation

### "Table not found"

**Cause:** Source database structure different than expected
**Action:**
1. Check if table exists in old database
2. May be expected (optional tables)
3. Verify with verification script

### Migration hangs on history consolidation

**Cause:** Large number of history files
**Action:**
1. This is normal for 65+ files
2. Check progress in log file
3. Process may take 5-10 minutes

## Post-Migration

### Cleanup (After Successful Migration and Testing)

**DO NOT delete old databases until:**
- ✅ Migration verified successful
- ✅ Application tested thoroughly
- ✅ Running in production for at least 1 week
- ✅ Manual backup created

Then:

```bash
cd /Users/aristath/arduino-trader/data

# Archive old databases
mkdir -p archives/pre_migration_$(date +%Y%m%d)
mv state.db calculations.db snapshots.db dividends.db archives/pre_migration_*/
mv recommendations.db archives/pre_migration_*/ 2>/dev/null || true
mv history/ archives/pre_migration_*/

# Keep ledger.db, config.db, satellites.db (still needed with modifications)
```

### Monitoring

After migration, monitor:
- Application logs for database errors
- Query performance
- Database file sizes
- Integrity check results (daily health job)

## Files Reference

| File | Purpose | Size |
|------|---------|------|
| migrate_databases.sh | Main orchestrator | ~5KB |
| migrate_universe.sh | Universe split | ~2KB |
| migrate_portfolio.sh | Portfolio consolidation | ~3KB |
| migrate_ledger.sh | Ledger expansion | ~2KB |
| migrate_history.sh | History consolidation | ~4KB |
| migrate_cache.sh | Cache migration | ~2KB |
| verify_migration.sh | Verification | ~5KB |
| README.md | This file | ~10KB |

## Support

If you encounter issues during migration:

1. **Check the log file:** `migration_TIMESTAMP.log`
2. **Review backup location:** `data/backups/migration_TIMESTAMP/`
3. **Verify source databases:** `./migrate_databases.sh --verify-only`
4. **DO NOT DELETE backups** until migration is confirmed successful

## Success Criteria

Migration is successful when:
- ✅ All migration scripts complete without errors
- ✅ Verification script reports 0 errors
- ✅ Application starts and runs without database errors
- ✅ All critical functions work (portfolio, trading, planning)
- ✅ Row counts match between old and new databases
- ✅ Database integrity checks pass for all 8 databases

## Timeline

Estimated migration time:
- Verification: 1 minute
- Backup creation: 2-5 minutes
- Universe migration: < 1 minute
- Portfolio consolidation: 1-2 minutes
- Ledger expansion: < 1 minute
- History consolidation: 5-10 minutes (depends on number of symbols)
- Cache migration: < 1 minute
- Verification: 1-2 minutes

**Total: 15-25 minutes**

## Architecture Benefits Post-Migration

1. **Cleaner separation** - Each database has clear purpose
2. **Better ACID guarantees** - Related data in same database
3. **Easier backups** - 8 files vs 65+ files
4. **Automatic cleanup** - Grace period system for removed securities
5. **Improved maintainability** - Clear data ownership
6. **Better performance** - Consolidated queries, fewer file handles
7. **Production-ready** - Health monitoring, auto-recovery built in
