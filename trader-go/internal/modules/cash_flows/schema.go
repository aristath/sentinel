package cash_flows

import "database/sql"

// InitSchema ensures cash_flows table exists in ledger.db
// Faithful translation from Python: app/core/database/schemas.py (LEDGER_SCHEMA)
const CashFlowsSchema = `
CREATE TABLE IF NOT EXISTS cash_flows (
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
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows(date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_type ON cash_flows(transaction_type);
`

func InitSchema(db *sql.DB) error {
	_, err := db.Exec(CashFlowsSchema)
	return err
}
