package cash_flows

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// Repository handles cash flow persistence
// Faithful translation from Python: app/modules/cash_flows/database/cash_flow_repository.py
type Repository struct {
	ledgerDB *sql.DB
	log      zerolog.Logger
}

// NewRepository creates a new cash flow repository
func NewRepository(ledgerDB *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		ledgerDB: ledgerDB,
		log:      log.With().Str("repo", "cash_flows").Logger(),
	}
}

// BalancePoint represents a point in cash balance history
type BalancePoint struct {
	Date    string  `json:"date"`
	Balance float64 `json:"balance"`
}

// Create inserts a new cash flow
func (r *Repository) Create(cashFlow *CashFlow) (*CashFlow, error) {
	query := `
		INSERT INTO cash_flows (
			transaction_id, type_doc_id, transaction_type, date, amount, currency,
			amount_eur, status, status_c, description, params_json, created_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	createdAt := time.Now().Format("2006-01-02 15:04:05")

	result, err := r.ledgerDB.Exec(
		query,
		cashFlow.TransactionID,
		cashFlow.TypeDocID,
		cashFlow.TransactionType,
		cashFlow.Date,
		cashFlow.Amount,
		cashFlow.Currency,
		cashFlow.AmountEUR,
		cashFlow.Status,
		cashFlow.StatusC,
		cashFlow.Description,
		cashFlow.ParamsJSON,
		createdAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to insert cash flow: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return nil, fmt.Errorf("failed to get last insert ID: %w", err)
	}

	cashFlow.ID = int(id)
	cashFlow.CreatedAt, _ = time.Parse("2006-01-02 15:04:05", createdAt)

	return cashFlow, nil
}

// GetByTransactionID retrieves a cash flow by transaction ID
func (r *Repository) GetByTransactionID(transactionID string) (*CashFlow, error) {
	query := `
		SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
		       amount_eur, status, status_c, description, params_json, created_at
		FROM cash_flows
		WHERE transaction_id = ?
	`

	var cf CashFlow
	var createdAt string

	err := r.ledgerDB.QueryRow(query, transactionID).Scan(
		&cf.ID,
		&cf.TransactionID,
		&cf.TypeDocID,
		&cf.TransactionType,
		&cf.Date,
		&cf.Amount,
		&cf.Currency,
		&cf.AmountEUR,
		&cf.Status,
		&cf.StatusC,
		&cf.Description,
		&cf.ParamsJSON,
		&createdAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get cash flow: %w", err)
	}

	cf.CreatedAt, _ = time.Parse("2006-01-02 15:04:05", createdAt)
	return &cf, nil
}

// Exists checks if a transaction ID exists
func (r *Repository) Exists(transactionID string) (bool, error) {
	var count int
	err := r.ledgerDB.QueryRow("SELECT COUNT(*) FROM cash_flows WHERE transaction_id = ?", transactionID).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check existence: %w", err)
	}
	return count > 0, nil
}

// GetAll retrieves all cash flows with optional limit
func (r *Repository) GetAll(limit *int) ([]CashFlow, error) {
	query := "SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency, amount_eur, status, status_c, description, params_json, created_at FROM cash_flows ORDER BY date DESC"

	if limit != nil {
		query += fmt.Sprintf(" LIMIT %d", *limit)
	}

	rows, err := r.ledgerDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query cash flows: %w", err)
	}
	defer rows.Close()

	return r.scanCashFlows(rows)
}

// GetByDateRange retrieves cash flows within a date range
func (r *Repository) GetByDateRange(startDate, endDate string) ([]CashFlow, error) {
	query := `
		SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
		       amount_eur, status, status_c, description, params_json, created_at
		FROM cash_flows
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`

	rows, err := r.ledgerDB.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query by date range: %w", err)
	}
	defer rows.Close()

	return r.scanCashFlows(rows)
}

// GetByType retrieves cash flows by transaction type
func (r *Repository) GetByType(txType string) ([]CashFlow, error) {
	query := `
		SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
		       amount_eur, status, status_c, description, params_json, created_at
		FROM cash_flows
		WHERE transaction_type = ?
		ORDER BY date DESC
	`

	rows, err := r.ledgerDB.Query(query, txType)
	if err != nil {
		return nil, fmt.Errorf("failed to query by type: %w", err)
	}
	defer rows.Close()

	return r.scanCashFlows(rows)
}

// SyncFromAPI syncs transactions from API, returns count of newly inserted
func (r *Repository) SyncFromAPI(transactions []APITransaction) (int, error) {
	syncedCount := 0

	for _, tx := range transactions {
		// Check if already exists
		exists, err := r.Exists(tx.TransactionID)
		if err != nil {
			r.log.Error().Err(err).Str("tx_id", tx.TransactionID).Msg("Failed to check existence")
			continue
		}
		if exists {
			continue
		}

		// Create cash flow
		cashFlow := &CashFlow{
			TransactionID:   tx.TransactionID,
			TypeDocID:       tx.TypeDocID,
			TransactionType: &tx.TransactionType,
			Date:            tx.Date,
			Amount:          tx.Amount,
			Currency:        tx.Currency,
			AmountEUR:       tx.AmountEUR,
			Status:          &tx.Status,
			StatusC:         &tx.StatusC,
			Description:     &tx.Description,
		}

		// Serialize params to JSON
		if len(tx.Params) > 0 {
			paramsJSON, _ := json.Marshal(tx.Params)
			paramsStr := string(paramsJSON)
			cashFlow.ParamsJSON = &paramsStr
		}

		_, err = r.Create(cashFlow)
		if err != nil {
			r.log.Error().Err(err).Msg("Failed to create cash flow during sync")
			continue
		}
		syncedCount++
	}

	return syncedCount, nil
}

// GetTotalDeposits calculates total deposits
func (r *Repository) GetTotalDeposits() (float64, error) {
	query := `
		SELECT COALESCE(SUM(amount_eur), 0)
		FROM cash_flows
		WHERE LOWER(transaction_type) LIKE '%deposit%'
		   OR LOWER(transaction_type) LIKE '%refill%'
	`

	var total float64
	err := r.ledgerDB.QueryRow(query).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get total deposits: %w", err)
	}
	return total, nil
}

// GetTotalWithdrawals calculates total withdrawals
func (r *Repository) GetTotalWithdrawals() (float64, error) {
	query := `
		SELECT COALESCE(SUM(ABS(amount_eur)), 0)
		FROM cash_flows
		WHERE LOWER(transaction_type) LIKE '%withdrawal%'
	`

	var total float64
	err := r.ledgerDB.QueryRow(query).Scan(&total)
	if err != nil {
		return 0, fmt.Errorf("failed to get total withdrawals: %w", err)
	}
	return total, nil
}

// GetCashBalanceHistory calculates running cash balance
func (r *Repository) GetCashBalanceHistory(startDate, endDate string, initialCash float64) ([]BalancePoint, error) {
	query := `
		SELECT date, SUM(
			CASE
				WHEN LOWER(transaction_type) LIKE '%deposit%' OR LOWER(transaction_type) LIKE '%dividend%' THEN amount_eur
				WHEN LOWER(transaction_type) LIKE '%withdrawal%' THEN -ABS(amount_eur)
				ELSE 0
			END
		) as daily_flow
		FROM cash_flows
		WHERE date >= ? AND date <= ?
		GROUP BY date
		ORDER BY date ASC
	`

	rows, err := r.ledgerDB.Query(query, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query balance history: %w", err)
	}
	defer rows.Close()

	var points []BalancePoint
	runningBalance := initialCash

	for rows.Next() {
		var date string
		var dailyFlow float64

		if err := rows.Scan(&date, &dailyFlow); err != nil {
			return nil, fmt.Errorf("failed to scan balance point: %w", err)
		}

		runningBalance += dailyFlow
		points = append(points, BalancePoint{
			Date:    date,
			Balance: runningBalance,
		})
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating balance history: %w", err)
	}

	return points, nil
}

// scanCashFlows is a helper to scan multiple cash flows
func (r *Repository) scanCashFlows(rows *sql.Rows) ([]CashFlow, error) {
	var cashFlows []CashFlow

	for rows.Next() {
		var cf CashFlow
		var createdAt string

		err := rows.Scan(
			&cf.ID,
			&cf.TransactionID,
			&cf.TypeDocID,
			&cf.TransactionType,
			&cf.Date,
			&cf.Amount,
			&cf.Currency,
			&cf.AmountEUR,
			&cf.Status,
			&cf.StatusC,
			&cf.Description,
			&cf.ParamsJSON,
			&createdAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan cash flow: %w", err)
		}

		cf.CreatedAt, _ = time.Parse("2006-01-02 15:04:05", createdAt)
		cashFlows = append(cashFlows, cf)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating cash flows: %w", err)
	}

	return cashFlows, nil
}
