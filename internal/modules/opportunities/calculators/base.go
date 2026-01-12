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
	// Returns candidates that passed all filters and securities that were pre-filtered out.
	Calculate(ctx *domain.OpportunityContext, params map[string]interface{}) (domain.CalculatorResult, error)

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

// ExclusionCollector helps calculators track pre-filtered securities with reasons.
// Use this to collect exclusion reasons during calculation.
// Dismissed filters are still tracked but marked as dismissed in the output.
type ExclusionCollector struct {
	calculator       string
	exclusions       map[string]*domain.PreFilteredSecurity // keyed by ISIN
	dismissedFilters map[string]map[string][]string         // map[ISIN][calculator][]reasons
}

// NewExclusionCollector creates a new exclusion collector for a calculator.
// The dismissedFilters parameter is optional - pass nil if no dismissals are tracked.
func NewExclusionCollector(calculatorName string, dismissedFilters map[string]map[string][]string) *ExclusionCollector {
	return &ExclusionCollector{
		calculator:       calculatorName,
		exclusions:       make(map[string]*domain.PreFilteredSecurity),
		dismissedFilters: dismissedFilters,
	}
}

// isDismissed checks if a specific reason for this ISIN is dismissed by the user.
func (c *ExclusionCollector) isDismissed(isin, reason string) bool {
	if c.dismissedFilters == nil {
		return false
	}
	calcDismissals, ok := c.dismissedFilters[isin]
	if !ok {
		return false
	}
	reasons, ok := calcDismissals[c.calculator]
	if !ok {
		return false
	}
	for _, r := range reasons {
		if r == reason {
			return true
		}
	}
	return false
}

// Add records an exclusion reason for a security.
// Multiple calls for the same ISIN will accumulate reasons.
// The reason will be marked as dismissed if it exists in the dismissed filters.
func (c *ExclusionCollector) Add(isin, symbol, name, reason string) {
	if isin == "" {
		return
	}

	dismissed := c.isDismissed(isin, reason)
	newReason := domain.PreFilteredReason{
		Reason:    reason,
		Dismissed: dismissed,
	}

	if existing, ok := c.exclusions[isin]; ok {
		// Check if reason already present
		for _, r := range existing.Reasons {
			if r.Reason == reason {
				return
			}
		}
		existing.Reasons = append(existing.Reasons, newReason)
	} else {
		c.exclusions[isin] = &domain.PreFilteredSecurity{
			ISIN:       isin,
			Symbol:     symbol,
			Name:       name,
			Calculator: c.calculator,
			Reasons:    []domain.PreFilteredReason{newReason},
		}
	}
}

