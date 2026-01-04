package rebalancing

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// TriggerResult represents the result of a rebalancing trigger check
type TriggerResult struct {
	ShouldRebalance bool
	Reason          string
}

// TriggerChecker checks if portfolio conditions warrant event-driven rebalancing
// Faithful translation from Python: app/modules/rebalancing/domain/rebalancing_triggers.py
type TriggerChecker struct {
	log zerolog.Logger
}

// NewTriggerChecker creates a new trigger checker
func NewTriggerChecker(log zerolog.Logger) *TriggerChecker {
	return &TriggerChecker{
		log: log.With().Str("component", "rebalancing_triggers").Logger(),
	}
}

// CheckRebalanceTriggers checks if event-driven rebalancing should be triggered
//
// Triggers rebalancing when:
// 1. Position drift: Any position has drifted >= threshold from target allocation
// 2. Cash accumulation: Cash >= threshold_multiplier × min_trade_size
//
// Args:
//
//	positions: Current portfolio positions
//	targetAllocations: Target allocation weights per symbol (0.0 to 1.0)
//	totalPortfolioValue: Total portfolio value in EUR (positions + cash)
//	cashBalance: Available cash in EUR
//	enabled: Whether event-driven rebalancing is enabled (default true)
//
// Returns:
//
//	TriggerResult with should_rebalance flag and reason
func (tc *TriggerChecker) CheckRebalanceTriggers(
	positions []*portfolio.Position,
	targetAllocations map[string]float64,
	totalPortfolioValue float64,
	cashBalance float64,
	enabled bool,
	driftThreshold float64,
	cashThresholdMultiplier float64,
	minTradeSize float64,
) *TriggerResult {
	// Check if event-driven rebalancing is enabled
	if !enabled {
		return &TriggerResult{
			ShouldRebalance: false,
			Reason:          "event-driven rebalancing disabled",
		}
	}

	// Check position drift
	driftResult := tc.checkPositionDrift(
		positions,
		targetAllocations,
		totalPortfolioValue,
		driftThreshold,
	)

	if driftResult.ShouldRebalance {
		return driftResult
	}

	// Check cash accumulation
	cashResult := tc.checkCashAccumulation(
		cashBalance,
		cashThresholdMultiplier,
		minTradeSize,
	)

	if cashResult.ShouldRebalance {
		return cashResult
	}

	return &TriggerResult{
		ShouldRebalance: false,
		Reason:          "no triggers met",
	}
}

// checkPositionDrift checks if any position has drifted significantly from target allocation
func (tc *TriggerChecker) checkPositionDrift(
	positions []*portfolio.Position,
	targetAllocations map[string]float64,
	totalPortfolioValue float64,
	driftThreshold float64,
) *TriggerResult {
	if len(positions) == 0 || totalPortfolioValue <= 0 {
		return &TriggerResult{
			ShouldRebalance: false,
			Reason:          "no positions or zero portfolio value",
		}
	}

	if len(targetAllocations) == 0 {
		// No target allocations provided, skip drift check
		return &TriggerResult{
			ShouldRebalance: false,
			Reason:          "no target allocations provided",
		}
	}

	// Check each position for drift
	for _, position := range positions {
		if position.MarketValueEUR <= 0 {
			continue
		}

		// Calculate current allocation weight
		currentWeight := position.MarketValueEUR / totalPortfolioValue

		// Get target allocation (default to 0 if not specified)
		targetWeight := targetAllocations[position.Symbol]

		// Calculate absolute drift
		drift := abs(currentWeight - targetWeight)

		if drift >= driftThreshold {
			tc.log.Info().
				Str("symbol", position.Symbol).
				Float64("current_weight", currentWeight).
				Float64("target_weight", targetWeight).
				Float64("drift", drift).
				Float64("threshold", driftThreshold).
				Msg("Position drift detected")

			return &TriggerResult{
				ShouldRebalance: true,
				Reason: fmt.Sprintf(
					"position drift: %s drifted %.1f%% from target (threshold: %.1f%%)",
					position.Symbol,
					drift*100,
					driftThreshold*100,
				),
			}
		}
	}

	return &TriggerResult{
		ShouldRebalance: false,
		Reason:          "no position drift detected",
	}
}

// checkCashAccumulation checks if cash has accumulated above threshold
func (tc *TriggerChecker) checkCashAccumulation(
	cashBalance float64,
	thresholdMultiplier float64,
	minTradeSize float64,
) *TriggerResult {
	if cashBalance <= 0 {
		return &TriggerResult{
			ShouldRebalance: false,
			Reason:          "no cash available",
		}
	}

	// Calculate threshold
	cashThreshold := thresholdMultiplier * minTradeSize

	if cashBalance >= cashThreshold {
		tc.log.Info().
			Float64("cash_balance", cashBalance).
			Float64("cash_threshold", cashThreshold).
			Float64("threshold_multiplier", thresholdMultiplier).
			Msg("Cash accumulation detected")

		return &TriggerResult{
			ShouldRebalance: true,
			Reason: fmt.Sprintf(
				"cash accumulation: €%.2f >= €%.2f (threshold: %.1fx min_trade)",
				cashBalance,
				cashThreshold,
				thresholdMultiplier,
			),
		}
	}

	return &TriggerResult{
		ShouldRebalance: false,
		Reason:          "cash below threshold",
	}
}

// Helper function
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
