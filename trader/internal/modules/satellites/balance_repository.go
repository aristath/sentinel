package satellites

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// BalanceRepository handles operations for bucket balances and transactions
// Faithful translation from Python: app/modules/satellites/database/balance_repository.py
type BalanceRepository struct {
	satellitesDB *sql.DB // satellites.db connection
	log          zerolog.Logger
}

// NewBalanceRepository creates a new balance repository
func NewBalanceRepository(satellitesDB *sql.DB, log zerolog.Logger) *BalanceRepository {
	return &BalanceRepository{
		satellitesDB: satellitesDB,
		log:          log.With().Str("repository", "balance").Logger(),
	}
}

// --- Balance Operations ---

// GetBalance gets balance for a specific bucket and currency
func (r *BalanceRepository) GetBalance(bucketID string, currency string) (*BucketBalance, error) {
	currency = strings.ToUpper(currency)

	query := `SELECT * FROM bucket_balances
	          WHERE bucket_id = ? AND currency = ?`

	row := r.satellitesDB.QueryRow(query, bucketID, currency)

	balance, err := r.scanBalance(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get balance: %w", err)
	}

	return balance, nil
}

// GetAllBalances gets all currency balances for a bucket
func (r *BalanceRepository) GetAllBalances(bucketID string) ([]*BucketBalance, error) {
	query := "SELECT * FROM bucket_balances WHERE bucket_id = ? ORDER BY currency"

	rows, err := r.satellitesDB.Query(query, bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get all balances: %w", err)
	}
	defer rows.Close()

	return r.scanBalances(rows)
}

// GetAllBalancesByCurrency gets balances for all buckets in a specific currency
func (r *BalanceRepository) GetAllBalancesByCurrency(currency string) ([]*BucketBalance, error) {
	currency = strings.ToUpper(currency)

	query := "SELECT * FROM bucket_balances WHERE currency = ? ORDER BY bucket_id"

	rows, err := r.satellitesDB.Query(query, currency)
	if err != nil {
		return nil, fmt.Errorf("failed to get balances by currency: %w", err)
	}
	defer rows.Close()

	return r.scanBalances(rows)
}

// GetTotalByCurrency gets sum of all bucket balances for a currency
// This should equal the actual brokerage balance for that currency
func (r *BalanceRepository) GetTotalByCurrency(currency string) (float64, error) {
	currency = strings.ToUpper(currency)

	query := `SELECT COALESCE(SUM(balance), 0) as total
	          FROM bucket_balances
	          WHERE currency = ?`

	var total float64
	err := r.satellitesDB.QueryRow(query, currency).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get total by currency: %w", err)
	}

	return total, nil
}

// GetAllCurrencies gets all distinct currencies that have balances
func (r *BalanceRepository) GetAllCurrencies() ([]string, error) {
	query := `SELECT DISTINCT currency
	          FROM bucket_balances
	          ORDER BY currency`

	rows, err := r.satellitesDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get all currencies: %w", err)
	}
	defer rows.Close()

	var currencies []string
	for rows.Next() {
		var currency string
		if err := rows.Scan(&currency); err != nil {
			return nil, fmt.Errorf("failed to scan currency: %w", err)
		}
		currencies = append(currencies, currency)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating currencies: %w", err)
	}

	return currencies, nil
}

// GetBalanceAmount gets balance amount, returning 0 if not found
func (r *BalanceRepository) GetBalanceAmount(bucketID string, currency string) (float64, error) {
	balance, err := r.GetBalance(bucketID, currency)
	if err != nil {
		return 0, err
	}
	if balance == nil {
		return 0, nil
	}
	return balance.Balance, nil
}

// SetBalance sets balance to a specific amount (upsert)
func (r *BalanceRepository) SetBalance(bucketID string, currency string, amount float64) (*BucketBalance, error) {
	now := time.Now().Format(time.RFC3339)
	currency = strings.ToUpper(currency)

	query := `INSERT OR REPLACE INTO bucket_balances
	          (bucket_id, currency, balance, last_updated)
	          VALUES (?, ?, ?, ?)`

	_, err := r.satellitesDB.Exec(query, bucketID, currency, amount, now)
	if err != nil {
		return nil, fmt.Errorf("failed to set balance: %w", err)
	}

	r.log.Info().
		Str("bucket_id", bucketID).
		Str("currency", currency).
		Float64("amount", amount).
		Msg("Set balance")

	return &BucketBalance{
		BucketID:    bucketID,
		Currency:    currency,
		Balance:     amount,
		LastUpdated: now,
	}, nil
}