// Result returns all collected pre-filtered securities.
func (c *ExclusionCollector) Result() []domain.PreFilteredSecurity {
	result := make([]domain.PreFilteredSecurity, 0, len(c.exclusions))
	for _, pf := range c.exclusions {
		result = append(result, *pf)
	}
	return result
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

// DefaultCalculatorBoosts returns the default boost multipliers.
// These match the original hardcoded values for backward compatibility.
func DefaultCalculatorBoosts() CalculatorBoosts {
	return CalculatorBoosts{
		// Risk Profile boosts
		LowRiskBoost:    1.15,
		MediumRiskBoost: 1.05,
		HighRiskPenalty: 0.90,
		// Regime-Aware boosts
		BullGrowthBoost:       1.15,
		BearValueBoost:        1.15,
		SidewaysDividendBoost: 1.12,
		NeutralGrowthBoost:    1.08,
		NeutralValueBoost:     1.08,
		NeutralDividendBoost:  1.10,
		// Quality boosts
		StrongFundamentalsBoost: 1.12,
		ConsistentGrowerBoost:   1.10,
		StableBoost:             1.08,
		// Dividend boosts
		DividendTotalReturnBoost: 1.12,
		// Performance boosts (sell)
		UnsustainableGainsBoost: 1.25,
		StagnantBoost:           1.15,
		UnderperformingBoost:    1.20,
		// Performance boosts (buy)
		MeetsTargetReturnBoost: 1.10,
	}
}

// ApplyTagBasedPriorityBoosts applies priority multipliers based on security tags.
// Implements intelligent prioritization based on 14 tags across 5 categories:
// - Risk Profile (3 tags): low-risk, medium-risk, high-risk
// - Classification (3 tags): growth, value, dividend-focused (regime-aware if securityRepo provided)
// - Quality (3 tags): strong-fundamentals, consistent-grower, stable
// - Dividend (1 tag): dividend-total-return
// - Performance (4 tags): meets-target-return, unsustainable-gains, stagnant, underperforming
// Optional securityRepo parameter enables regime-aware classification boosts.
// Uses default boost multipliers. For temperament-adjusted boosts, use ApplyTagBasedPriorityBoostsWithConfig.
func ApplyTagBasedPriorityBoosts(
	priority float64,
	securityTags []string,
	calculatorType string,
	securityRepo ...SecurityRepository, // Optional: enables regime-aware logic
) float64 {
	return ApplyTagBasedPriorityBoostsWithConfig(priority, securityTags, calculatorType, nil, securityRepo...)
}

// ApplyTagBasedPriorityBoostsWithConfig applies priority multipliers based on security tags
// using temperament-adjusted boost multipliers from config.
func ApplyTagBasedPriorityBoostsWithConfig(
	priority float64,
	securityTags []string,
	calculatorType string,
	boosts *CalculatorBoosts, // nil uses defaults
	securityRepo ...SecurityRepository, // Optional: enables regime-aware logic
) float64 {
	if len(securityTags) == 0 {
		return priority
	}

	// Use provided boosts or defaults
	b := DefaultCalculatorBoosts()
	if boosts != nil {
		b = *boosts
	}

	multiplier := 1.0

	// Risk Profile Boosts (buy calculators only)
	if calculatorType == "opportunity_buys" || calculatorType == "averaging_down" || calculatorType == "rebalance_buys" {
		if contains(securityTags, "low-risk") {
			multiplier *= b.LowRiskBoost
		} else if contains(securityTags, "medium-risk") {
			multiplier *= b.MediumRiskBoost
		} else if contains(securityTags, "high-risk") {
			multiplier *= b.HighRiskPenalty
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
			multiplier *= b.BullGrowthBoost
		} else if regime == "bear" && contains(securityTags, "value") {
			multiplier *= b.BearValueBoost
		} else if regime == "sideways" && contains(securityTags, "dividend-focused") {
			multiplier *= b.SidewaysDividendBoost
		} else {
			// Neutral market or non-matching tags - apply standard boosts
			if contains(securityTags, "growth") {
				multiplier *= b.NeutralGrowthBoost
			}
			if contains(securityTags, "value") {
				multiplier *= b.NeutralValueBoost
			}
			if contains(securityTags, "dividend-focused") {
				multiplier *= b.NeutralDividendBoost
			}
		}
	} else {
		// No regime detection - apply standard boosts
		if contains(securityTags, "growth") {
			multiplier *= b.NeutralGrowthBoost
		}
		if contains(securityTags, "value") {
			multiplier *= b.NeutralValueBoost
		}
		if contains(securityTags, "dividend-focused") {
			multiplier *= b.NeutralDividendBoost
		}
	}

	// Quality Boosts (applicable to all buy calculators)
	if contains(securityTags, "strong-fundamentals") {
		multiplier *= b.StrongFundamentalsBoost
	}
	if contains(securityTags, "consistent-grower") {
		multiplier *= b.ConsistentGrowerBoost
	}
	if contains(securityTags, "stable") {
		multiplier *= b.StableBoost
	}

	// Dividend Total Return Boost
	if contains(securityTags, "dividend-total-return") {
		multiplier *= b.DividendTotalReturnBoost
	}

	// Performance Boosts (sell calculators primarily)
	if calculatorType == "profit_taking" || calculatorType == "rebalance_sells" {
		if contains(securityTags, "unsustainable-gains") {
			multiplier *= b.UnsustainableGainsBoost
		}
		if contains(securityTags, "stagnant") {
			multiplier *= b.StagnantBoost
		}
		if contains(securityTags, "underperforming") {
			multiplier *= b.UnderperformingBoost
		}
	} else {
		// Buy calculators - boost securities meeting target return
		if contains(securityTags, "meets-target-return") {
			multiplier *= b.MeetsTargetReturnBoost
		}
	}

	return priority * multiplier
}
