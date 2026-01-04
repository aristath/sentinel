package portfolio

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestGetTurnoverStatus(t *testing.T) {
	log := zerolog.Nop()
	tracker := NewTurnoverTracker(nil, nil, log)

	tests := []struct {
		name            string
		turnover        *float64
		expectedStatus  string
		expectedAlert   *string
		shouldHaveAlert bool
	}{
		{
			name:            "nil turnover",
			turnover:        nil,
			expectedStatus:  "unknown",
			expectedAlert:   nil,
			shouldHaveAlert: false,
		},
		{
			name:            "normal turnover (20%)",
			turnover:        float64Ptr(0.20),
			expectedStatus:  "normal",
			expectedAlert:   nil,
			shouldHaveAlert: false,
		},
		{
			name:            "warning turnover (60%)",
			turnover:        float64Ptr(0.60),
			expectedStatus:  "warning",
			expectedAlert:   stringPtr("warning"),
			shouldHaveAlert: true,
		},
		{
			name:            "critical turnover (120%)",
			turnover:        float64Ptr(1.20),
			expectedStatus:  "critical",
			expectedAlert:   stringPtr("critical"),
			shouldHaveAlert: true,
		},
		{
			name:            "edge case: exactly 50%",
			turnover:        float64Ptr(0.50),
			expectedStatus:  "warning",
			expectedAlert:   stringPtr("warning"),
			shouldHaveAlert: true,
		},
		{
			name:            "edge case: exactly 100%",
			turnover:        float64Ptr(1.00),
			expectedStatus:  "critical",
			expectedAlert:   stringPtr("critical"),
			shouldHaveAlert: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tracker.GetTurnoverStatus(tt.turnover)

			assert.Equal(t, tt.expectedStatus, result.Status, "Status should match")

			if tt.shouldHaveAlert {
				assert.NotNil(t, result.Alert, "Alert should be present")
				if tt.expectedAlert != nil {
					assert.Equal(t, *tt.expectedAlert, *result.Alert, "Alert should match")
				}
			} else {
				assert.Nil(t, result.Alert, "Alert should be nil")
			}

			// Verify reason is not empty (except for nil case)
			if tt.turnover != nil {
				assert.NotEmpty(t, result.Reason, "Reason should not be empty")
			}

			// Verify turnover display format
			if tt.turnover != nil {
				assert.NotEqual(t, "N/A", result.TurnoverDisplay, "TurnoverDisplay should not be N/A for valid turnover")
			} else {
				assert.Equal(t, "N/A", result.TurnoverDisplay, "TurnoverDisplay should be N/A for nil turnover")
			}
		})
	}
}

func TestCalculateTurnoverFormula(t *testing.T) {
	// Test the formula logic manually
	// Formula: (total_buy_value + total_sell_value) / 2.0 / average_portfolio_value

	tests := []struct {
		name              string
		totalBuyValue     float64
		totalSellValue    float64
		avgPortfolioValue float64
		expectedTurnover  float64
	}{
		{
			name:              "50% turnover",
			totalBuyValue:     25000.0,
			totalSellValue:    25000.0,
			avgPortfolioValue: 50000.0,
			expectedTurnover:  0.50,
		},
		{
			name:              "100% turnover",
			totalBuyValue:     50000.0,
			totalSellValue:    50000.0,
			avgPortfolioValue: 50000.0,
			expectedTurnover:  1.00,
		},
		{
			name:              "20% turnover",
			totalBuyValue:     10000.0,
			totalSellValue:    10000.0,
			avgPortfolioValue: 50000.0,
			expectedTurnover:  0.20,
		},
		{
			name:              "asymmetric trades (more buys)",
			totalBuyValue:     30000.0,
			totalSellValue:    10000.0,
			avgPortfolioValue: 50000.0,
			expectedTurnover:  0.40, // (30000 + 10000) / 2 / 50000 = 0.40
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Apply formula
			turnover := (tt.totalBuyValue + tt.totalSellValue) / 2.0 / tt.avgPortfolioValue

			assert.InDelta(t, tt.expectedTurnover, turnover, 0.001, "Turnover should match formula")
		})
	}
}

// Helper functions

func float64Ptr(v float64) *float64 {
	return &v
}

func stringPtr(s string) *string {
	return &s
}
