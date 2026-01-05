package universe

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestScoresColumns_MatchesSchema(t *testing.T) {
	// Expected column order based on migration 004 + 029
	// After migration 029, the schema is:
	// symbol, total_score, quality_score, opportunity_score, analyst_score,
	// allocation_fit_score, volatility, cagr_score, consistency_score,
	// history_years, technical_score, fundamental_score,
	// sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
	// rsi, ema_200, below_52w_high_pct, last_updated

	expectedColumns := []string{
		"symbol",
		"total_score",
		"quality_score",
		"opportunity_score",
		"analyst_score",
		"allocation_fit_score",
		"volatility",
		"cagr_score",
		"consistency_score",
		"history_years",
		"technical_score",
		"fundamental_score",
		"sharpe_score",
		"drawdown_score",
		"dividend_bonus",
		"financial_strength_score",
		"rsi",
		"ema_200",
		"below_52w_high_pct",
		"last_updated",
	}

	// Parse scoresColumns constant
	// scoresColumns is a string like "symbol, total_score, ..."
	// We'll verify it contains all expected columns in order
	actualColumns := parseColumns(scoresColumns)

	assert.Equal(t, len(expectedColumns), len(actualColumns), "Column count should match")

	for i, expected := range expectedColumns {
		if i < len(actualColumns) {
			assert.Equal(t, expected, actualColumns[i], "Column at position %d should be %s", i, expected)
		}
	}
}

// parseColumns parses a column list string into a slice
func parseColumns(columnList string) []string {
	// Simple parsing - split by comma and trim spaces
	// This is just for testing, not production code
	var columns []string
	// Remove newlines and split by comma
	cleaned := columnList
	cleaned = cleaned + ", " // Add trailing comma for easier parsing
	var current string
	for _, char := range cleaned {
		if char == ',' {
			if current != "" {
				columns = append(columns, trimSpace(current))
				current = ""
			}
		} else if char != '\n' {
			current += string(char)
		}
	}
	return columns
}

func trimSpace(s string) string {
	start := 0
	end := len(s)
	for start < end && (s[start] == ' ' || s[start] == '\t') {
		start++
	}
	for end > start && (s[end-1] == ' ' || s[end-1] == '\t') {
		end--
	}
	return s[start:end]
}
