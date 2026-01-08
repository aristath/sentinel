//go:build integration
// +build integration

package universe

import (
	"testing"

	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/modules/scoring/scorers"
	"github.com/aristath/sentinel/pkg/formulas"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestScoreCalculation_SavesAllRawValues(t *testing.T) {
	// Create in-memory database
	db, err := database.New(database.Config{
		Path:    ":memory:",
		Profile: database.ProfileStandard,
		Name:    "test",
	})
	require.NoError(t, err)
	defer db.Close()

	// Create scores table with all columns (ISIN as PRIMARY KEY, matching migration 030)
	// Drop table first to ensure clean state
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

	// Create scoring service
	scorer := scorers.NewSecurityScorer()

	// Create test data that will produce raw values
	dailyPrices := make([]float64, 250)
	basePrice := 100.0
	for i := range dailyPrices {
		// Simulate price movement
		if i%10 < 5 {
			dailyPrices[i] = basePrice + float64(i)*0.2 + float64(i%5)*0.3
		} else {
			dailyPrices[i] = basePrice + float64(i)*0.2 - float64(i%5)*0.2
		}
	}

	monthlyPrices := make([]formulas.MonthlyPrice, 60)
	for i := range monthlyPrices {
		monthlyPrices[i] = formulas.MonthlyPrice{
			YearMonth:   "2019-01",
			AvgAdjClose: 100.0 + float64(i)*0.5,
		}
	}

	// Create scoring input
	scoringInput := scorers.ScoreSecurityInput{
		Symbol:        "TEST",
		DailyPrices:   dailyPrices,
		MonthlyPrices: monthlyPrices,
		DividendYield: floatPtr(0.065), // 6.5% yield for dividend bonus
		PERatio:       floatPtr(15.0),
		ProfitMargin:  floatPtr(0.15),
		DebtToEquity:  floatPtr(30.0),
		CurrentRatio:  floatPtr(2.5),
	}

	// Calculate score
	calculatedScore := scorer.ScoreSecurityWithDefaults(scoringInput)

	// Convert to SecurityScore
	score := ConvertToSecurityScore("TEST12345678", "TEST", calculatedScore)

	// Verify raw values are extracted (some may be 0.0 if calculation fails or data is insufficient)
	assert.GreaterOrEqual(t, score.SharpeScore, 0.0, "SharpeScore should be >= 0")
	assert.LessOrEqual(t, score.DrawdownScore, 0.0, "DrawdownScore should be <= 0 (negative value)")
	assert.GreaterOrEqual(t, score.FinancialStrengthScore, 0.0, "FinancialStrengthScore should be >= 0")
	assert.GreaterOrEqual(t, score.RSI, 0.0, "RSI should be >= 0")
	assert.LessOrEqual(t, score.RSI, 100.0, "RSI should be <= 100")
	assert.GreaterOrEqual(t, score.EMA200, 0.0, "EMA200 should be >= 0")
	assert.GreaterOrEqual(t, score.Below52wHighPct, 0.0, "Below52wHighPct should be >= 0")
	assert.Equal(t, 0.10, score.DividendBonus, "DividendBonus should be 0.10 for 6.5% yield")

	// Save to database
	repo := NewScoreRepository(db.Conn(), zerolog.Nop())
	err = repo.Upsert(score)
	require.NoError(t, err)

	// Retrieve from database (using ISIN directly)
	retrieved, err := repo.GetByISIN("TEST12345678")
	require.NoError(t, err)
	require.NotNil(t, retrieved)

	// Verify all raw values are persisted
	assert.Equal(t, score.SharpeScore, retrieved.SharpeScore, "SharpeScore should be persisted")
	assert.Equal(t, score.DrawdownScore, retrieved.DrawdownScore, "DrawdownScore should be persisted")
	assert.Equal(t, score.FinancialStrengthScore, retrieved.FinancialStrengthScore, "FinancialStrengthScore should be persisted")
	assert.Equal(t, score.RSI, retrieved.RSI, "RSI should be persisted")
	assert.Equal(t, score.EMA200, retrieved.EMA200, "EMA200 should be persisted")
	assert.Equal(t, score.Below52wHighPct, retrieved.Below52wHighPct, "Below52wHighPct should be persisted")
	assert.Equal(t, score.DividendBonus, retrieved.DividendBonus, "DividendBonus should be persisted")

	// Verify other fields are also persisted
	assert.Equal(t, score.TotalScore, retrieved.TotalScore)
	assert.Equal(t, score.QualityScore, retrieved.QualityScore)
	assert.Equal(t, score.OpportunityScore, retrieved.OpportunityScore)
}
