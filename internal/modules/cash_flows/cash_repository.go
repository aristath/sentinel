// Package cash_flows provides repository implementations for managing cash balances and cash flow transactions.
// This file implements the CashRepository, which handles cash balance persistence in portfolio.db.
// Cash balances represent current holdings in various currencies (EUR, USD, HKD, GBP, etc.).
package cash_flows

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// CashRepository handles cash balance persistence in portfolio.db.
// Cash balances are stored per currency and represent the current cash holdings.
// This follows the "cash-as-balances" architecture where cash is tracked separately
// from positions, allowing for multi-currency portfolios.
type CashRepository struct {
	portfolioDB *sql.DB        // portfolio.db - cash_balances table
	log         zerolog.Logger // Structured logger
}

// NewCashRepository creates a new cash repository.
// The repository manages cash balances stored in the cash_balances table.
//
// Parameters:
//   - portfolioDB: Database connection to portfolio.db
//   - log: Structured logger
//
// Returns:
//   - *CashRepository: Initialized repository instance
func NewCashRepository(portfolioDB *sql.DB, log zerolog.Logger) *CashRepository {
	return &CashRepository{
		portfolioDB: portfolioDB,
		log:         log.With().Str("repo", "cash_balance").Logger(),
	}
}

// Get returns the cash balance for the given currency.
// Returns 0.0 if currency doesn't exist (not an error - zero balance is valid).
//
// Parameters:
//   - currency: Currency code (e.g., "EUR", "USD", "HKD")
//
// Returns:
//   - float64: Cash balance (0.0 if currency not found)
//   - error: Error if query fails
func (r *CashRepository) Get(currency string) (float64, error) {
	var balance float64
	err := r.portfolioDB.QueryRow(
		"SELECT balance FROM cash_balances WHERE currency = ?",
		currency,
	).Scan(&balance)

	if err == sql.ErrNoRows {
		return 0.0, nil // No balance = zero, not an error
	}
	if err != nil {
		return 0.0, fmt.Errorf("failed to get cash balance for %s: %w", currency, err)
	}

	return balance, nil
}

// GetAll returns all cash balances as a map of currency -> balance.
// This is useful for displaying all cash holdings across all currencies.
//
// Returns:
//   - map[string]float64: Map of currency codes to balances
//   - error: Error if query fails
func (r *CashRepository) GetAll() (map[string]float64, error) {
	rows, err := r.portfolioDB.Query("SELECT currency, balance FROM cash_balances")
	if err != nil {
		return nil, fmt.Errorf("failed to query cash balances: %w", err)
	}
	defer rows.Close()

	balances := make(map[string]float64)
	for rows.Next() {
		var currency string
		var balance float64
		if err := rows.Scan(&currency, &balance); err != nil {
			return nil, fmt.Errorf("failed to scan cash balance: %w", err)
		}
		balances[currency] = balance
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating cash balances: %w", err)
	}

	return balances, nil
}

// Upsert inserts or updates a cash balance for the given currency.
// Uses INSERT OR REPLACE to handle both insert and update in a single operation.
// The last_updated timestamp is automatically set to the current time.
//
// Parameters:
//   - currency: Currency code (e.g., "EUR", "USD", "HKD")
//   - balance: Cash balance amount
//
// Returns:
//   - error: Error if database operation fails
func (r *CashRepository) Upsert(currency string, balance float64) error {
	now := time.Now().Unix()

	query := `
		INSERT INTO cash_balances (currency, balance, last_updated)
		VALUES (?, ?, ?)
		ON CONFLICT(currency) DO UPDATE SET
			balance = excluded.balance,
			last_updated = excluded.last_updated
	`

	_, err := r.portfolioDB.Exec(query, currency, balance, now)
	if err != nil {
		return fmt.Errorf("failed to upsert cash balance for %s: %w", currency, err)
	}

	r.log.Debug().
		Str("currency", currency).
		Float64("balance", balance).
		Msg("Upserted cash balance")

	return nil
}

// Delete removes a cash balance for the given currency.
// This operation is idempotent - it does not error if the currency doesn't exist.
// Useful for cleaning up currencies that are no longer in use.
//
// Parameters:
//   - currency: Currency code to delete
//
// Returns:
//   - error: Error if database operation fails
func (r *CashRepository) Delete(currency string) error {
	result, err := r.portfolioDB.Exec("DELETE FROM cash_balances WHERE currency = ?", currency)
	if err != nil {
		return fmt.Errorf("failed to delete cash balance for %s: %w", currency, err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected > 0 {
		r.log.Debug().
			Str("currency", currency).
			Msg("Deleted cash balance")
	}

	return nil
}
