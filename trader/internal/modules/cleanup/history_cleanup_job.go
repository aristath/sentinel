// Package cleanup provides data cleanup and maintenance functionality.
package cleanup

import (
	"fmt"

	"github.com/aristath/portfolioManager/internal/database"
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

	// Find and cleanup orphaned data (ISINs in history/portfolio but not in universe)
	orphaned, err := j.findOrphanedSymbols()
	if err != nil {
		return fmt.Errorf("failed to find orphaned ISINs: %w", err)
	}

	if len(orphaned) == 0 {
		j.log.Info().Msg("No orphaned ISINs to clean up")
		return nil
	}

	j.log.Info().Int("count", len(orphaned)).Msg("Found orphaned ISINs")

	// Clean up each orphaned ISIN immediately
	cleaned := 0
	errors := 0

	for _, isin := range orphaned {
		if err := j.cleanupSymbol(isin); err != nil {
			j.log.Error().
				Err(err).
				Str("isin", isin).
				Msg("Failed to cleanup orphaned ISIN")
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

// findOrphanedSymbols returns ISINs present in history/portfolio but not in universe
func (j *HistoryCleanupJob) findOrphanedSymbols() ([]string, error) {
	// Get unique ISINs from history.db
	historyISINs := make(map[string]bool)
	rows, err := j.historyDB.Conn().Query("SELECT DISTINCT isin FROM daily_prices")
	if err != nil {
		return nil, fmt.Errorf("failed to query history ISINs: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		if err := rows.Scan(&isin); err != nil {
			return nil, err
		}
		historyISINs[isin] = true
	}

	// Get active ISINs from universe.db
	activeISINs := make(map[string]bool)
	rows2, err := j.universeDB.Conn().Query("SELECT isin FROM securities WHERE active = 1")
	if err != nil {
		return nil, fmt.Errorf("failed to query universe ISINs: %w", err)
	}
	defer rows2.Close()

	for rows2.Next() {
		var isin string
		if err := rows2.Scan(&isin); err != nil {
			return nil, err
		}
		activeISINs[isin] = true
	}

	// Find orphans (in history but not in universe)
	var orphaned []string
	for isin := range historyISINs {
		if !activeISINs[isin] {
			orphaned = append(orphaned, isin)
		}
	}

	return orphaned, nil
}

// Name returns the job name for scheduler
func (j *HistoryCleanupJob) Name() string {
	return "history_cleanup"
}

// cleanupSymbol removes all data for an ISIN across databases
func (j *HistoryCleanupJob) cleanupSymbol(isin string) error {
	j.log.Info().Str("isin", isin).Msg("Cleaning up orphaned ISIN")

	// Delete from history.db daily_prices
	result, err := j.historyDB.Conn().Exec("DELETE FROM daily_prices WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete from daily_prices: %w", err)
	}

	deletedRows, _ := result.RowsAffected()

	j.log.Info().
		Str("isin", isin).
		Int64("rows_deleted", deletedRows).
		Msg("ISIN cleaned up successfully")

	// Clean up from portfolio.db (positions, scores, calculated_metrics)
	if err := j.cleanupPortfolioData(isin); err != nil {
		j.log.Error().
			Err(err).
			Str("isin", isin).
			Msg("Failed to cleanup portfolio data (non-fatal)")
		// Don't return error - history cleanup succeeded
	}

	return nil
}

// cleanupPortfolioData removes portfolio data for an ISIN
// Note: positions and scores tables use ISIN as PRIMARY KEY, not symbol
func (j *HistoryCleanupJob) cleanupPortfolioData(isin string) error {
	// Delete from positions (ISIN is PRIMARY KEY)
	_, err := j.portfolioDB.Conn().Exec("DELETE FROM positions WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete positions: %w", err)
	}

	// Delete from scores (ISIN is PRIMARY KEY)
	_, err = j.portfolioDB.Conn().Exec("DELETE FROM scores WHERE isin = ?", isin)
	if err != nil {
		return fmt.Errorf("failed to delete scores: %w", err)
	}

	// Delete from calculated_metrics if table exists (legacy table, may not exist)
	_, err = j.portfolioDB.Conn().Exec("DELETE FROM calculated_metrics WHERE symbol = ?", isin)
	if err != nil && !isTableNotExistsError(err) {
		return fmt.Errorf("failed to delete calculated_metrics: %w", err)
	}

	j.log.Debug().
		Str("isin", isin).
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
