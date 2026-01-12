// Package repository provides planning data repository functionality.
package repository

import (
	"fmt"

	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
)

// DismissedFilterRepository handles database operations for dismissed pre-filter reasons.
// Database: config.db (dismissed_filters table)
//
// Dismissals are per-ISIN + per-calculator + per-reason (most specific granularity).
// Row exists = dismissed, delete row = re-enabled.
// Dismissals are cleared when a trade (BUY/SELL) is executed on the security.
type DismissedFilterRepository struct {
	db  *database.DB // config.db
	log zerolog.Logger
}

// NewDismissedFilterRepository creates a new dismissed filter repository.
// db parameter should be config.db connection
func NewDismissedFilterRepository(db *database.DB, log zerolog.Logger) *DismissedFilterRepository {
	return &DismissedFilterRepository{
		db:  db,
		log: log.With().Str("component", "dismissed_filter_repository").Logger(),
	}
}

// Dismiss adds a dismissal for a specific pre-filter reason.
// If the dismissal already exists, this is a no-op.
func (r *DismissedFilterRepository) Dismiss(isin, calculator, reason string) error {
	_, err := r.db.Exec(`
		INSERT OR IGNORE INTO dismissed_filters (isin, calculator, reason)
		VALUES (?, ?, ?)
	`, isin, calculator, reason)

	if err != nil {
		return fmt.Errorf("failed to dismiss filter: %w", err)
	}

	r.log.Debug().
		Str("isin", isin).
		Str("calculator", calculator).
		Str("reason", reason).
		Msg("Dismissed pre-filter reason")

	return nil
}

// Undismiss removes a dismissal for a specific pre-filter reason.
// If the dismissal doesn't exist, this is a no-op.
func (r *DismissedFilterRepository) Undismiss(isin, calculator, reason string) error {
	result, err := r.db.Exec(`
		DELETE FROM dismissed_filters
		WHERE isin = ? AND calculator = ? AND reason = ?
	`, isin, calculator, reason)

	if err != nil {
		return fmt.Errorf("failed to undismiss filter: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Debug().
		Str("isin", isin).
		Str("calculator", calculator).
		Str("reason", reason).
		Int64("rows_affected", rowsAffected).
		Msg("Undismissed pre-filter reason")

	return nil
}

// GetAll retrieves all dismissed filters as a nested map.
// Returns map[ISIN][calculator][]reasons
func (r *DismissedFilterRepository) GetAll() (map[string]map[string][]string, error) {
	rows, err := r.db.Query(`
		SELECT isin, calculator, reason
		FROM dismissed_filters
		ORDER BY isin, calculator
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to query dismissed filters: %w", err)
	}
	defer rows.Close()

	result := make(map[string]map[string][]string)

	for rows.Next() {
		var isin, calculator, reason string
		if err := rows.Scan(&isin, &calculator, &reason); err != nil {
			return nil, fmt.Errorf("failed to scan dismissed filter row: %w", err)
		}

		if result[isin] == nil {
			result[isin] = make(map[string][]string)
		}
		result[isin][calculator] = append(result[isin][calculator], reason)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating dismissed filter rows: %w", err)
	}

	r.log.Debug().
		Int("isin_count", len(result)).
		Msg("Retrieved dismissed filters")

	return result, nil
}

// ClearForSecurity removes all dismissals for a specific security (by ISIN).
// This is called after a trade is executed on the security.
// Returns the number of rows deleted.
func (r *DismissedFilterRepository) ClearForSecurity(isin string) (int, error) {
	result, err := r.db.Exec(`
		DELETE FROM dismissed_filters
		WHERE isin = ?
	`, isin)

	if err != nil {
		return 0, fmt.Errorf("failed to clear dismissals for security: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().
		Str("isin", isin).
		Int64("rows_deleted", rowsAffected).
		Msg("Cleared dismissals for security after trade")

	return int(rowsAffected), nil
}

// IsDismissed checks if a specific pre-filter reason is dismissed.
func (r *DismissedFilterRepository) IsDismissed(isin, calculator, reason string) (bool, error) {
	var count int
	err := r.db.QueryRow(`
		SELECT COUNT(*) FROM dismissed_filters
		WHERE isin = ? AND calculator = ? AND reason = ?
	`, isin, calculator, reason).Scan(&count)

	if err != nil {
		return false, fmt.Errorf("failed to check if filter is dismissed: %w", err)
	}

	return count > 0, nil
}
