-- Migration 011: Remove bucket_balances table
--
-- IMPORTANT: Only run this migration after:
-- 1. Successfully running the migration script (migrate_bucket_balances_to_positions.go)
-- 2. Running the verification script (verify_cash_migration.go)
-- 3. Monitoring the application for 48+ hours of stable operation
-- 4. Confirming cash positions are working correctly
--
-- This migration is part of the cash-as-securities architecture that treats
-- cash balances as synthetic securities (product_type='CASH') and stores them
-- as positions in the portfolio.db instead of bucket_balances in satellites.db.
--
-- Rollback: If needed, bucket_balances can be reconstructed from cash positions
-- using: SELECT * FROM positions WHERE symbol LIKE 'CASH:%'

-- Drop the bucket_balances table (cash now stored as positions)
DROP TABLE IF EXISTS bucket_balances;

-- Note: The buckets table remains unchanged - it still tracks bucket metadata
-- Cash allocations are now represented as cash positions (CASH:EUR:core, etc.)
