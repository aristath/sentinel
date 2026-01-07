package universe

import (
	"testing"
	"time"

	"github.com/aristath/portfolioManager/internal/database"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestScanScore_ScansAllColumns(t *testing.T) {
	// Create in-memory database
	db, err := database.New(database.Config{
		Path:    ":memory:",
		Profile: database.ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)
	defer db.Close()

	// Create scores table with all columns
	_, _ = db.Conn().Exec(`DROP TABLE IF EXISTS scores`)
	_, err = db.Conn().Exec(`
		CREATE TABLE scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			quality_score REAL,
			opportunity_score REAL,
			analyst_score REAL,
			allocation_fit_score REAL,
			volatility REAL,
			cagr_score REAL,
			consistency_score REAL,
			history_years INTEGER,
			technical_score REAL,
			fundamental_score REAL,
			sharpe_score REAL,
			drawdown_score REAL,
			dividend_bonus REAL,
			financial_strength_score REAL,
			rsi REAL,
			ema_200 REAL,
			below_52w_high_pct REAL,
			last_updated TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	// Insert test data with all columns populated (ISIN as first column)
	now := time.Now().Unix()
	_, err = db.Conn().Exec(`
		INSERT INTO scores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, "TEST12345678", 0.75, 0.70, 0.65, 0.60, 0.55, 0.20, 0.15, 0.10, 5, 0.50, 0.45,
		1.5, -0.15, 0.10, 0.90, 45.0, 120.5, 0.20, now)
	require.NoError(t, err)

	// Query and scan (using ISIN as key)
	repo := NewScoreRepository(db.Conn(), zerolog.Nop())
	rows, err := db.Conn().Query("SELECT "+scoresColumns+" FROM scores WHERE isin = ?", "TEST12345678")
	require.NoError(t, err)
	defer rows.Close()

	require.True(t, rows.Next(), "Should have one row")

	score, err := repo.scanScore(rows)
	require.NoError(t, err)

	// Verify all columns are scanned correctly (ISIN is primary key, symbol is not stored)
	assert.Equal(t, "TEST12345678", score.ISIN)
	assert.Equal(t, 0.75, score.TotalScore)
	assert.Equal(t, 0.70, score.QualityScore)
	assert.Equal(t, 0.65, score.OpportunityScore)
	assert.Equal(t, 0.60, score.AnalystScore)
	assert.Equal(t, 0.55, score.AllocationFitScore)
	assert.Equal(t, 0.20, score.Volatility)
	assert.Equal(t, 0.15, score.CAGRScore)
	assert.Equal(t, 0.10, score.ConsistencyScore)
	assert.Equal(t, 5.0, score.HistoryYears)
	assert.Equal(t, 0.50, score.TechnicalScore)
	assert.Equal(t, 0.45, score.FundamentalScore)
	assert.Equal(t, 1.5, score.SharpeScore)
	assert.Equal(t, -0.15, score.DrawdownScore)
	assert.Equal(t, 0.10, score.DividendBonus)
	assert.Equal(t, 0.90, score.FinancialStrengthScore)
	assert.Equal(t, 45.0, score.RSI)
	assert.Equal(t, 120.5, score.EMA200)
	assert.Equal(t, 0.20, score.Below52wHighPct)
	assert.NotNil(t, score.CalculatedAt)
}

func TestScanScore_HandlesNullValues(t *testing.T) {
	// Create in-memory database
	db, err := database.New(database.Config{
		Path:    ":memory:",
		Profile: database.ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)
	defer db.Close()

	// Create scores table
	_, _ = db.Conn().Exec(`DROP TABLE IF EXISTS scores`)
	_, err = db.Conn().Exec(`
		CREATE TABLE scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			quality_score REAL,
			opportunity_score REAL,
			analyst_score REAL,
			allocation_fit_score REAL,
			volatility REAL,
			cagr_score REAL,
			consistency_score REAL,
			history_years INTEGER,
			technical_score REAL,
			fundamental_score REAL,
			sharpe_score REAL,
			drawdown_score REAL,
			dividend_bonus REAL,
			financial_strength_score REAL,
			rsi REAL,
			ema_200 REAL,
			below_52w_high_pct REAL,
			last_updated TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	// Insert test data with NULL values for optional columns (ISIN as key)
	now := time.Now().Unix()
	_, err = db.Conn().Exec(`
		INSERT INTO scores (isin, total_score, last_updated) VALUES (?, ?, ?)
	`, "TEST12345678", 0.50, now)
	require.NoError(t, err)

	// Query and scan
	repo := NewScoreRepository(db.Conn(), zerolog.Nop())
	rows, err := db.Conn().Query("SELECT "+scoresColumns+" FROM scores WHERE isin = ?", "TEST12345678")
	require.NoError(t, err)
	defer rows.Close()

	require.True(t, rows.Next(), "Should have one row")

	score, err := repo.scanScore(rows)
	require.NoError(t, err)

	// Verify NULL values are handled (default to 0.0)
	assert.Equal(t, "TEST12345678", score.ISIN)
	assert.Equal(t, 0.50, score.TotalScore)
	assert.Equal(t, 0.0, score.QualityScore)
	assert.Equal(t, 0.0, score.SharpeScore)
	assert.Equal(t, 0.0, score.DrawdownScore)
	assert.Equal(t, 0.0, score.DividendBonus)
	assert.Equal(t, 0.0, score.RSI)
	assert.Equal(t, 0.0, score.EMA200)
}
