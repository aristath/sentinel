package rebalancing

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/pkg/logger"
)

func TestTriggerChecker_Disabled(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	result := tc.CheckRebalanceTriggers(
		nil,
		nil,
		0,
		0,
		false, // disabled
		0.05,
		2.0,
		100.0,
	)

	if result.ShouldRebalance {
		t.Error("Expected no rebalancing when disabled")
	}
	if result.Reason != "event-driven rebalancing disabled" {
		t.Errorf("Expected disabled reason, got: %s", result.Reason)
	}
}

func TestTriggerChecker_NoPositions(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	result := tc.CheckRebalanceTriggers(
		[]*portfolio.Position{},
		map[string]float64{"AAPL": 0.5},
		10000,
		100,
		true,
		0.05,
		2.0,
		100.0,
	)

	if result.ShouldRebalance {
		t.Error("Expected no rebalancing with no positions")
	}
}

func TestTriggerChecker_PositionDrift(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	positions := []*portfolio.Position{
		{
			Symbol:         "AAPL",
			MarketValueEUR: 6000.0, // 60% of portfolio
		},
	}

	targetAllocations := map[string]float64{
		"AAPL": 0.50, // Target 50%, actual 60% = 10% drift
	}

	result := tc.CheckRebalanceTriggers(
		positions,
		targetAllocations,
		10000, // Total portfolio value
		100,
		true,
		0.05, // 5% drift threshold - 10% drift exceeds this
		2.0,
		100.0,
	)

	if !result.ShouldRebalance {
		t.Error("Expected rebalancing due to position drift")
	}
	if result.Reason == "" {
		t.Error("Expected reason for rebalancing")
	}
	t.Logf("Drift reason: %s", result.Reason)
}

func TestTriggerChecker_NoDrift(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	positions := []*portfolio.Position{
		{
			Symbol:         "AAPL",
			MarketValueEUR: 5100.0, // 51% of portfolio
		},
	}

	targetAllocations := map[string]float64{
		"AAPL": 0.50, // Target 50%, actual 51% = 1% drift
	}

	result := tc.CheckRebalanceTriggers(
		positions,
		targetAllocations,
		10000,
		100,
		true,
		0.05, // 5% drift threshold - 1% drift is below this
		2.0,
		100.0,
	)

	if result.ShouldRebalance {
		t.Errorf("Expected no rebalancing, but got: %s", result.Reason)
	}
}

func TestTriggerChecker_CashAccumulation(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	result := tc.CheckRebalanceTriggers(
		[]*portfolio.Position{},
		map[string]float64{},
		10000,
		250, // Cash balance
		true,
		0.05,
		2.0,   // Threshold multiplier
		100.0, // Min trade size -> threshold = 2.0 * 100 = 200
	)

	if !result.ShouldRebalance {
		t.Error("Expected rebalancing due to cash accumulation (250 >= 200)")
	}
	if result.Reason == "" {
		t.Error("Expected reason for rebalancing")
	}
	t.Logf("Cash reason: %s", result.Reason)
}

func TestTriggerChecker_CashBelowThreshold(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	result := tc.CheckRebalanceTriggers(
		[]*portfolio.Position{},
		map[string]float64{},
		10000,
		150, // Cash balance
		true,
		0.05,
		2.0,   // Threshold multiplier
		100.0, // Min trade size -> threshold = 2.0 * 100 = 200
	)

	if result.ShouldRebalance {
		t.Errorf("Expected no rebalancing, but got: %s", result.Reason)
	}
}

func TestTriggerChecker_NoTargetAllocations(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	positions := []*portfolio.Position{
		{
			Symbol:         "AAPL",
			MarketValueEUR: 5000.0,
		},
	}

	result := tc.CheckRebalanceTriggers(
		positions,
		map[string]float64{}, // No target allocations
		10000,
		100,
		true,
		0.05,
		2.0,
		100.0,
	)

	if result.ShouldRebalance {
		t.Errorf("Expected no rebalancing without target allocations, but got: %s", result.Reason)
	}
}

