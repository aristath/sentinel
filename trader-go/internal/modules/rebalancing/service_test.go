package rebalancing

import (
	"testing"

	"github.com/aristath/arduino-trader/pkg/logger"
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
	service := NewService(log)

	checker := service.GetTriggerChecker()
	if checker == nil {
		t.Error("Expected trigger checker, got nil")
	}
}

func TestService_GetNegativeBalanceRebalancer(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	service := NewService(log)

	rebalancer := service.GetNegativeBalanceRebalancer()
	if rebalancer == nil {
		t.Error("Expected negative balance rebalancer, got nil")
	}
}

func TestService_CalculateRebalanceTrades_InsufficientCash(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	service := NewService(log)

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

func TestNegativeBalanceRebalancer_CheckCurrencyMinimums(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	rebalancer := NewNegativeBalanceRebalancer(log)

	balances := map[string]float64{
		"EUR": 10.0, // Above minimum (€5)
		"USD": 3.0,  // Below minimum (needs €2)
		"GBP": -2.0, // Negative (needs €7)
	}

	shortfalls := rebalancer.CheckCurrencyMinimums(balances)

	if len(shortfalls) != 2 {
		t.Errorf("Expected 2 shortfalls, got %d", len(shortfalls))
	}

	if shortfalls["USD"] != 2.0 {
		t.Errorf("Expected USD shortfall of 2.0, got %.2f", shortfalls["USD"])
	}

	if shortfalls["GBP"] != 7.0 {
		t.Errorf("Expected GBP shortfall of 7.0, got %.2f", shortfalls["GBP"])
	}

	if _, exists := shortfalls["EUR"]; exists {
		t.Error("EUR should not have a shortfall")
	}
}

func TestNegativeBalanceRebalancer_CheckCurrencyMinimums_AllOK(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	rebalancer := NewNegativeBalanceRebalancer(log)

	balances := map[string]float64{
		"EUR": 100.0,
		"USD": 50.0,
		"GBP": 25.0,
	}

	shortfalls := rebalancer.CheckCurrencyMinimums(balances)

	if len(shortfalls) != 0 {
		t.Errorf("Expected no shortfalls, got %d", len(shortfalls))
	}
}
