// Package cash_flows provides repository implementations for managing cash balances and cash flow transactions.
// This file implements the Repository for cash flow transactions, which handles cash flow records stored in ledger.db.
// Cash flows represent deposits, withdrawals, dividends, and other cash movements in the portfolio.
package cash_flows

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"time"

	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// Repository handles cash flow persistence for the immutable audit trail.
// Cash flows are stored in ledger.db and represent deposits, withdrawals, dividends,
// and other cash movements. They form part of the immutable financial audit trail.
//
// The repository validates currency conversion accuracy and provides methods for
// querying cash flows by date range, type, and calculating totals.
//
// Faithful translation from Python: app/modules/cash_flows/database/cash_flow_repository.py
type Repository struct {
	ledgerDB *sql.DB        // ledger.db - cash_flows table (immutable audit trail)
	log      zerolog.Logger // Structured logger
}

// NewRepository creates a new cash flow repository.
// The repository manages cash flow transactions stored in the cash_flows table.
//
// Parameters:
//   - ledgerDB: Database connection to ledger.db
//   - log: Structured logger
//
// Returns:
//   - *Repository: Initialized repository instance
func NewRepository(ledgerDB *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		ledgerDB: ledgerDB,
		log:      log.With().Str("repo", "cash_flows").Logger(),
	}
}

// BalancePoint represents a point in cash balance history.
// Used for generating cash balance charts over time.
type BalancePoint struct {
	Date    string  `json:"date"`    // Date in YYYY-MM-DD format
	Balance float64 `json:"balance"` // Cash balance in EUR at this date
}

