package calculators

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// OpportunityCalculator is the interface that all opportunity calculators must implement.
// Each calculator identifies trading opportunities of a specific type (profit taking,
// averaging down, rebalancing, etc.) based on current portfolio state.
type OpportunityCalculator interface {
	// Name returns the unique identifier for this calculator.
	Name() string

	// Calculate identifies trading opportunities based on the opportunity context.
	// Returns a list of action candidates with priorities and reasons.
	Calculate(ctx *domain.OpportunityContext, params map[string]interface{}) ([]domain.ActionCandidate, error)

	// Category returns the opportunity category this calculator produces.
	Category() domain.OpportunityCategory
}

// BaseCalculator provides common functionality for all calculators.
type BaseCalculator struct {
	log zerolog.Logger
}

// NewBaseCalculator creates a new base calculator with logging.
func NewBaseCalculator(log zerolog.Logger, name string) *BaseCalculator {
	return &BaseCalculator{
		log: log.With().Str("calculator", name).Logger(),
	}
}

// GetFloatParam retrieves a float parameter with a default value.
func GetFloatParam(params map[string]interface{}, key string, defaultValue float64) float64 {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if floatVal, ok := val.(float64); ok {
			return floatVal
		}
		if intVal, ok := val.(int); ok {
			return float64(intVal)
		}
	}
	return defaultValue
}

// GetIntParam retrieves an int parameter with a default value.
func GetIntParam(params map[string]interface{}, key string, defaultValue int) int {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if intVal, ok := val.(int); ok {
			return intVal
		}
		if floatVal, ok := val.(float64); ok {
			return int(floatVal)
		}
	}
	return defaultValue
}

// GetBoolParam retrieves a bool parameter with a default value.
func GetBoolParam(params map[string]interface{}, key string, defaultValue bool) bool {
	if params == nil {
		return defaultValue
	}
	if val, ok := params[key]; ok {
		if boolVal, ok := val.(bool); ok {
			return boolVal
		}
	}
	return defaultValue
}

// RoundToLotSize intelligently rounds quantity to lot size
// Strategy:
//  1. Try rounding down: floor(quantity/lotSize) * lotSize
//  2. If result is 0 or invalid, try rounding up: ceil(quantity/lotSize) * lotSize
//  3. Return the valid rounded quantity, or 0 if both fail
func RoundToLotSize(quantity int, lotSize int) int {
	if lotSize <= 0 {
		return quantity // No rounding needed
	}

	// Strategy 1: Round down
	roundedDown := (quantity / lotSize) * lotSize

	// If rounding down gives valid result (>= lotSize), use it
	if roundedDown >= lotSize {
		return roundedDown
	}

	// Strategy 2: Round up (only if rounding down failed)
	// Using ceiling: (quantity + lotSize - 1) / lotSize * lotSize
	roundedUp := ((quantity + lotSize - 1) / lotSize) * lotSize

	// Use rounded up if it's valid, otherwise return 0
	if roundedUp >= lotSize {
		return roundedUp
	}

	return 0 // Cannot make valid
}

// contains checks if a string slice contains a specific string.
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// ApplyQuantumWarningPenalty applies calculator-specific quantum warning penalties.
// Quantum bubble warnings indicate elevated risk but not absolute exclusion.
// Different calculator types apply different penalty levels based on risk tolerance.
func ApplyQuantumWarningPenalty(
	priority float64,
	securityTags []string,
	calculatorType string,
) float64 {
	hasQuantumWarning := contains(securityTags, "quantum-bubble-warning")
	if !hasQuantumWarning {
		return priority
	}

	switch calculatorType {
	case "averaging_down":
		return priority * 0.9 // 10% reduction (already in position, less risky)
	case "opportunity_buys", "rebalance_buys", "weight_based":
		return priority * 0.7 // 30% reduction (new positions, more conservative)
	case "profit_taking", "rebalance_sells":
		return priority // No penalty (selling positions, quantum warning doesn't apply)
	default:
		return priority * 0.7 // Default: 30% reduction
	}
}

// DetectCurrentRegime analyzes security tags to determine current market regime.
// Returns one of: "bull", "bear", "sideways", "volatile", or "neutral".
func DetectCurrentRegime(securityRepo SecurityRepository) string {
	if securityRepo == nil {
		return "neutral"
	}

	// Count securities with each regime tag
	bearSafe, _ := securityRepo.GetByTags([]string{"regime-bear-safe"})
	bullGrowth, _ := securityRepo.GetByTags([]string{"regime-bull-growth"})
	sidewaysValue, _ := securityRepo.GetByTags([]string{"regime-sideways-value"})
	volatile, _ := securityRepo.GetByTags([]string{"regime-volatile"})

	bearCount := len(bearSafe)
	bullCount := len(bullGrowth)
	sidewaysCount := len(sidewaysValue)
	volatileCount := len(volatile)

	// Determine regime based on tag distribution
	// Threshold: If 10+ securities have a regime tag, it indicates that regime
	if volatileCount > 10 {
		return "volatile"
	}
	if bullCount > bearCount && bullCount > sidewaysCount {
		return "bull"
	}
	if bearCount > bullCount && bearCount > sidewaysCount {
		return "bear"
	}
	if sidewaysCount > bullCount && sidewaysCount > bearCount {
		return "sideways"
	}

	return "neutral"
}

