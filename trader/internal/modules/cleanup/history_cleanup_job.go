package cleanup

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// HistoryCleanupJob implements automatic cleanup of removed securities with grace period
// Runs daily to clean up historical data for securities marked for removal after grace period expires
type HistoryCleanupJob struct {
	historyDB   *database.DB
	portfolioDB *database.DB
	universeDB  *database.DB
	log         zerolog.Logger
}

// NewHistoryCleanupJob creates a new history cleanup job
func NewHistoryCleanupJob(historyDB, portfolioDB, universeDB *database.DB, log zerolog.Logger) *HistoryCleanupJob {
	return &HistoryCleanupJob{
		historyDB:   historyDB,
		portfolioDB: portfolioDB,
		universeDB:  universeDB,
		log:         log.With().Str("job", "history_cleanup").Logger(),
	}
}

// Run executes the cleanup job
func (j *HistoryCleanupJob) Run() error {
	j.log.Info().Msg("Starting history cleanup job")

	// Step 1: Find expired symbols (grace period passed)
	expiredSymbols, err := j.findExpiredSymbols()
	if err != nil {
		return fmt.Errorf("failed to find expired symbols: %w", err)
	}

	if len(expiredSymbols) == 0 {
		j.log.Info().Msg("No expired symbols to clean up")
		return nil
	}

	j.log.Info().Int("count", len(expiredSymbols)).Msg("Found expired symbols")

	// Step 2: Clean up each expired symbol
	cleaned := 0
	errors := 0

	for _, symbol := range expiredSymbols {
		if err := j.cleanupSymbol(symbol); err != nil {
			j.log.Error().
				Err(err).
				Str("symbol", symbol).
				Msg("Failed to cleanup symbol")
			errors++
		} else {
			cleaned++
		}
	}

	// Step 3: Find and cleanup orphaned data (symbols in history/portfolio but not in universe)
	orphaned, err := j.findOrphanedSymbols()
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to find orphaned symbols")
	} else if len(orphaned) > 0 {
		j.log.Warn().Int("count", len(orphaned)).Msg("Found orphaned symbols")
		for _, symbol := range orphaned {
			if err := j.cleanupSymbol(symbol); err != nil {
				j.log.Error().
					Err(err).
					Str("symbol", symbol).
					Msg("Failed to cleanup orphaned symbol")
				errors++
			} else {
				cleaned++
			}
		}
	}

	j.log.Info().
		Int("cleaned", cleaned).
		Int("errors", errors).
		Msg("History cleanup job completed")

	if errors > 0 {
		return fmt.Errorf("cleanup completed with %d errors", errors)
	}

	return nil
}

// findExpiredSymbols returns symbols marked for removal with expired grace period
func (j *HistoryCleanupJob) findExpiredSymbols() ([]string, error) {
	now := time.Now().Unix()

	query := `
		SELECT symbol, removed_at, grace_period_days
		FROM symbol_removals
		WHERE removed_at + (grace_period_days * 86400) < ?
	`

	rows, err := j.historyDB.Conn().Query(query, now)
	if err != nil {
		return nil, fmt.Errorf("failed to query symbol_removals: %w", err)
	}
	defer rows.Close()

	var symbols []string
	for rows.Next() {
		var symbol string
		var removedAt int64
		var gracePeriodDays int

		if err := rows.Scan(&symbol, &removedAt, &gracePeriodDays); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}

		symbols = append(symbols, symbol)
	}

	return symbols, rows.Err()
}

