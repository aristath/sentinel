package universe

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/stretchr/testify/assert"
)

func TestConvertToSecurityScore_ExtractsRawValues(t *testing.T) {
	// Create a CalculatedSecurityScore with all raw values in SubScores
	calculated := &domain.CalculatedSecurityScore{
		Symbol:     "TEST",
		TotalScore: 0.75,
		Volatility: floatPtr(0.20),
		GroupScores: map[string]float64{
			"long_term":       0.80,
			"fundamentals":    0.70,
			"opportunity":     0.65,
			"technicals":      0.60,
			"dividends":       0.55,
			"opinion":         0.50,
			"diversification": 0.45,
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"cagr":       0.85,
				"sharpe":     0.80, // scored
				"sharpe_raw": 1.5,  // raw value
			},
			"short_term": {
				"drawdown":     0.75,  // scored
				"drawdown_raw": -0.15, // raw value (negative)
			},
			"fundamentals": {
				"financial_strength": 0.90,
				"consistency":        0.80,
			},
			"technicals": {
				"rsi":     0.70,  // scored
				"rsi_raw": 45.0,  // raw value (0-100)
				"ema":     0.65,  // scored
				"ema_raw": 120.5, // raw value (price)
			},
			"opportunity": {
				"below_52w_high":     0.60, // scored
				"below_52w_high_raw": 0.20, // raw value (percentage)
			},
			"dividends": {
				"yield":          0.55, // scored
				"consistency":    0.50, // scored
				"dividend_bonus": 0.10, // bonus value
			},
		},
	}

	score := convertToSecurityScore("TEST", calculated)

	// Verify all raw values are extracted
	assert.Equal(t, 1.5, score.SharpeScore, "SharpeScore should be extracted from sharpe_raw")
	assert.Equal(t, -0.15, score.DrawdownScore, "DrawdownScore should be extracted from drawdown_raw")
	assert.Equal(t, 0.90, score.FinancialStrengthScore, "FinancialStrengthScore should be extracted from financial_strength")
	assert.Equal(t, 45.0, score.RSI, "RSI should be extracted from rsi_raw")
	assert.Equal(t, 120.5, score.EMA200, "EMA200 should be extracted from ema_raw")
	assert.Equal(t, 0.20, score.Below52wHighPct, "Below52wHighPct should be extracted from below_52w_high_raw")
	assert.Equal(t, 0.10, score.DividendBonus, "DividendBonus should be extracted from dividend_bonus")

	// Verify other fields are still populated correctly
	assert.Equal(t, 0.75, score.TotalScore)
	assert.Equal(t, 0.20, score.Volatility)
	assert.Equal(t, 0.75, score.QualityScore) // Average of long_term (0.80) and fundamentals (0.70) = 0.75
}

func TestConvertToSecurityScore_HandlesMissingRawValues(t *testing.T) {
	// Create a CalculatedSecurityScore without raw values
	calculated := &domain.CalculatedSecurityScore{
		Symbol:     "TEST",
		TotalScore: 0.50,
		GroupScores: map[string]float64{
			"long_term":    0.50,
			"fundamentals": 0.50,
		},
		SubScores: map[string]map[string]float64{
			"long_term": {
				"sharpe": 0.50, // Only scored, no raw
			},
		},
	}

	score := convertToSecurityScore("TEST", calculated)

	// Missing raw values should default to 0.0
	assert.Equal(t, 0.0, score.SharpeScore, "Missing sharpe_raw should default to 0.0")
	assert.Equal(t, 0.0, score.DrawdownScore, "Missing drawdown_raw should default to 0.0")
	assert.Equal(t, 0.0, score.RSI, "Missing rsi_raw should default to 0.0")
	assert.Equal(t, 0.0, score.EMA200, "Missing ema_raw should default to 0.0")
	assert.Equal(t, 0.0, score.Below52wHighPct, "Missing below_52w_high_raw should default to 0.0")
	assert.Equal(t, 0.0, score.DividendBonus, "Missing dividend_bonus should default to 0.0")
}

func TestConvertToSecurityScore_HandlesNilSubScores(t *testing.T) {
	// Create a CalculatedSecurityScore with nil SubScores
	calculated := &domain.CalculatedSecurityScore{
		Symbol:     "TEST",
		TotalScore: 0.50,
		GroupScores: map[string]float64{
			"long_term": 0.50,
		},
		SubScores: nil,
	}

	score := convertToSecurityScore("TEST", calculated)

	// All raw values should default to 0.0 when SubScores is nil
	assert.Equal(t, 0.0, score.SharpeScore)
	assert.Equal(t, 0.0, score.DrawdownScore)
	assert.Equal(t, 0.0, score.FinancialStrengthScore)
	assert.Equal(t, 0.0, score.RSI)
	assert.Equal(t, 0.0, score.EMA200)
	assert.Equal(t, 0.0, score.Below52wHighPct)
	assert.Equal(t, 0.0, score.DividendBonus)
}

// Helper function to create float pointer
func floatPtr(f float64) *float64 {
	return &f
}