// ApplyTagBasedPriorityBoosts applies priority multipliers based on security tags.
// Implements intelligent prioritization based on 14 tags across 5 categories:
// - Risk Profile (3 tags): low-risk, medium-risk, high-risk
// - Classification (3 tags): growth, value, dividend-focused (regime-aware if securityRepo provided)
// - Quality (3 tags): strong-fundamentals, consistent-grower, stable
// - Dividend (1 tag): dividend-total-return
// - Performance (4 tags): meets-target-return, unsustainable-gains, stagnant, underperforming
// Optional securityRepo parameter enables regime-aware classification boosts.
func ApplyTagBasedPriorityBoosts(
	priority float64,
	securityTags []string,
	calculatorType string,
	securityRepo ...SecurityRepository, // Optional: enables regime-aware logic
) float64 {
	if len(securityTags) == 0 {
		return priority
	}

	multiplier := 1.0

	// Risk Profile Boosts (buy calculators only)
	if calculatorType == "opportunity_buys" || calculatorType == "averaging_down" || calculatorType == "rebalance_buys" {
		if contains(securityTags, "low-risk") {
			multiplier *= 1.15 // 15% boost for low risk
		} else if contains(securityTags, "medium-risk") {
			multiplier *= 1.05 // 5% boost for medium risk
		} else if contains(securityTags, "high-risk") {
			multiplier *= 0.90 // 10% penalty for high risk
		}
	}

	// Classification Boosts (regime-aware when securityRepo provided)
	var repo SecurityRepository
	if len(securityRepo) > 0 {
		repo = securityRepo[0]
	}

	if repo != nil {
		// Regime-aware classification boosts
		regime := DetectCurrentRegime(repo)
		if regime == "bull" && contains(securityTags, "growth") {
			multiplier *= 1.15 // 15% boost for growth in bull market
		} else if regime == "bear" && contains(securityTags, "value") {
			multiplier *= 1.15 // 15% boost for value in bear market
		} else if regime == "sideways" && contains(securityTags, "dividend-focused") {
			multiplier *= 1.12 // 12% boost for dividends in sideways market
		} else {
			// Neutral market or non-matching tags - apply standard boosts
			if contains(securityTags, "growth") {
				multiplier *= 1.08
			}
			if contains(securityTags, "value") {
				multiplier *= 1.08
			}
			if contains(securityTags, "dividend-focused") {
				multiplier *= 1.10
			}
		}
	} else {
		// No regime detection - apply standard boosts
		if contains(securityTags, "growth") {
			multiplier *= 1.08 // 8% boost for growth
		}
		if contains(securityTags, "value") {
			multiplier *= 1.08 // 8% boost for value
		}
		if contains(securityTags, "dividend-focused") {
			multiplier *= 1.10 // 10% boost for dividend focus
		}
	}

	// Quality Boosts (applicable to all buy calculators)
	if contains(securityTags, "strong-fundamentals") {
		multiplier *= 1.12 // 12% boost for strong fundamentals
	}
	if contains(securityTags, "consistent-grower") {
		multiplier *= 1.10 // 10% boost for consistency
	}
	if contains(securityTags, "stable") {
		multiplier *= 1.08 // 8% boost for stability
	}

	// Dividend Total Return Boost
	if contains(securityTags, "dividend-total-return") {
		multiplier *= 1.12 // 12% boost for high total return from dividends
	}

	// Performance Boosts (sell calculators primarily)
	if calculatorType == "profit_taking" || calculatorType == "rebalance_sells" {
		if contains(securityTags, "unsustainable-gains") {
			multiplier *= 1.25 // 25% boost to sell unsustainable gains
		}
		if contains(securityTags, "stagnant") {
			multiplier *= 1.15 // 15% boost to sell stagnant positions
		}
		if contains(securityTags, "underperforming") {
			multiplier *= 1.20 // 20% boost to sell underperformers
		}
	} else {
		// Buy calculators - boost securities meeting target return
		if contains(securityTags, "meets-target-return") {
			multiplier *= 1.10 // 10% boost for meeting target
		}
	}

	return priority * multiplier
}
