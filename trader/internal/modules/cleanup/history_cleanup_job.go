package cleanup

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/rs/zerolog"
)

// HistoryCleanupJob implements automatic cleanup of orphaned securities
// Runs daily to clean up historical data for symbols not in the universe
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

	// Find and cleanup orphaned data (symbols in history/portfolio but not in universe)
	orphaned, err := j.findOrphanedSymbols()
	if err != nil {
		return fmt.Errorf("failed to find orphaned symbols: %w", err)
	}

	if len(orphaned) == 0 {
		j.log.Info().Msg("No orphaned symbols to clean up")
		return nil
	}

	j.log.Info().Int("count", len(orphaned)).Msg("Found orphaned symbols")

	// Clean up each orphaned symbol immediately
	cleaned := 0
	errors := 0

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

	j.log.Info().
		Int("cleaned", cleaned).
		Int("errors", errors).
		Msg("History cleanup job completed")

	if errors > 0 {
		return fmt.Errorf("cleanup completed with %d errors", errors)
	}

	return nil
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
	j.log.Info().Str("symbol", symbol).Msg("Cleaning up orphaned symbol")

	// Delete from history.db daily_prices
	result, err := j.historyDB.Conn().Exec("DELETE FROM daily_prices WHERE symbol = ?", symbol)
	if err != nil {
		return fmt.Errorf("failed to delete from daily_prices: %w", err)
	}

	deletedRows, _ := result.RowsAffected()

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