func TestAbs(t *testing.T) {
	tests := []struct {
		name     string
		input    float64
		expected float64
	}{
		{"positive", 5.0, 5.0},
		{"negative", -5.0, 5.0},
		{"zero", 0.0, 0.0},
		{"positive decimal", 3.14, 3.14},
		{"negative decimal", -3.14, 3.14},
		{"large positive", 1000.0, 1000.0},
		{"large negative", -1000.0, 1000.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := abs(tt.input)
			if result != tt.expected {
				t.Errorf("abs(%v) = %v, want %v", tt.input, result, tt.expected)
			}
		})
	}
}

func TestTriggerChecker_CheckPositionDrift_EdgeCases(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	tests := []struct {
		name            string
		positions       []*portfolio.Position
		targetAllocs    map[string]float64
		totalValue      float64
		driftThreshold  float64
		shouldRebalance bool
		description     string
	}{
		{
			name:            "zero portfolio value",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 100.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.5},
			totalValue:      0.0,
			driftThreshold:  0.05,
			shouldRebalance: false,
			description:     "Zero portfolio value should not trigger",
		},
		{
			name:            "negative portfolio value",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 100.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.5},
			totalValue:      -1000.0,
			driftThreshold:  0.05,
			shouldRebalance: false,
			description:     "Negative portfolio value should not trigger",
		},
		{
			name:            "position with zero market value",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 0.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.5},
			totalValue:      10000.0,
			driftThreshold:  0.05,
			shouldRebalance: false,
			description:     "Position with zero value should be skipped",
		},
		{
			name:            "exact threshold drift",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 5500.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.50},
			totalValue:      10000.0,
			driftThreshold:  0.05,
			shouldRebalance: true,
			description:     "Exact threshold drift should trigger (5% = 5%)",
		},
		{
			name:            "just below threshold",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 5499.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.50},
			totalValue:      10000.0,
			driftThreshold:  0.05,
			shouldRebalance: false,
			description:     "Just below threshold should not trigger",
		},
		{
			name:            "negative drift",
			positions:       []*portfolio.Position{{Symbol: "AAPL", MarketValueEUR: 4400.0}},
			targetAllocs:    map[string]float64{"AAPL": 0.50},
			totalValue:      10000.0,
			driftThreshold:  0.05,
			shouldRebalance: true,
			description:     "Negative drift (below target) should trigger (44% vs 50% = 6% drift)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tc.checkPositionDrift(tt.positions, tt.targetAllocs, tt.totalValue, tt.driftThreshold)
			if result.ShouldRebalance != tt.shouldRebalance {
				t.Errorf("%s: Expected shouldRebalance=%v, got %v. Reason: %s",
					tt.description, tt.shouldRebalance, result.ShouldRebalance, result.Reason)
			}
		})
	}
}

func TestTriggerChecker_CheckCashAccumulation_EdgeCases(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})
	tc := NewTriggerChecker(log)

	tests := []struct {
		name            string
		cashBalance     float64
		thresholdMult   float64
		minTradeSize    float64
		shouldRebalance bool
		description     string
	}{
		{
			name:            "zero cash",
			cashBalance:     0.0,
			thresholdMult:   2.0,
			minTradeSize:    100.0,
			shouldRebalance: false,
			description:     "Zero cash should not trigger",
		},
		{
			name:            "negative cash",
			cashBalance:     -100.0,
			thresholdMult:   2.0,
			minTradeSize:    100.0,
			shouldRebalance: false,
			description:     "Negative cash should not trigger",
		},
		{
			name:            "exact threshold",
			cashBalance:     200.0,
			thresholdMult:   2.0,
			minTradeSize:    100.0,
			shouldRebalance: true,
			description:     "Exact threshold should trigger (200 = 2.0 * 100)",
		},
		{
			name:            "just above threshold",
			cashBalance:     200.01,
			thresholdMult:   2.0,
			minTradeSize:    100.0,
			shouldRebalance: true,
			description:     "Just above threshold should trigger",
		},
		{
			name:            "just below threshold",
			cashBalance:     199.99,
			thresholdMult:   2.0,
			minTradeSize:    100.0,
			shouldRebalance: false,
			description:     "Just below threshold should not trigger",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tc.checkCashAccumulation(tt.cashBalance, tt.thresholdMult, tt.minTradeSize)
			if result.ShouldRebalance != tt.shouldRebalance {
				t.Errorf("%s: Expected shouldRebalance=%v, got %v. Reason: %s",
					tt.description, tt.shouldRebalance, result.ShouldRebalance, result.Reason)
			}
		})
	}
}
