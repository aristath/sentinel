package rebalancing

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/settings"
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
		nil,                         // planningService
		nil,                         // positionRepo
		nil,                         // securityRepo
		nil,                         // allocRepo
		nil,                         // cashManager
		nil,                         // brokerClient
		nil,                         // configRepo
		nil,                         // recommendationRepo
		nil,                         // contextBuilder
		(*settings.Repository)(nil), // settingsRepo
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
		nil,                         // planningService
		nil,                         // positionRepo
		nil,                         // securityRepo
		nil,                         // allocRepo
		nil,                         // cashManager
		nil,                         // brokerClient
		nil,                         // configRepo
		nil,                         // recommendationRepo
		nil,                         // contextBuilder
		(*settings.Repository)(nil), // settingsRepo
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
		nil,                         // planningService
		nil,                         // positionRepo
		nil,                         // securityRepo
		nil,                         // allocRepo
		nil,                         // cashManager
		nil,                         // brokerClient
		nil,                         // configRepo
		nil,                         // recommendationRepo
		nil,                         // contextBuilder
		(*settings.Repository)(nil), // settingsRepo
		log,
	)

	// With €100 cash and min trade of €250, should return error due to nil dependencies
	_, err := service.CalculateRebalanceTrades(100.0)

	// Should return error because dependencies are nil
	if err == nil {
		t.Error("Expected error due to nil dependencies, got nil")
	}
}

// Note: Tests for convertCAGRScoreToCAGR and populateCAGRs have been moved to
// internal/services/opportunity_context_builder_test.go as part of the unified
// OpportunityContextBuilder refactoring.

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
			desc:      "Integer string should parse as float",
		},
		{
			name:      "negative float",
			input:     "-0.11",
			expected:  -0.11,
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
			input:     "1.5e-2",
			expected:  0.015,
			wantError: false,
			desc:      "Scientific notation should parse correctly",
		},
		{
			name:      "invalid string",
			input:     "not-a-number",
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
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := parseFloat(tt.input)
			if tt.wantError {
				if err == nil {
					t.Errorf("parseFloat(%q) expected error, got nil - %s", tt.input, tt.desc)
				}
			} else {
				if err != nil {
					t.Errorf("parseFloat(%q) unexpected error: %v - %s", tt.input, err, tt.desc)
				}
				tolerance := 0.0001
				if result < tt.expected-tolerance || result > tt.expected+tolerance {
					t.Errorf("parseFloat(%q) = %f, want %f - %s", tt.input, result, tt.expected, tt.desc)
				}
			}
		})
	}
}
