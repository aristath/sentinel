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
