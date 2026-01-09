package rebalancing

import (
	"database/sql"
	"testing"

	"github.com/aristath/sentinel/pkg/logger"
)

func TestCalculateMinTradeAmount(t *testing.T) {
	tests := []struct {
		name        string
		fixed       float64
		percent     float64
		maxRatio    float64
		expectedMin float64
		description string
	}{
		{
			name:        "Freedom24 standard",
			fixed:       2.0,
			percent:     0.002,
			maxRatio:    0.01,
			expectedMin: 250.0, // 2.0 / (0.01 - 0.002) = 2.0 / 0.008 = 250
			description: "€2 fixed + 0.2% with 1% max ratio",
		},
		{
			name:        "Higher fixed cost",
			fixed:       5.0,
			percent:     0.002,
			maxRatio:    0.01,
			expectedMin: 625.0, // 5.0 / 0.008 = 625
			description: "€5 fixed cost",
		},
		{
			name:        "Variable cost exceeds max",
			fixed:       2.0,
			percent:     0.02,   // 2%
			maxRatio:    0.01,   // 1% max
			expectedMin: 1000.0, // Should return high minimum
			description: "Impossible ratio returns 1000",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := CalculateMinTradeAmount(tt.fixed, tt.percent, tt.maxRatio)
			if result != tt.expectedMin {
				t.Errorf("Expected %.2f, got %.2f - %s", tt.expectedMin, result, tt.description)
			}
		})
	}
}

func TestService_GetTriggerChecker(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	triggerChecker := NewTriggerChecker(log)
	negativeRebalancer := &NegativeBalanceRebalancer{log: log}
	// Pass nil for dependencies not used by this test (only tests getter method)
	service := NewService(
		triggerChecker,
		negativeRebalancer,
		nil,            // planningService
		nil,            // positionRepo
		nil,            // securityRepo
		nil,            // allocRepo
		nil,            // cashManager
		nil,            // tradernetClient
		nil,            // yahooClient
		nil,            // priceConversionService
		nil,            // configRepo
		nil,            // recommendationRepo
		(*sql.DB)(nil), // portfolioDB
		(*sql.DB)(nil), // configDB
		log,
	)

	checker := service.GetTriggerChecker()
	if checker == nil {
		t.Error("Expected trigger checker, got nil")
	}
}

func TestService_GetNegativeBalanceRebalancer(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	triggerChecker := NewTriggerChecker(log)
	negativeRebalancer := &NegativeBalanceRebalancer{log: log}
	// Pass nil for dependencies not used by this test (only tests getter method)
	service := NewService(
		triggerChecker,
		negativeRebalancer,
		nil,            // planningService
		nil,            // positionRepo
		nil,            // securityRepo
		nil,            // allocRepo
		nil,            // cashManager
		nil,            // tradernetClient
		nil,            // yahooClient
		nil,            // priceConversionService
		nil,            // configRepo
		nil,            // recommendationRepo
		(*sql.DB)(nil), // portfolioDB
		(*sql.DB)(nil), // configDB
		log,
	)

	rebalancer := service.GetNegativeBalanceRebalancer()
	if rebalancer == nil {
		t.Error("Expected negative balance rebalancer, got nil")
	}
}

func TestService_CalculateRebalanceTrades_InsufficientCash(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	triggerChecker := NewTriggerChecker(log)
	negativeRebalancer := &NegativeBalanceRebalancer{log: log}
	// Pass nil for dependencies not used by this test (only tests getter method)
	service := NewService(
		triggerChecker,
		negativeRebalancer,
		nil,            // planningService
		nil,            // positionRepo
		nil,            // securityRepo
		nil,            // allocRepo
		nil,            // cashManager
		nil,            // tradernetClient
		nil,            // yahooClient
		nil,            // priceConversionService
		nil,            // configRepo
		nil,            // recommendationRepo
		(*sql.DB)(nil), // portfolioDB
		(*sql.DB)(nil), // configDB
		log,
	)

	// With €100 cash and min trade of €250, should return empty
	trades, err := service.CalculateRebalanceTrades(100.0)

	// Should return empty slice when cash is insufficient
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}

	if len(trades) != 0 {
		t.Errorf("Expected empty trades, got %d", len(trades))
	}
}

// Note: Tests for NegativeBalanceRebalancer.CheckCurrencyMinimums
// require full dependencies (security repo, etc.) and are better suited
// for integration tests. Unit tests here focus on CalculateMinTradeAmount
// which is the core business logic.

