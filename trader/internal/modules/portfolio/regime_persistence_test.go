package portfolio

import (
	"database/sql"
	"os"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestDB(t *testing.T) *sql.DB {
	// Create temporary database
	tmpfile, err := os.CreateTemp("", "test_regime_*.db")
	require.NoError(t, err)
	tmpfile.Close()

	db, err := sql.Open("sqlite3", tmpfile.Name())
	require.NoError(t, err)

	// Create table
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS market_regime_history (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			recorded_at TEXT NOT NULL,
			raw_score REAL NOT NULL,
			smoothed_score REAL NOT NULL,
			discrete_regime TEXT NOT NULL,
			created_at TEXT DEFAULT CURRENT_TIMESTAMP
		);
		CREATE INDEX IF NOT EXISTS idx_regime_history_recorded ON market_regime_history(recorded_at DESC);
	`)
	require.NoError(t, err)

	t.Cleanup(func() {
		db.Close()
		os.Remove(tmpfile.Name())
	})

	return db
}

func TestGetCurrentRegimeScore(t *testing.T) {
	db := setupTestDB(t)
	persistence := NewRegimePersistence(db, zerolog.Nop())

	t.Run("No history returns neutral", func(t *testing.T) {
		score, err := persistence.GetCurrentRegimeScore()
		require.NoError(t, err)
		assert.Equal(t, NeutralScore, score)
	})

	t.Run("Returns last smoothed score", func(t *testing.T) {
		// Insert test data
		_, err := db.Exec(`
			INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score, discrete_regime)
			VALUES (?, ?, ?, ?)
		`, time.Now().Format(time.RFC3339), 0.5, 0.45, "bull")
		require.NoError(t, err)

		score, err := persistence.GetCurrentRegimeScore()
		require.NoError(t, err)
		assert.InDelta(t, 0.45, float64(score), 0.01)
	})
}

func TestRecordRegimeScore(t *testing.T) {
	db := setupTestDB(t)
	persistence := NewRegimePersistence(db, zerolog.Nop())

	t.Run("First score recorded without smoothing", func(t *testing.T) {
		err := persistence.RecordRegimeScore(0.5)
		require.NoError(t, err)

		var raw, smoothed float64
		var discrete string
		err = db.QueryRow(`
			SELECT raw_score, smoothed_score, discrete_regime
			FROM market_regime_history
			ORDER BY recorded_at DESC LIMIT 1
		`).Scan(&raw, &smoothed, &discrete)
		require.NoError(t, err)

		assert.Equal(t, 0.5, raw)
		assert.Equal(t, 0.5, smoothed) // First score, no smoothing
		assert.Equal(t, "bull", discrete)
	})

	t.Run("Second score applies smoothing", func(t *testing.T) {
		// Clear any existing data from previous subtests
		_, err := db.Exec("DELETE FROM market_regime_history")
		require.NoError(t, err)

		// First score
		err = persistence.RecordRegimeScore(0.2)
		require.NoError(t, err)

		// Verify first score was stored correctly
		var firstSmoothed float64
		err = db.QueryRow(`
			SELECT smoothed_score
			FROM market_regime_history
			ORDER BY recorded_at ASC LIMIT 1
		`).Scan(&firstSmoothed)
		require.NoError(t, err)
		assert.Equal(t, 0.2, firstSmoothed, "First score should be stored as-is")

		// Get current score before second record
		currentBefore, err := persistence.GetCurrentRegimeScore()
		require.NoError(t, err)
		assert.Equal(t, MarketRegimeScore(0.2), currentBefore, "Current score should be 0.2")

		// Second score (should smooth with first)
		err = persistence.RecordRegimeScore(0.8)
		require.NoError(t, err)

		var smoothed float64
		err = db.QueryRow(`
			SELECT smoothed_score
			FROM market_regime_history
			ORDER BY recorded_at DESC LIMIT 1
		`).Scan(&smoothed)
		require.NoError(t, err)

		// Should be smoothed: 0.1 * 0.8 + 0.9 * 0.2 = 0.26
		assert.InDelta(t, 0.26, smoothed, 0.01,
			"Smoothed score should be 0.26 (0.1*0.8 + 0.9*0.2), got %.3f", smoothed)
	})
}

func TestGetScoreChange(t *testing.T) {
	db := setupTestDB(t)
	persistence := NewRegimePersistence(db, zerolog.Nop())

	t.Run("No history returns zero", func(t *testing.T) {
		change, err := persistence.GetScoreChange()
		require.NoError(t, err)
		assert.Equal(t, 0.0, change)
	})

	t.Run("Single entry returns zero", func(t *testing.T) {
		_, err := db.Exec(`
			INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score, discrete_regime)
			VALUES (?, ?, ?, ?)
		`, time.Now().Format(time.RFC3339), 0.5, 0.5, "bull")
		require.NoError(t, err)

		change, err := persistence.GetScoreChange()
		require.NoError(t, err)
		assert.Equal(t, 0.0, change)
	})

	t.Run("Calculates change correctly", func(t *testing.T) {
		// Clear any existing data from previous subtests
		_, err := db.Exec("DELETE FROM market_regime_history")
		require.NoError(t, err)

		// Insert two entries
		now := time.Now()
		_, err = db.Exec(`
			INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score, discrete_regime)
			VALUES (?, ?, ?, ?), (?, ?, ?, ?)
		`,
			now.Add(-1*time.Hour).Format(time.RFC3339), 0.2, 0.2, "sideways",
			now.Format(time.RFC3339), 0.8, 0.8, "bull")
		require.NoError(t, err)

		change, err := persistence.GetScoreChange()
		require.NoError(t, err)
		assert.InDelta(t, 0.6, change, 0.01) // 0.8 - 0.2
	})
}

func TestGetRegimeHistory(t *testing.T) {
	db := setupTestDB(t)
	persistence := NewRegimePersistence(db, zerolog.Nop())

	t.Run("Returns empty for no history", func(t *testing.T) {
		history, err := persistence.GetRegimeHistory(10)
		require.NoError(t, err)
		assert.Empty(t, history)
	})

	t.Run("Returns recent entries", func(t *testing.T) {
		// Insert multiple entries
		now := time.Now()
		for i := 0; i < 5; i++ {
			_, err := db.Exec(`
				INSERT INTO market_regime_history (recorded_at, raw_score, smoothed_score, discrete_regime)
				VALUES (?, ?, ?, ?)
			`, now.Add(time.Duration(i)*time.Hour).Format(time.RFC3339),
				float64(i)*0.1, float64(i)*0.1, "bull")
			require.NoError(t, err)
		}

		history, err := persistence.GetRegimeHistory(3)
		require.NoError(t, err)
		assert.Len(t, history, 3)

		// Should be in descending order (most recent first)
		assert.Greater(t, history[0].SmoothedScore, history[1].SmoothedScore)
		assert.Greater(t, history[1].SmoothedScore, history[2].SmoothedScore)
	})
}
