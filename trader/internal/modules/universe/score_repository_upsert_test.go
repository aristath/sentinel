package universe

import (
	"database/sql"
	"testing"
	"time"

	"github.com/aristath/portfolioManager/internal/database"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestUpsert_InsertsAllColumns(t *testing.T) {
	// Create in-memory database
	db, err := database.New(database.Config{
		Path:    ":memory:",
		Profile: database.ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)
	defer db.Close()

	// Create scores table with all columns (ISIN as PRIMARY KEY, matching migration 030)
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

	// Create score with all fields populated (ISIN required)
	now := time.Now()
	score := SecurityScore{
		ISIN:                   "TEST12345678",
		Symbol:                 "TEST",
		TotalScore:             0.75,
		QualityScore:           0.70,
		OpportunityScore:       0.65,
		AnalystScore:           0.60,
		AllocationFitScore:     0.55,
		Volatility:             0.20,
		CAGRScore:              0.15,
		ConsistencyScore:       0.10,
		HistoryYears:           5.0,
		TechnicalScore:         0.50,
		FundamentalScore:       0.45,
		SharpeScore:            1.5,
		DrawdownScore:          -0.15,
		DividendBonus:          0.10,
		FinancialStrengthScore: 0.90,
		RSI:                    45.0,
		EMA200:                 120.5,
		Below52wHighPct:        0.20,
		CalculatedAt:           &now,
	}

	// Upsert
	repo := NewScoreRepository(db.Conn(), zerolog.Nop())
	err = repo.Upsert(score)
	require.NoError(t, err)

	// Verify all columns were inserted using scanScore (using ISIN as key)
	repo2 := NewScoreRepository(db.Conn(), zerolog.Nop())
	rows, err := db.Conn().Query("SELECT "+scoresColumns+" FROM scores WHERE isin = ?", "TEST12345678")
	require.NoError(t, err)
	defer rows.Close()

	require.True(t, rows.Next(), "Should have one row")
	result, err := repo2.scanScore(rows)
	require.NoError(t, err)

	// Verify all values match (ISIN is primary key, symbol is not stored in scores table)
	assert.Equal(t, "TEST12345678", result.ISIN)
	assert.Equal(t, 0.75, result.TotalScore)
	assert.Equal(t, 0.70, result.QualityScore)
	assert.Equal(t, 0.65, result.OpportunityScore)
	assert.Equal(t, 0.60, result.AnalystScore)
	assert.Equal(t, 0.55, result.AllocationFitScore)
	assert.Equal(t, 0.20, result.Volatility)
	assert.Equal(t, 0.15, result.CAGRScore)
	assert.Equal(t, 0.10, result.ConsistencyScore)
	assert.Equal(t, 5.0, result.HistoryYears)
	assert.Equal(t, 0.50, result.TechnicalScore)
	assert.Equal(t, 0.45, result.FundamentalScore)
	assert.Equal(t, 1.5, result.SharpeScore)
	assert.Equal(t, -0.15, result.DrawdownScore)
	assert.Equal(t, 0.10, result.DividendBonus)
	assert.Equal(t, 0.90, result.FinancialStrengthScore)
	assert.Equal(t, 45.0, result.RSI)
	assert.Equal(t, 120.5, result.EMA200)
	assert.Equal(t, 0.20, result.Below52wHighPct)
}

func TestUpsert_HandlesZeroValues(t *testing.T) {
	// Create in-memory database
	db, err := database.New(database.Config{
		Path:    ":memory:",
		Profile: database.ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)
	defer db.Close()

	// Create scores table (ISIN as PRIMARY KEY, matching migration 030)
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

	// Create score with minimal fields
	score := SecurityScore{
		ISIN:       "TEST12345678",
		Symbol:     "TEST",
		TotalScore: 0.50,
	}

	// Upsert
	repo := NewScoreRepository(db.Conn(), zerolog.Nop())
	err = repo.Upsert(score)
	require.NoError(t, err)

	// Verify zero values are inserted as NULL (using ISIN as key)
	var sharpeScore, drawdownScore, dividendBonus, rsi, ema200, below52wHighPct sql.NullFloat64
	err = db.Conn().QueryRow(`
		SELECT sharpe_score, drawdown_score, dividend_bonus, rsi, ema_200, below_52w_high_pct
		FROM scores WHERE isin = ?
	`, "TEST12345678").Scan(&sharpeScore, &drawdownScore, &dividendBonus, &rsi, &ema200, &below52wHighPct)
	require.NoError(t, err)

	// Zero values should be stored as NULL
	assert.False(t, sharpeScore.Valid)
	assert.False(t, drawdownScore.Valid)
	assert.False(t, dividendBonus.Valid)
	assert.False(t, rsi.Valid)
	assert.False(t, ema200.Valid)
	assert.False(t, below52wHighPct.Valid)
}
