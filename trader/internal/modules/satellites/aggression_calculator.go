package satellites

import (
	"fmt"
	"strings"

	"github.com/rs/zerolog"
)

// AggressionResult represents the result of aggression calculation
// Faithful translation from Python: app/modules/satellites/domain/aggression_calculator.py
type AggressionResult struct {
	Aggression           float64 `json:"aggression"`            // Final aggression level (0.0-1.0)
	AllocationAggression float64 `json:"allocation_aggression"` // Aggression based on allocation
	DrawdownAggression   float64 `json:"drawdown_aggression"`   // Aggression based on drawdown
	LimitingFactor       string  `json:"limiting_factor"`       // 'allocation', 'drawdown', or 'equal'
	CurrentValue         float64 `json:"current_value"`         // Current bucket value
	TargetValue          float64 `json:"target_value"`          // Target bucket value
	PctOfTarget          float64 `json:"pct_of_target"`         // Current as % of target (0.0-1.0+)
	Drawdown             float64 `json:"drawdown"`              // Current drawdown (0.0-1.0)
	InHibernation        bool    `json:"in_hibernation"`        // True if aggression is 0.0
}

// AggressionCalculator calculates dynamic position sizing based on allocation and drawdown
//
// The aggression level (0.0-1.0) scales position sizes:
// - 1.0 = Full aggression (100% of strategy's normal size)
// - 0.8 = Reduced (80%)
// - 0.6 = Conservative (60%)
// - 0.4 = Very conservative (40%)
// - 0.0 = Hibernation (no new trades)
//
// The most conservative factor (min of allocation-based and drawdown-based) wins.
type AggressionCalculator struct {
	log zerolog.Logger
}

// NewAggressionCalculator creates a new aggression calculator
func NewAggressionCalculator(log zerolog.Logger) *AggressionCalculator {
	return &AggressionCalculator{
		log: log.With().Str("component", "aggression_calculator").Logger(),
	}
}

// CalculateAggression calculates aggression level for a satellite bucket
//
// Args:
//
//	currentValue: Current total value of bucket (positions + cash)
//	targetValue: Target allocation value for this bucket
//	highWaterMark: Highest value achieved (for drawdown calculation), use nil if not tracking
//
// Returns:
//
//	AggressionResult with final aggression and breakdown
func (c *AggressionCalculator) CalculateAggression(
	currentValue float64,
	targetValue float64,
	highWaterMark *float64,
) AggressionResult {
	// Percentage-based aggression (allocation status)
	var pctOfTarget float64
	if targetValue < 0.01 { // Less than 1 cent
		pctOfTarget = 0.0
	} else {
		pctOfTarget = currentValue / targetValue
	}

	// Allocation aggression thresholds
	var aggPct float64
	if pctOfTarget >= 1.0 {
		aggPct = 1.0 // At or above target → full aggression
	} else if pctOfTarget >= 0.8 {
		aggPct = 0.8 // 80-100% of target → reduced aggression
	} else if pctOfTarget >= 0.6 {
		aggPct = 0.6 // 60-80% of target → conservative
	} else if pctOfTarget >= 0.4 {
		aggPct = 0.4 // 40-60% of target → very conservative
	} else {
		aggPct = 0.0 // Below 40% → hibernation
	}

	// Drawdown-based aggression (risk management)
	var drawdown float64
	if highWaterMark != nil && *highWaterMark > 0 && currentValue < *highWaterMark {
		drawdown = (*highWaterMark - currentValue) / *highWaterMark
	} else {
		drawdown = 0.0 // No drawdown (at or above high water mark)
	}

	var aggDD float64
	if drawdown >= 0.35 {
		aggDD = 0.0 // Severe drawdown (≥35%) → hibernation
	} else if drawdown >= 0.25 {
		aggDD = 0.3 // Major drawdown (25-35%) → minimal trading
	} else if drawdown >= 0.15 {
		aggDD = 0.7 // Moderate drawdown (15-25%) → reduced trading
	} else {
		aggDD = 1.0 // Minimal drawdown (<15%) → full aggression
	}

	// Most conservative wins
	finalAggression := min(aggPct, aggDD)

	// Determine limiting factor
	var limitingFactor string
	if aggPct < aggDD {
		limitingFactor = "allocation"
	} else if aggDD < aggPct {
		limitingFactor = "drawdown"
	} else {
		limitingFactor = "equal" // Both factors agree
	}

	return AggressionResult{
		Aggression:           finalAggression,
		AllocationAggression: aggPct,
		DrawdownAggression:   aggDD,
		LimitingFactor:       limitingFactor,
		CurrentValue:         currentValue,
		TargetValue:          targetValue,
		PctOfTarget:          pctOfTarget,
		Drawdown:             drawdown,
		InHibernation:        finalAggression == 0.0,
	}
}

// ShouldHibernate checks if satellite should hibernate (aggression = 0.0)
func (c *AggressionCalculator) ShouldHibernate(result AggressionResult) bool {
	return result.InHibernation
}

// ScalePositionSize scales a position size by aggression level
func (c *AggressionCalculator) ScalePositionSize(baseSize float64, aggression float64) float64 {
	return baseSize * aggression
}

// GetAggressionDescription returns human-readable description of aggression status
func (c *AggressionCalculator) GetAggressionDescription(result AggressionResult) string {
	if result.InHibernation {
		if result.LimitingFactor == "allocation" {
			return fmt.Sprintf(
				"HIBERNATION: Bucket at %.1f%% of target (below 40%% threshold)",
				result.PctOfTarget*100,
			)
		} else if result.LimitingFactor == "drawdown" {
			return fmt.Sprintf(
				"HIBERNATION: Drawdown at %.1f%% (above 35%% threshold)",
				result.Drawdown*100,
			)
		} else {
			return "HIBERNATION: Both allocation and drawdown in critical zone"
		}
	}

	// Build status parts
	var status []string

	// Allocation status
	if result.PctOfTarget >= 1.0 {
		status = append(status, fmt.Sprintf("Fully funded (%.1f%% of target)", result.PctOfTarget*100))
	} else {
		status = append(status, fmt.Sprintf("Funding: %.1f%% of target", result.PctOfTarget*100))
	}

	// Drawdown status
	if result.Drawdown > 0 {
		status = append(status, fmt.Sprintf("Drawdown: %.1f%%", result.Drawdown*100))
	} else {
		status = append(status, "No drawdown (at/above high water mark)")
	}

	// Aggression level
	status = append(status, fmt.Sprintf("Aggression: %.0f%%", result.Aggression*100))

	// Limiting factor
	if result.LimitingFactor != "equal" {
		status = append(status, fmt.Sprintf("(limited by %s)", result.LimitingFactor))
	}

	return strings.Join(status, " | ")
}

// Helper function
func min(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}