// AdjustBalance adjusts balance by a delta amount
// Creates the balance record if it doesn't exist
func (r *BalanceRepository) AdjustBalance(bucketID string, currency string, delta float64) (*BucketBalance, error) {
	now := time.Now().Format(time.RFC3339)
	currency = strings.ToUpper(currency)

	tx, err := r.satellitesDB.Begin()
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// First, ensure the row exists
	_, err = tx.Exec(
		`INSERT OR IGNORE INTO bucket_balances
		 (bucket_id, currency, balance, last_updated)
		 VALUES (?, ?, 0, ?)`,
		bucketID, currency, now,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to ensure balance row exists: %w", err)
	}

	// Then update with delta
	_, err = tx.Exec(
		`UPDATE bucket_balances
		 SET balance = balance + ?,
		     last_updated = ?
		 WHERE bucket_id = ? AND currency = ?`,
		delta, now, bucketID, currency,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to adjust balance: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().
		Str("bucket_id", bucketID).
		Str("currency", currency).
		Float64("delta", delta).
		Msg("Adjusted balance")

	// Get updated balance
	balance, err := r.GetBalance(bucketID, currency)
	if err != nil {
		return nil, err
	}
	if balance == nil {
		// Should not happen, but handle gracefully
		return &BucketBalance{
			BucketID:    bucketID,
			Currency:    currency,
			Balance:     delta,
			LastUpdated: now,
		}, nil
	}

	return balance, nil
}

// DeleteBalances deletes all balances for a bucket
// Returns number of balance records deleted
func (r *BalanceRepository) DeleteBalances(bucketID string) (int, error) {
	result, err := r.satellitesDB.Exec(
		"DELETE FROM bucket_balances WHERE bucket_id = ?",
		bucketID,
	)
	if err != nil {
		return 0, fmt.Errorf("failed to delete balances: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("bucket_id", bucketID).Int64("count", rowsAffected).Msg("Deleted balances")

	return int(rowsAffected), nil
}

// --- Transaction Operations ---

// RecordTransaction records a transaction in the audit trail
// If tx is provided, uses that transaction; otherwise creates a new one
func (r *BalanceRepository) RecordTransaction(transaction *BucketTransaction, tx *sql.Tx) error {
	now := time.Now().Format(time.RFC3339)
	transaction.CreatedAt = now

	// If no transaction provided, create and manage our own
	ownTx := false
	if tx == nil {
		var err error
		tx, err = r.satellitesDB.Begin()
		if err != nil {
			return fmt.Errorf("failed to begin transaction: %w", err)
		}
		ownTx = true
		defer tx.Rollback()
	}

	query := `INSERT INTO bucket_transactions
	          (bucket_id, type, amount, currency, description, created_at)
	          VALUES (?, ?, ?, ?, ?, ?)`

	result, err := tx.Exec(query,
		transaction.BucketID,
		string(transaction.Type),
		transaction.Amount,
		strings.ToUpper(transaction.Currency),
		transaction.Description,
		transaction.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to insert transaction: %w", err)
	}

	lastID, err := result.LastInsertId()
	if err != nil {
		return fmt.Errorf("failed to get last insert ID: %w", err)
	}
	transaction.ID = &lastID

	// Only commit if we created the transaction
	if ownTx {
		if err := tx.Commit(); err != nil {
			return fmt.Errorf("failed to commit transaction: %w", err)
		}
	}

	r.log.Info().
		Str("bucket_id", transaction.BucketID).
		Str("type", string(transaction.Type)).
		Float64("amount", transaction.Amount).
		Msg("Recorded transaction")

	return nil
}

// GetTransactions gets transactions for a bucket with optional type filter
func (r *BalanceRepository) GetTransactions(bucketID string, limit int, offset int, transactionType *TransactionType) ([]*BucketTransaction, error) {
	var query string
	var args []interface{}

	if transactionType != nil {
		query = `SELECT * FROM bucket_transactions
		         WHERE bucket_id = ? AND type = ?
		         ORDER BY created_at DESC
		         LIMIT ? OFFSET ?`
		args = []interface{}{bucketID, string(*transactionType), limit, offset}
	} else {
		query = `SELECT * FROM bucket_transactions
		         WHERE bucket_id = ?
		         ORDER BY created_at DESC
		         LIMIT ? OFFSET ?`
		args = []interface{}{bucketID, limit, offset}
	}

	rows, err := r.satellitesDB.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to get transactions: %w", err)
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetRecentTransactions gets transactions from the last N days
func (r *BalanceRepository) GetRecentTransactions(bucketID string, days int) ([]*BucketTransaction, error) {
	query := `SELECT * FROM bucket_transactions
	          WHERE bucket_id = ?
	            AND created_at >= datetime('now', ? || ' days')
	          ORDER BY created_at DESC`

	rows, err := r.satellitesDB.Query(query, bucketID, -days)
	if err != nil {
		return nil, fmt.Errorf("failed to get recent transactions: %w", err)
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetTransactionsByType gets all transactions of a specific type across all buckets
func (r *BalanceRepository) GetTransactionsByType(transactionType TransactionType, limit int) ([]*BucketTransaction, error) {
	query := `SELECT * FROM bucket_transactions
	          WHERE type = ?
	          ORDER BY created_at DESC
	          LIMIT ?`

	rows, err := r.satellitesDB.Query(query, string(transactionType), limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get transactions by type: %w", err)
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// DeleteTransactions deletes all transactions for a bucket
// Should typically only be used for cleanup during tests or when retiring a satellite
// Returns number of transactions deleted
func (r *BalanceRepository) DeleteTransactions(bucketID string) (int, error) {
	result, err := r.satellitesDB.Exec(
		"DELETE FROM bucket_transactions WHERE bucket_id = ?",
		bucketID,
	)
	if err != nil {
		return 0, fmt.Errorf("failed to delete transactions: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("bucket_id", bucketID).Int64("count", rowsAffected).Msg("Deleted transactions")

	return int(rowsAffected), nil
}

// --- Allocation Settings ---

// GetAllocationSetting gets an allocation setting value
func (r *BalanceRepository) GetAllocationSetting(key string) (*float64, error) {
	var value float64
	err := r.satellitesDB.QueryRow(
		"SELECT value FROM allocation_settings WHERE key = ?",
		key,
	).Scan(&value)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation setting: %w", err)
	}

	return &value, nil
}

// SetAllocationSetting sets an allocation setting value
func (r *BalanceRepository) SetAllocationSetting(key string, value float64, description *string) error {
	if description != nil {
		query := `INSERT OR REPLACE INTO allocation_settings
		          (key, value, description)
		          VALUES (?, ?, ?)`
		_, err := r.satellitesDB.Exec(query, key, value, *description)
		if err != nil {
			return fmt.Errorf("failed to set allocation setting: %w", err)
		}
	} else {
		query := `UPDATE allocation_settings
		          SET value = ?
		          WHERE key = ?`
		_, err := r.satellitesDB.Exec(query, value, key)
		if err != nil {
			return fmt.Errorf("failed to update allocation setting: %w", err)
		}
	}

	r.log.Info().Str("key", key).Float64("value", value).Msg("Set allocation setting")
	return nil
}

// GetAllAllocationSettings gets all allocation settings as a map
func (r *BalanceRepository) GetAllAllocationSettings() (map[string]float64, error) {
	query := "SELECT key, value FROM allocation_settings"

	rows, err := r.satellitesDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get all allocation settings: %w", err)
	}
	defer rows.Close()

	settings := make(map[string]float64)
	for rows.Next() {
		var key string
		var value float64
		if err := rows.Scan(&key, &value); err != nil {
			return nil, fmt.Errorf("failed to scan allocation setting: %w", err)
		}
		settings[key] = value
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating allocation settings: %w", err)
	}

	return settings, nil
}

// --- Helper Methods ---

// scanBalance scans a single balance row
func (r *BalanceRepository) scanBalance(row interface{ Scan(...interface{}) error }) (*BucketBalance, error) {
	var balance BucketBalance

	err := row.Scan(
		&balance.BucketID,
		&balance.Currency,
		&balance.Balance,
		&balance.LastUpdated,
	)
	if err != nil {
		return nil, err
	}

	return &balance, nil
}

// scanBalances scans multiple balance rows
func (r *BalanceRepository) scanBalances(rows *sql.Rows) ([]*BucketBalance, error) {
	balances := make([]*BucketBalance, 0)

	for rows.Next() {
		balance, err := r.scanBalance(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan balance row: %w", err)
		}
		balances = append(balances, balance)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating balance rows: %w", err)
	}

	return balances, nil
}

// scanTransaction scans a single transaction row
func (r *BalanceRepository) scanTransaction(row interface{ Scan(...interface{}) error }) (*BucketTransaction, error) {
	var tx BucketTransaction
	var id int64
	var typeStr string
	var description sql.NullString

	err := row.Scan(
		&id,
		&tx.BucketID,
		&typeStr,
		&tx.Amount,
		&tx.Currency,
		&description,
		&tx.CreatedAt,
	)
	if err != nil {
		return nil, err
	}

	tx.ID = &id
	tx.Type = TransactionType(typeStr)

	if description.Valid {
		tx.Description = &description.String
	}

	return &tx, nil
}

// scanTransactions scans multiple transaction rows
func (r *BalanceRepository) scanTransactions(rows *sql.Rows) ([]*BucketTransaction, error) {
	transactions := make([]*BucketTransaction, 0)

	for rows.Next() {
		tx, err := r.scanTransaction(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan transaction row: %w", err)
		}
		transactions = append(transactions, tx)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating transaction rows: %w", err)
	}

	return transactions, nil
}
