package cleanup

import (
	"testing"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestHistoryCleanupJob_OrphanedData(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	t.Run("detects and cleans orphaned symbols", func(t *testing.T) {
		// Create test databases
		tempDir := t.TempDir()

		historyDB, err := database.New(database.Config{
			Path:    tempDir + "/history.db",
			Profile: database.ProfileStandard,
			Name:    "history",
		})
		require.NoError(t, err)
		defer historyDB.Close()

		portfolioDB, err := database.New(database.Config{
			Path:    tempDir + "/portfolio.db",
			Profile: database.ProfileStandard,
			Name:    "portfolio",
		})
		require.NoError(t, err)
		defer portfolioDB.Close()

		universeDB, err := database.New(database.Config{
			Path:    tempDir + "/universe.db",
			Profile: database.ProfileStandard,
			Name:    "universe",
		})
		require.NoError(t, err)
		defer universeDB.Close()

		// Create tables
		_, err = historyDB.Conn().Exec(`
			CREATE TABLE daily_prices (
				symbol TEXT,
				date INTEGER,
				close REAL,
				PRIMARY KEY (symbol, date)
			)
		`)
		require.NoError(t, err)

		_, err = universeDB.Conn().Exec(`
			CREATE TABLE securities (symbol TEXT PRIMARY KEY, name TEXT, active INTEGER)
		`)
		require.NoError(t, err)

		_, err = portfolioDB.Conn().Exec(`
			CREATE TABLE positions (symbol TEXT PRIMARY KEY, quantity REAL)
		`)
		require.NoError(t, err)

		_, err = portfolioDB.Conn().Exec(`
			CREATE TABLE scores (symbol TEXT PRIMARY KEY, quality REAL)
		`)
		require.NoError(t, err)

		_, err = portfolioDB.Conn().Exec(`
			CREATE TABLE calculated_metrics (symbol TEXT PRIMARY KEY, rsi REAL)
		`)
		require.NoError(t, err)

		// Insert active symbol in universe
		_, err = universeDB.Conn().Exec("INSERT INTO securities (symbol, name, active) VALUES ('AAPL', 'Apple Inc', 1)")
		require.NoError(t, err)

		// Insert price data for both active and orphaned symbols
		_, err = historyDB.Conn().Exec(`
			INSERT INTO daily_prices (symbol, date, close)
			VALUES ('AAPL', ?, 150.0), ('ORPHAN', ?, 100.0)
		`, time.Now().Unix(), time.Now().Unix())
		require.NoError(t, err)

		// Insert portfolio data for orphaned symbol
		_, err = portfolioDB.Conn().Exec("INSERT INTO positions (symbol, quantity) VALUES ('ORPHAN', 10)")
		require.NoError(t, err)
		_, err = portfolioDB.Conn().Exec("INSERT INTO scores (symbol, quality) VALUES ('ORPHAN', 0.8)")
		require.NoError(t, err)

		// Create cleanup job
		job := NewHistoryCleanupJob(historyDB, portfolioDB, universeDB, log)

		// Run cleanup
		err = job.Run()
		require.NoError(t, err)

		// Verify active symbol still exists
		var count int
		err = historyDB.Conn().QueryRow("SELECT COUNT(*) FROM daily_prices WHERE symbol = 'AAPL'").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 1, count, "Active symbol should remain")

		// Verify orphaned symbol was cleaned up from history
		err = historyDB.Conn().QueryRow("SELECT COUNT(*) FROM daily_prices WHERE symbol = 'ORPHAN'").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 0, count, "Orphaned symbol should be deleted from history")

		// Verify orphaned symbol was cleaned up from portfolio
		err = portfolioDB.Conn().QueryRow("SELECT COUNT(*) FROM positions WHERE symbol = 'ORPHAN'").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 0, count, "Orphaned symbol should be deleted from positions")

		err = portfolioDB.Conn().QueryRow("SELECT COUNT(*) FROM scores WHERE symbol = 'ORPHAN'").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 0, count, "Orphaned symbol should be deleted from scores")
	})

	t.Run("no orphaned symbols when all symbols are in universe", func(t *testing.T) {
		// Create test databases
		tempDir := t.TempDir()

		historyDB, err := database.New(database.Config{
			Path:    tempDir + "/history.db",
			Profile: database.ProfileStandard,
			Name:    "history",
		})
		require.NoError(t, err)
		defer historyDB.Close()

		portfolioDB, err := database.New(database.Config{
			Path:    tempDir + "/portfolio.db",
			Profile: database.ProfileStandard,
			Name:    "portfolio",
		})
		require.NoError(t, err)
		defer portfolioDB.Close()

		universeDB, err := database.New(database.Config{
			Path:    tempDir + "/universe.db",
			Profile: database.ProfileStandard,
			Name:    "universe",
		})
		require.NoError(t, err)
		defer universeDB.Close()

		// Create tables
		_, err = historyDB.Conn().Exec(`
			CREATE TABLE daily_prices (
				symbol TEXT,
				date INTEGER,
				close REAL,
				PRIMARY KEY (symbol, date)
			)
		`)
		require.NoError(t, err)

		_, err = universeDB.Conn().Exec(`
			CREATE TABLE securities (symbol TEXT PRIMARY KEY, name TEXT, active INTEGER)
		`)
		require.NoError(t, err)

		// Insert active symbols in universe
		_, err = universeDB.Conn().Exec("INSERT INTO securities (symbol, name, active) VALUES ('AAPL', 'Apple Inc', 1), ('GOOGL', 'Google', 1)")
		require.NoError(t, err)

		// Insert price data for all symbols
		_, err = historyDB.Conn().Exec(`
			INSERT INTO daily_prices (symbol, date, close)
			VALUES ('AAPL', ?, 150.0), ('GOOGL', ?, 2800.0)
		`, time.Now().Unix(), time.Now().Unix())
		require.NoError(t, err)

		// Create cleanup job
		job := NewHistoryCleanupJob(historyDB, portfolioDB, universeDB, log)

		// Run cleanup
		err = job.Run()
		require.NoError(t, err)

		// Verify all symbols still exist
		var count int
		err = historyDB.Conn().QueryRow("SELECT COUNT(*) FROM daily_prices").Scan(&count)
		require.NoError(t, err)
		assert.Equal(t, 2, count, "All symbols should remain")
	})
}

func TestHistoryCleanupJob_Name(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Create minimal databases for job construction
	tempDir := t.TempDir()

	historyDB, err := database.New(database.Config{
		Path:    tempDir + "/history.db",
		Profile: database.ProfileStandard,
		Name:    "history",
	})
	require.NoError(t, err)
	defer historyDB.Close()

	portfolioDB, err := database.New(database.Config{
		Path:    tempDir + "/portfolio.db",
		Profile: database.ProfileStandard,
		Name:    "portfolio",
	})
	require.NoError(t, err)
	defer portfolioDB.Close()

	universeDB, err := database.New(database.Config{
		Path:    tempDir + "/universe.db",
		Profile: database.ProfileStandard,
		Name:    "universe",
	})
	require.NoError(t, err)
	defer universeDB.Close()

	job := NewHistoryCleanupJob(historyDB, portfolioDB, universeDB, log)
	assert.Equal(t, "history_cleanup", job.Name())
}
