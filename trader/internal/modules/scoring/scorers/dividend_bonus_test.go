package scorers

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestDividendScorer_CalculatesDividendBonus(t *testing.T) {
	scorer := NewDividendScorer()

	// High yield (6%+) should get HighDividendBonus (0.10)
	dividendYield := 0.065 // 6.5% yield
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.04

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	// Verify dividend_bonus is calculated and stored
	assert.Contains(t, result.Components, "dividend_bonus", "Components should contain dividend_bonus")

	// High yield should get 0.10 bonus
	bonus := result.Components["dividend_bonus"]
	assert.Equal(t, 0.10, bonus, "High yield (6%+) should get 0.10 bonus")
}

func TestDividendScorer_CalculatesDividendBonus_MidYield(t *testing.T) {
	scorer := NewDividendScorer()

	// Mid yield (3-6%) should get MidDividendBonus (0.07)
	dividendYield := 0.045 // 4.5% yield
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.04

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	bonus := result.Components["dividend_bonus"]
	assert.Equal(t, 0.07, bonus, "Mid yield (3-6%) should get 0.07 bonus")
}

func TestDividendScorer_CalculatesDividendBonus_LowYield(t *testing.T) {
	scorer := NewDividendScorer()

	// Low yield (<3%) should get LowDividendBonus (0.03)
	dividendYield := 0.015 // 1.5% yield
	payoutRatio := 0.50
	fiveYearAvgDivYield := 0.01

	result := scorer.Calculate(&dividendYield, &payoutRatio, &fiveYearAvgDivYield)

	bonus := result.Components["dividend_bonus"]
	assert.Equal(t, 0.03, bonus, "Low yield (<3%) should get 0.03 bonus")
}

func TestDividendScorer_CalculatesDividendBonus_NoDividend(t *testing.T) {
	scorer := NewDividendScorer()

	// No dividend should get 0.0 bonus
	dividendYield := 0.0
	var payoutRatio *float64
	var fiveYearAvgDivYield *float64

	result := scorer.Calculate(&dividendYield, payoutRatio, fiveYearAvgDivYield)

	bonus := result.Components["dividend_bonus"]
	assert.Equal(t, 0.0, bonus, "No dividend should get 0.0 bonus")
}

func TestDividendScorer_CalculatesDividendBonus_NilYield(t *testing.T) {
	scorer := NewDividendScorer()

	// Nil yield should get 0.0 bonus
	var dividendYield *float64
	var payoutRatio *float64
	var fiveYearAvgDivYield *float64

	result := scorer.Calculate(dividendYield, payoutRatio, fiveYearAvgDivYield)

	bonus := result.Components["dividend_bonus"]
	assert.Equal(t, 0.0, bonus, "Nil yield should get 0.0 bonus")
}
