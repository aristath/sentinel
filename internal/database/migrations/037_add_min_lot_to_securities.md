# Migration 037: Add min_lot Column to Securities Table

## Description
Adds `min_lot` (minimum lot size) column to the securities table for storing broker-provided minimum lot sizes. Previously this was stored only in security_overrides as user-configurable data. Now it's base data synced from broker, with user overrides still possible via security_overrides table.

## Changes
- Adds `min_lot INTEGER DEFAULT 1` column to securities table
- Updates universe schema documentation

## SQL
```sql
-- Add min_lot column to securities table
ALTER TABLE securities ADD COLUMN min_lot INTEGER DEFAULT 1;
```

## Rollback
```sql
-- SQLite doesn't support DROP COLUMN directly, requires table rebuild
-- Restore from universe.db backup if needed
```

## Notes
- Default value is 1 (standard lot size)
- Existing securities will get default value of 1
- Broker sync (security:metadata work type) will populate actual values from Tradernet quotes.x_lot
- User overrides via security_overrides table take precedence over base data
- Safe to apply - adds non-nullable column with default value