// Create inserts a new cash flow into the immutable audit trail.
// This method validates currency conversion accuracy before insertion.
// Dates are converted from YYYY-MM-DD format to Unix timestamps at midnight UTC.
//
// Parameters:
//   - cashFlow: CashFlow object to create
//
// Returns:
//   - *CashFlow: Created cash flow with ID and CreatedAt populated
//   - error: Error if validation fails or database operation fails
func (r *Repository) Create(cashFlow *CashFlow) (*CashFlow, error) {
	// Validate currency conversion accuracy
	if err := r.validateCurrencyConversion(cashFlow); err != nil {
		return nil, err
	}

	query := `
		INSERT INTO cash_flows (
			transaction_id, type_doc_id, transaction_type, date, amount, currency,
			amount_eur, status, status_c, description, params_json, created_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	createdAt := time.Now().Unix()

	// Convert YYYY-MM-DD date string to Unix timestamp at midnight UTC
	dateUnix, err := utils.DateToUnix(cashFlow.Date)
	if err != nil {
		return nil, fmt.Errorf("invalid date format (expected YYYY-MM-DD): %w", err)
	}

	result, err := r.ledgerDB.Exec(
		query,
		cashFlow.TransactionID,
		cashFlow.TypeDocID,
		cashFlow.TransactionType,
		dateUnix,
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
	cashFlow.CreatedAt = time.Unix(createdAt, 0).UTC()

	return cashFlow, nil
}

// validateCurrencyConversion ensures currency conversion accuracy in cash flows.
// For EUR currency, amounts must match exactly. For other currencies, it performs
// sanity checks on the implied exchange rate (warns if suspicious but doesn't fail).
//
// Parameters:
//   - cf: CashFlow object to validate
//
// Returns:
//   - error: Error if EUR conversion mismatch detected
func (r *Repository) validateCurrencyConversion(cf *CashFlow) error {
	// For EUR currency, amounts should match exactly
	if cf.Currency == "EUR" {
		if math.Abs(cf.Amount-cf.AmountEUR) > 0.01 {
			return fmt.Errorf("currency conversion mismatch for EUR: amount=%f but amount_eur=%f",
				cf.Amount, cf.AmountEUR)
		}
	} else if cf.Currency != "" && cf.Amount != 0 {
		// For non-EUR currencies, calculate expected rate and warn if suspicious
		impliedRate := cf.AmountEUR / cf.Amount

		// Sanity check: rate should be positive and within reasonable bounds
		// Typical EUR exchange rates range from ~0.01 to ~100
		if impliedRate <= 0 || impliedRate > 200 || impliedRate < 0.001 {
			r.log.Warn().
				Str("currency", cf.Currency).
				Float64("amount", cf.Amount).
				Float64("amount_eur", cf.AmountEUR).
				Float64("implied_rate", impliedRate).
				Msg("Suspicious currency conversion rate")
		}
	}
	return nil
}

// GetByTransactionID retrieves a cash flow by transaction ID.
// Transaction IDs are unique identifiers from the broker API and are used to prevent duplicates.
//
// Parameters:
//   - transactionID: Broker transaction ID
//
// Returns:
//   - *CashFlow: Cash flow object if found, nil if not found
//   - error: Error if query fails
func (r *Repository) GetByTransactionID(transactionID string) (*CashFlow, error) {
	query := `
		SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
		       amount_eur, status, status_c, description, params_json, created_at
		FROM cash_flows
		WHERE transaction_id = ?
	`

	var cf CashFlow
	var dateUnix sql.NullInt64
	var createdAt sql.NullInt64

	err := r.ledgerDB.QueryRow(query, transactionID).Scan(
		&cf.ID,
		&cf.TransactionID,
		&cf.TypeDocID,
		&cf.TransactionType,
		&dateUnix,
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

	if dateUnix.Valid {
		cf.Date = utils.UnixToDate(dateUnix.Int64)
	}
	if createdAt.Valid {
		cf.CreatedAt = time.Unix(createdAt.Int64, 0).UTC()
	}
	return &cf, nil
}

// Exists checks if a transaction ID exists in the database.
// This is used to prevent duplicate cash flow recording during sync operations.
//
// Parameters:
//   - transactionID: Broker transaction ID
//
// Returns:
//   - bool: True if transaction exists, false otherwise
//   - error: Error if query fails
func (r *Repository) Exists(transactionID string) (bool, error) {
	var count int
	err := r.ledgerDB.QueryRow("SELECT COUNT(*) FROM cash_flows WHERE transaction_id = ?", transactionID).Scan(&count)
	if err != nil {
		return false, fmt.Errorf("failed to check existence: %w", err)
	}
	return count > 0, nil
}

// GetAll retrieves all cash flows with optional limit.
// Results are ordered by date descending (most recent first).
//
// Parameters:
//   - limit: Optional limit on number of results (nil for no limit)
//
// Returns:
//   - []CashFlow: List of cash flows (ordered by date DESC)
//   - error: Error if query fails
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

// GetByDateRange retrieves cash flows within a date range.
// Dates are converted from YYYY-MM-DD format to Unix timestamps at midnight UTC.
// Useful for generating reports or analyzing cash movements over a specific period.
//
// Parameters:
//   - startDate: Start date in YYYY-MM-DD format (inclusive, midnight UTC)
//   - endDate: End date in YYYY-MM-DD format (inclusive, end of day UTC)
//
// Returns:
//   - []CashFlow: List of cash flows within the date range (ordered by date ASC)
//   - error: Error if date parsing fails or query fails
func (r *Repository) GetByDateRange(startDate, endDate string) ([]CashFlow, error) {
	// Convert YYYY-MM-DD to Unix timestamps at midnight UTC
	startUnix, err := utils.DateToUnix(startDate)
	if err != nil {
		return nil, fmt.Errorf("invalid start_date format (expected YYYY-MM-DD): %w", err)
	}

	// End date should be end of day (23:59:59)
	endTime, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid end_date format (expected YYYY-MM-DD): %w", err)
	}
	endUnix := time.Date(endTime.Year(), endTime.Month(), endTime.Day(), 23, 59, 59, 0, time.UTC).Unix()

	query := `
		SELECT id, transaction_id, type_doc_id, transaction_type, date, amount, currency,
		       amount_eur, status, status_c, description, params_json, created_at
		FROM cash_flows
		WHERE date >= ? AND date <= ?
		ORDER BY date ASC
	`

	rows, err := r.ledgerDB.Query(query, startUnix, endUnix)
	if err != nil {
		return nil, fmt.Errorf("failed to query by date range: %w", err)
	}
	defer rows.Close()

	return r.scanCashFlows(rows)
}

// GetByType retrieves cash flows by transaction type.
// Transaction types include deposits, withdrawals, dividends, fees, etc.
//
// Parameters:
//   - txType: Transaction type (e.g., "DEPOSIT", "WITHDRAWAL", "DIVIDEND")
//
// Returns:
//   - []CashFlow: List of cash flows of the specified type (ordered by date DESC)
//   - error: Error if query fails
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

// SyncFromAPI syncs transactions from the broker API.
// This method checks for existing transactions by transaction_id to prevent duplicates,
// then creates new cash flow records for transactions that don't exist yet.
// Returns the count of newly inserted transactions.
//
// Parameters:
//   - transactions: List of API transactions from broker
//
// Returns:
//   - int: Count of newly inserted transactions
//   - error: Error if any transaction creation fails (partial sync may have occurred)
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

// GetTotalDeposits calculates total deposits in EUR.
// Includes transactions with "deposit" or "refill" in the transaction type (case-insensitive).
//
// Returns:
//   - float64: Total deposits in EUR (0.0 if none)
//   - error: Error if query fails
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

// GetTotalWithdrawals calculates total withdrawals in EUR.
// Includes transactions with "withdrawal" in the transaction type (case-insensitive).
// Uses ABS() to ensure positive values even if amounts are stored as negative.
//
// Returns:
//   - float64: Total withdrawals in EUR (0.0 if none)
//   - error: Error if query fails
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

// GetCashBalanceHistory calculates running cash balance over time.
// This method aggregates daily cash flows and calculates a running balance starting
// from initialCash. Useful for generating cash balance charts.
//
// Dates are converted from YYYY-MM-DD format to Unix timestamps at midnight UTC.
// Daily flows are calculated by summing deposits/dividends (positive) and withdrawals (negative).
//
// Parameters:
//   - startDate: Start date in YYYY-MM-DD format (inclusive, midnight UTC)
//   - endDate: End date in YYYY-MM-DD format (inclusive, end of day UTC)
//   - initialCash: Starting cash balance in EUR (before the date range)
//
// Returns:
//   - []BalancePoint: List of balance points with dates and running balances
//   - error: Error if date parsing fails or query fails
func (r *Repository) GetCashBalanceHistory(startDate, endDate string, initialCash float64) ([]BalancePoint, error) {
	// Convert YYYY-MM-DD to Unix timestamps at midnight UTC
	startUnix, err := utils.DateToUnix(startDate)
	if err != nil {
		return nil, fmt.Errorf("invalid start_date format (expected YYYY-MM-DD): %w", err)
	}

	// End date should be end of day (23:59:59)
	endTime, err := time.Parse("2006-01-02", endDate)
	if err != nil {
		return nil, fmt.Errorf("invalid end_date format (expected YYYY-MM-DD): %w", err)
	}
	endUnix := time.Date(endTime.Year(), endTime.Month(), endTime.Day(), 23, 59, 59, 0, time.UTC).Unix()

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

	rows, err := r.ledgerDB.Query(query, startUnix, endUnix)
	if err != nil {
		return nil, fmt.Errorf("failed to query balance history: %w", err)
	}
	defer rows.Close()

	var points []BalancePoint
	runningBalance := initialCash

	for rows.Next() {
		var dateUnix sql.NullInt64
		var dailyFlow float64

		if err := rows.Scan(&dateUnix, &dailyFlow); err != nil {
			return nil, fmt.Errorf("failed to scan balance point: %w", err)
		}

		runningBalance += dailyFlow
		var dateStr string
		if dateUnix.Valid {
			dateStr = utils.UnixToDate(dateUnix.Int64)
		}
		points = append(points, BalancePoint{
			Date:    dateStr,
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
		var dateUnix sql.NullInt64
		var createdAt sql.NullInt64

		err := rows.Scan(
			&cf.ID,
			&cf.TransactionID,
			&cf.TypeDocID,
			&cf.TransactionType,
			&dateUnix,
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

		if dateUnix.Valid {
			cf.Date = utils.UnixToDate(dateUnix.Int64)
		}
		if createdAt.Valid {
			cf.CreatedAt = time.Unix(createdAt.Int64, 0).UTC()
		}
		cashFlows = append(cashFlows, cf)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating cash flows: %w", err)
	}

	return cashFlows, nil
}
