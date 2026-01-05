-- Migration 036: Migrate cash_flows table to new schema (ledger.db)
--
-- The cash_flows table has an old schema and needs to be migrated to the new schema
-- that matches the CashFlowsRepository expectations.
--
-- Old schema: id, flow_type, amount, currency, amount_eur, description, executed_at, created_at, date
-- New schema: id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
--             amount_eur, status, status_c, description, params_json, created_at

-- Step 1: Create new cash_flows table with correct schema
CREATE TABLE cash_flows_new (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    type_doc_id INTEGER NOT NULL,
    transaction_type TEXT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    amount_eur REAL NOT NULL,
    status TEXT,
    status_c INTEGER,
    description TEXT,
    params_json TEXT,
    created_at TEXT NOT NULL
) STRICT;

-- Step 2: Migrate data from old schema to new schema
-- Map old columns to new columns with defaults for missing fields
INSERT INTO cash_flows_new (
    id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
    amount_eur, status, status_c, description, params_json, created_at
)
SELECT
    id,
    -- Generate transaction_id from id (old schema doesn't have transaction_id)
    'migrated-' || CAST(id AS TEXT) as transaction_id,
    0 as type_doc_id, -- Default type_doc_id (old schema doesn't have this)
    COALESCE(flow_type, 'UNKNOWN') as transaction_type, -- Map flow_type to transaction_type
    COALESCE(date, executed_at, created_at) as date, -- Use date, executed_at, or created_at
    amount,
    currency,
    amount_eur,
    NULL as status, -- Old schema doesn't have status
    NULL as status_c, -- Old schema doesn't have status_c
    description,
    NULL as params_json, -- Old schema doesn't have params_json
    COALESCE(created_at, datetime('now')) as created_at
FROM cash_flows;

-- Step 3: Drop old table and rename new
DROP TABLE cash_flows;
ALTER TABLE cash_flows_new RENAME TO cash_flows;

-- Step 4: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);
