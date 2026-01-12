// Package clientdata provides persistent caching for external API client responses.
// All data is stored as JSON blobs with expiration timestamps for cache-first behavior.
package clientdata

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"
)

// AllTables lists all tables in client_data.db for cleanup operations.
var AllTables = []string{
	"alphavantage_overview",
	"alphavantage_balance_sheet",
	"alphavantage_cash_flow",
	"alphavantage_earnings",
	"alphavantage_dividends",
	"alphavantage_etf_profile",
	"alphavantage_insider",
	"alphavantage_economic",
	"openfigi",
	"yahoo_metadata",
	"exchangerate",
	"current_prices",
}

// validTables is a set for O(1) table name validation.
var validTables = func() map[string]bool {
	m := make(map[string]bool, len(AllTables))
	for _, t := range AllTables {
		m[t] = true
	}
	return m
}()

// Repository provides cache operations for client data.
type Repository struct {
	db *sql.DB
}

// NewRepository creates a new client data repository.
func NewRepository(db *sql.DB) *Repository {
	return &Repository{db: db}
}

// validateTable ensures the table name is in our allowed list.
// This prevents SQL injection through table names.
func validateTable(table string) error {
	if !validTables[table] {
		return fmt.Errorf("invalid table name: %s", table)
	}
	return nil
}

// getKeyColumn returns the primary key column name for a table.
// Most tables use "isin", but some use different keys.
func getKeyColumn(table string) string {
	switch table {
	case "alphavantage_economic":
		return "indicator"
	case "exchangerate":
		return "pair"
	default:
		return "isin"
	}
}

// Store saves data with expiration = now + ttl.
// Uses INSERT OR REPLACE to upsert data.
func (r *Repository) Store(table, key string, data interface{}, ttl time.Duration) error {
	if err := validateTable(table); err != nil {
		return err
	}

	// Serialize data to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	// Calculate expiration timestamp
	expiresAt := time.Now().Add(ttl).Unix()

	// Get the key column name for this table
	keyCol := getKeyColumn(table)

	// INSERT OR REPLACE for upsert behavior
	query := fmt.Sprintf(
		"INSERT OR REPLACE INTO %s (%s, data, expires_at) VALUES (?, ?, ?)",
		table, keyCol,
	)

	_, err = r.db.Exec(query, key, string(jsonData), expiresAt)
	if err != nil {
		return fmt.Errorf("failed to store data in %s: %w", table, err)
	}

	return nil
}

// GetIfFresh returns data only if expires_at > now, nil otherwise.
// Returns nil, nil if the key doesn't exist or data is expired.
// Use Get() to retrieve stale data as a fallback when API calls fail.
func (r *Repository) GetIfFresh(table, key string) (json.RawMessage, error) {
	if err := validateTable(table); err != nil {
		return nil, err
	}

	keyCol := getKeyColumn(table)
	now := time.Now().Unix()

	query := fmt.Sprintf(
		"SELECT data FROM %s WHERE %s = ? AND expires_at > ?",
		table, keyCol,
	)

	var data string
	err := r.db.QueryRow(query, key, now).Scan(&data)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get data from %s: %w", table, err)
	}

	return json.RawMessage(data), nil
}

// Get returns data regardless of expiration status.
// Use this as a fallback when API calls fail - stale data is better than no data.
// Returns nil, nil if the key doesn't exist.
func (r *Repository) Get(table, key string) (json.RawMessage, error) {
	if err := validateTable(table); err != nil {
		return nil, err
	}

	keyCol := getKeyColumn(table)

	query := fmt.Sprintf(
		"SELECT data FROM %s WHERE %s = ?",
		table, keyCol,
	)

	var data string
	err := r.db.QueryRow(query, key).Scan(&data)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get data from %s: %w", table, err)
	}

	return json.RawMessage(data), nil
}

// Delete removes a specific entry.
func (r *Repository) Delete(table, key string) error {
	if err := validateTable(table); err != nil {
		return err
	}

	keyCol := getKeyColumn(table)

	query := fmt.Sprintf("DELETE FROM %s WHERE %s = ?", table, keyCol)

	_, err := r.db.Exec(query, key)
	if err != nil {
		return fmt.Errorf("failed to delete from %s: %w", table, err)
	}

	return nil
}

// DeleteExpired removes all rows where expires_at < now.
// Returns the number of rows deleted.
func (r *Repository) DeleteExpired(table string) (int64, error) {
	if err := validateTable(table); err != nil {
		return 0, err
	}

	now := time.Now().Unix()

	query := fmt.Sprintf("DELETE FROM %s WHERE expires_at < ?", table)

	result, err := r.db.Exec(query, now)
	if err != nil {
		return 0, fmt.Errorf("failed to delete expired from %s: %w", table, err)
	}

	deleted, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected for %s: %w", table, err)
	}

	return deleted, nil
}

// DeleteAllExpired removes all expired entries from all tables.
// Returns a map of table name to number of rows deleted.
func (r *Repository) DeleteAllExpired() (map[string]int64, error) {
	results := make(map[string]int64)

	for _, table := range AllTables {
		deleted, err := r.DeleteExpired(table)
		if err != nil {
			return results, fmt.Errorf("failed to delete expired from %s: %w", table, err)
		}
		results[table] = deleted
	}

	return results, nil
}