func TestConvertCAGRScoreToCAGR(t *testing.T) {
	tests := []struct {
		name      string
		cagrScore float64
		expected  float64
		desc      string
		tolerance float64
	}{
		{
			name:      "zero score",
			cagrScore: 0.0,
			expected:  0.0,
			desc:      "Zero score should return 0% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "negative score",
			cagrScore: -0.5,
			expected:  0.0,
			desc:      "Negative score should return 0% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "floor score (0.15)",
			cagrScore: 0.15,
			expected:  0.0,
			desc:      "Floor score should return 0% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "below floor",
			cagrScore: 0.1,
			expected:  0.0,
			desc:      "Below floor should return 0% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "target score (0.8)",
			cagrScore: 0.8,
			expected:  0.11,
			desc:      "Target score should return 11% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "excellent score (1.0)",
			cagrScore: 1.0,
			expected:  0.20,
			desc:      "Excellent score should return 20% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "mid-range score (0.5)",
			cagrScore: 0.5,
			expected:  0.059, // (0.5 - 0.15) * 0.11 / (0.8 - 0.15) = 0.35 * 0.11 / 0.65 ≈ 0.059
			desc:      "Mid-range score should interpolate to ~5.9% CAGR",
			tolerance: 0.001,
		},
		{
			name:      "above target (0.9)",
			cagrScore: 0.9,
			expected:  0.155,
			desc:      "Above target should interpolate to ~15.5% CAGR",
			tolerance: 0.001,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := convertCAGRScoreToCAGR(tt.cagrScore)
			tolerance := tt.tolerance
			if tolerance == 0 {
				tolerance = 0.001
			}
			if result < tt.expected-tolerance || result > tt.expected+tolerance {
				t.Errorf("convertCAGRScoreToCAGR(%.2f) = %.3f, want %.3f (±%.3f) - %s",
					tt.cagrScore, result, tt.expected, tolerance, tt.desc)
			}
		})
	}
}

func TestParseFloat(t *testing.T) {
	tests := []struct {
		name      string
		input     string
		expected  float64
		wantError bool
		desc      string
	}{
		{
			name:      "valid float",
			input:     "3.14",
			expected:  3.14,
			wantError: false,
			desc:      "Valid float should parse correctly",
		},
		{
			name:      "integer string",
			input:     "42",
			expected:  42.0,
			wantError: false,
			desc:      "Integer string should parse to float",
		},
		{
			name:      "negative float",
			input:     "-10.5",
			expected:  -10.5,
			wantError: false,
			desc:      "Negative float should parse correctly",
		},
		{
			name:      "zero",
			input:     "0",
			expected:  0.0,
			wantError: false,
			desc:      "Zero should parse correctly",
		},
		{
			name:      "scientific notation",
			input:     "1.5e2",
			expected:  150.0,
			wantError: false,
			desc:      "Scientific notation should parse",
		},
		{
			name:      "invalid string",
			input:     "not a number",
			expected:  0.0,
			wantError: true,
			desc:      "Invalid string should return error",
		},
		{
			name:      "empty string",
			input:     "",
			expected:  0.0,
			wantError: true,
			desc:      "Empty string should return error",
		},
		{
			name:      "with whitespace",
			input:     "  3.14  ",
			expected:  3.14, // fmt.Sscanf can handle whitespace
			wantError: false,
			desc:      "Whitespace should be handled by fmt.Sscanf",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := parseFloat(tt.input)
			if (err != nil) != tt.wantError {
				t.Errorf("parseFloat(%q) error = %v, wantError %v - %s",
					tt.input, err, tt.wantError, tt.desc)
				return
			}
			if !tt.wantError {
				tolerance := 0.001
				if result < tt.expected-tolerance || result > tt.expected+tolerance {
					t.Errorf("parseFloat(%q) = %.3f, want %.3f (±%.3f) - %s",
						tt.input, result, tt.expected, tolerance, tt.desc)
				}
			}
		})
	}
}

func TestParseFloatRebalancing(t *testing.T) {
	// This is a duplicate of parseFloat, so we test it similarly
	tests := []struct {
		name      string
		input     string
		expected  float64
		wantError bool
		desc      string
	}{
		{
			name:      "valid float",
			input:     "100.50",
			expected:  100.50,
			wantError: false,
			desc:      "Valid float should parse correctly",
		},
		{
			name:      "integer string",
			input:     "250",
			expected:  250.0,
			wantError: false,
			desc:      "Integer string should parse to float",
		},
		{
			name:      "invalid string",
			input:     "invalid",
			expected:  0.0,
			wantError: true,
			desc:      "Invalid string should return error",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := parseFloatRebalancing(tt.input)
			if (err != nil) != tt.wantError {
				t.Errorf("parseFloatRebalancing(%q) error = %v, wantError %v - %s",
					tt.input, err, tt.wantError, tt.desc)
				return
			}
			if !tt.wantError {
				tolerance := 0.001
				if result < tt.expected-tolerance || result > tt.expected+tolerance {
					t.Errorf("parseFloatRebalancing(%q) = %.3f, want %.3f (±%.3f) - %s",
						tt.input, result, tt.expected, tolerance, tt.desc)
				}
			}
		})
	}
}