// findOrphanedSymbols returns symbols present in history/portfolio but not in universe
func (j *HistoryCleanupJob) findOrphanedSymbols() ([]string, error) {
	// Get unique symbols from history.db
	historySymbols := make(map[string]bool)
	rows, err := j.historyDB.Conn().Query("SELECT DISTINCT symbol FROM daily_prices")
	if err != nil {
		return nil, fmt.Errorf("failed to query history symbols: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			return nil, err
		}
		historySymbols[symbol] = true
	}

	// Get active symbols from universe.db
	activeSymbols := make(map[string]bool)
	rows2, err := j.universeDB.Conn().Query("SELECT symbol FROM securities")
	if err != nil {
		return nil, fmt.Errorf("failed to query universe symbols: %w", err)
	}
	defer rows2.Close()

	for rows2.Next() {
		var symbol string
		if err := rows2.Scan(&symbol); err != nil {
			return nil, err
		}
		activeSymbols[symbol] = true
	}

	// Find orphans (in history but not in universe)
	var orphaned []string
	for symbol := range historySymbols {
		if !activeSymbols[symbol] {
			orphaned = append(orphaned, symbol)
		}
	}

	return orphaned, nil
}

// Name returns the job name for scheduler
func (j *HistoryCleanupJob) Name() string {
	return "history_cleanup"
}

// cleanupSymbol removes all data for a symbol across databases
func (j *HistoryCleanupJob) cleanupSymbol(symbol string) error {
	j.log.Info().Str("symbol", symbol).Msg("Cleaning up symbol")

	tx, err := j.historyDB.Conn().Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() {
		_ = tx.Rollback()
	}()

	// Count rows before deletion for logging
	var rowCount int
	err = tx.QueryRow("SELECT COUNT(*) FROM daily_prices WHERE symbol = ?", symbol).Scan(&rowCount)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return fmt.Errorf("failed to count rows: %w", err)
	}

	// Delete from history.db daily_prices
	result, err := tx.Exec("DELETE FROM daily_prices WHERE symbol = ?", symbol)
	if err != nil {
		return fmt.Errorf("failed to delete from daily_prices: %w", err)
	}

	deletedRows, _ := result.RowsAffected()

	// Log to cleanup_log
	_, err = tx.Exec(`
		INSERT INTO cleanup_log (symbol, deleted_at, row_count, cleanup_reason)
		VALUES (?, ?, ?, ?)
	`, symbol, time.Now().Unix(), rowCount, "grace_period_expired")
	if err != nil {
		return fmt.Errorf("failed to log cleanup: %w", err)
	}

	// Remove from symbol_removals
	_, err = tx.Exec("DELETE FROM symbol_removals WHERE symbol = ?", symbol)
	if err != nil {
		return fmt.Errorf("failed to delete from symbol_removals: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	j.log.Info().
		Str("symbol", symbol).
		Int64("rows_deleted", deletedRows).
		Msg("Symbol cleaned up successfully")

	// Clean up from portfolio.db (positions, scores, calculated_metrics)
	if err := j.cleanupPortfolioData(symbol); err != nil {
		j.log.Error().
			Err(err).
			Str("symbol", symbol).
			Msg("Failed to cleanup portfolio data (non-fatal)")
		// Don't return error - history cleanup succeeded
	}

	return nil
}

// cleanupPortfolioData removes portfolio data for a symbol
func (j *HistoryCleanupJob) cleanupPortfolioData(symbol string) error {
	// Delete from positions
	_, err := j.portfolioDB.Conn().Exec("DELETE FROM positions WHERE symbol = ?", symbol)
	if err != nil {
		return fmt.Errorf("failed to delete positions: %w", err)
	}

	// Delete from scores
	_, err = j.portfolioDB.Conn().Exec("DELETE FROM scores WHERE symbol = ?", symbol)
	if err != nil {
		return fmt.Errorf("failed to delete scores: %w", err)
	}

	// Delete from calculated_metrics if table exists
	_, err = j.portfolioDB.Conn().Exec("DELETE FROM calculated_metrics WHERE symbol = ?", symbol)
	if err != nil && !isTableNotExistsError(err) {
		return fmt.Errorf("failed to delete calculated_metrics: %w", err)
	}

	j.log.Debug().
		Str("symbol", symbol).
		Msg("Portfolio data cleaned up")

	return nil
}

// isTableNotExistsError checks if error is due to table not existing
func isTableNotExistsError(err error) bool {
	if err == nil {
		return false
	}
	return err.Error() == "no such table: calculated_metrics"
}
