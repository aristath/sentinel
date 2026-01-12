package repository

import (
	"os"
	"testing"

	"github.com/aristath/sentinel/internal/database"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// setupTestDB creates a temporary test database with the dismissed_filters table.
func setupTestDB(t *testing.T) (*database.DB, func()) {
	t.Helper()

	// Create temporary file
	tmpFile, err := os.CreateTemp("", "test_dismissed_filters_*.db")
	require.NoError(t, err)
	tmpPath := tmpFile.Name()
	_ = tmpFile.Close()

	// Create database
	db, err := database.New(database.Config{
		Path:    tmpPath,
		Profile: database.ProfileStandard,
		Name:    "config",
	})
	require.NoError(t, err)

	// Create the dismissed_filters table (from config_schema.sql)
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS dismissed_filters (
			isin TEXT NOT NULL,
			calculator TEXT NOT NULL,
			reason TEXT NOT NULL,
			PRIMARY KEY (isin, calculator, reason)
		) STRICT
	`)
	require.NoError(t, err)

	// Create index
	_, err = db.Exec(`
		CREATE INDEX IF NOT EXISTS idx_dismissed_filters_isin ON dismissed_filters(isin)
	`)
	require.NoError(t, err)

	// Return cleanup function
	cleanup := func() {
		_ = db.Close()
		_ = os.Remove(tmpPath)
	}

	return db, cleanup
}

func TestDismissedFilterRepository_Dismiss(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewDismissedFilterRepository(db, zerolog.Nop())

	t.Run("dismisses a filter", func(t *testing.T) {
		err := repo.Dismiss("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)

		// Verify it was added
		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)
		assert.True(t, dismissed)
	})

	t.Run("duplicate dismiss is no-op", func(t *testing.T) {
		err := repo.Dismiss("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)

		// Should still be dismissed (no error, no duplicate)
		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)
		assert.True(t, dismissed)
	})

	t.Run("different calculators are separate", func(t *testing.T) {
		err := repo.Dismiss("US0378331005", "averaging_down", "score below minimum")
		require.NoError(t, err)

		// Both should be dismissed independently
		dismissed1, err := repo.IsDismissed("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)
		assert.True(t, dismissed1)

		dismissed2, err := repo.IsDismissed("US0378331005", "averaging_down", "score below minimum")
		require.NoError(t, err)
		assert.True(t, dismissed2)
	})
}

func TestDismissedFilterRepository_Undismiss(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewDismissedFilterRepository(db, zerolog.Nop())

	t.Run("undismisses a filter", func(t *testing.T) {
		// First dismiss
		err := repo.Dismiss("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)

		// Verify dismissed
		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)
		assert.True(t, dismissed)

		// Undismiss
		err = repo.Undismiss("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)

		// Verify undismissed
		dismissed, err = repo.IsDismissed("US0378331005", "opportunity_buys", "score below minimum")
		require.NoError(t, err)
		assert.False(t, dismissed)
	})

	t.Run("undismiss non-existent is no-op", func(t *testing.T) {
		err := repo.Undismiss("NONEXISTENT", "opportunity_buys", "reason")
		require.NoError(t, err) // Should not error
	})
}

func TestDismissedFilterRepository_GetAll(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewDismissedFilterRepository(db, zerolog.Nop())

	t.Run("returns empty map when no dismissals", func(t *testing.T) {
		result, err := repo.GetAll()
		require.NoError(t, err)
		assert.Empty(t, result)
	})

	t.Run("returns all dismissals organized by ISIN and calculator", func(t *testing.T) {
		// Add some dismissals
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "score below minimum")
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "quality gate failed")
		_ = repo.Dismiss("US0378331005", "averaging_down", "recently bought")
		_ = repo.Dismiss("US5949181045", "profit_taking", "recently sold")

		result, err := repo.GetAll()
		require.NoError(t, err)

		// Check structure
		assert.Len(t, result, 2) // Two ISINs

		// AAPL dismissals
		assert.Len(t, result["US0378331005"], 2) // Two calculators
		assert.Len(t, result["US0378331005"]["opportunity_buys"], 2)
		assert.Contains(t, result["US0378331005"]["opportunity_buys"], "score below minimum")
		assert.Contains(t, result["US0378331005"]["opportunity_buys"], "quality gate failed")
		assert.Len(t, result["US0378331005"]["averaging_down"], 1)
		assert.Contains(t, result["US0378331005"]["averaging_down"], "recently bought")

		// MSFT dismissals
		assert.Len(t, result["US5949181045"], 1) // One calculator
		assert.Len(t, result["US5949181045"]["profit_taking"], 1)
		assert.Contains(t, result["US5949181045"]["profit_taking"], "recently sold")
	})
}

func TestDismissedFilterRepository_ClearForSecurity(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewDismissedFilterRepository(db, zerolog.Nop())

	t.Run("clears all dismissals for a security", func(t *testing.T) {
		// Add dismissals for multiple ISINs
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "reason1")
		_ = repo.Dismiss("US0378331005", "averaging_down", "reason2")
		_ = repo.Dismiss("US5949181045", "profit_taking", "reason3")

		// Clear for AAPL
		count, err := repo.ClearForSecurity("US0378331005")
		require.NoError(t, err)
		assert.Equal(t, 2, count)

		// Verify AAPL dismissals are gone
		result, err := repo.GetAll()
		require.NoError(t, err)
		assert.Nil(t, result["US0378331005"])

		// Verify MSFT dismissal remains
		assert.Len(t, result["US5949181045"], 1)
	})

	t.Run("returns 0 when no dismissals for security", func(t *testing.T) {
		count, err := repo.ClearForSecurity("NONEXISTENT")
		require.NoError(t, err)
		assert.Equal(t, 0, count)
	})
}

func TestDismissedFilterRepository_IsDismissed(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewDismissedFilterRepository(db, zerolog.Nop())

	t.Run("returns false when not dismissed", func(t *testing.T) {
		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "reason")
		require.NoError(t, err)
		assert.False(t, dismissed)
	})

	t.Run("returns true when dismissed", func(t *testing.T) {
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "reason")

		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "reason")
		require.NoError(t, err)
		assert.True(t, dismissed)
	})

	t.Run("is specific to calculator", func(t *testing.T) {
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "reason")

		// Same ISIN, different calculator
		dismissed, err := repo.IsDismissed("US0378331005", "averaging_down", "reason")
		require.NoError(t, err)
		assert.False(t, dismissed)
	})

	t.Run("is specific to reason", func(t *testing.T) {
		_ = repo.Dismiss("US0378331005", "opportunity_buys", "reason1")

		// Same ISIN, same calculator, different reason
		dismissed, err := repo.IsDismissed("US0378331005", "opportunity_buys", "reason2")
		require.NoError(t, err)
		assert.False(t, dismissed)
	})
}
