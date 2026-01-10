// Package domain provides planning domain models.
package domain

// PlannerConfiguration represents the complete configuration for a planner instance.
// Simplified to match database schema - flattened structure with individual boolean fields
// instead of nested ModuleConfig structures.
type PlannerConfiguration struct {
	// Planner identification
	Name                  string `json:"name"`
	Description           string `json:"description"`
	EnableBatchGeneration bool   `json:"enable_batch_generation"`

	// Global planner settings
	MaxDepth                    int     `json:"max_depth"`
	MaxOpportunitiesPerCategory int     `json:"max_opportunities_per_category"`
	EnableDiverseSelection      bool    `json:"enable_diverse_selection"`
	DiversityWeight             float64 `json:"diversity_weight"`
	MaxSequenceAttempts         int     `json:"max_sequence_attempts"` // Maximum number of sequences to try until one passes constraints

	// Transaction costs
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`

	// Trade permissions
	AllowSell bool `json:"allow_sell"`
	AllowBuy  bool `json:"allow_buy"`

	// Risk management settings
	MinHoldDays       int     `json:"min_hold_days"`       // Minimum days a position must be held before selling
	SellCooldownDays  int     `json:"sell_cooldown_days"`  // Days to wait after selling before buying again
	MaxLossThreshold  float64 `json:"max_loss_threshold"`  // Maximum loss threshold before forced selling consideration
	MaxSellPercentage float64 `json:"max_sell_percentage"` // Maximum percentage of position allowed to sell per transaction

	// Portfolio optimizer settings
	OptimizerBlend        float64 `json:"optimizer_blend"`        // 0.0 = pure Mean-Variance, 1.0 = pure HRP
	OptimizerTargetReturn float64 `json:"optimizer_target_return"` // Target annual return for MV component
	MinCashReserve        float64 `json:"min_cash_reserve"`        // Minimum cash to keep (never fully deploy)

	// Opportunity Calculator enabled flags
	EnableProfitTakingCalc    bool `json:"enable_profit_taking_calc"`
	EnableAveragingDownCalc   bool `json:"enable_averaging_down_calc"`
	EnableOpportunityBuysCalc bool `json:"enable_opportunity_buys_calc"`
	EnableRebalanceSellsCalc  bool `json:"enable_rebalance_sells_calc"`
	EnableRebalanceBuysCalc   bool `json:"enable_rebalance_buys_calc"`
	EnableWeightBasedCalc     bool `json:"enable_weight_based_calc"`

	// Pattern Generator enabled flags
	EnableDirectBuyPattern        bool `json:"enable_direct_buy_pattern"`
	EnableProfitTakingPattern     bool `json:"enable_profit_taking_pattern"`
	EnableRebalancePattern        bool `json:"enable_rebalance_pattern"`
	EnableAveragingDownPattern    bool `json:"enable_averaging_down_pattern"`
	EnableSingleBestPattern       bool `json:"enable_single_best_pattern"`
	EnableMultiSellPattern        bool `json:"enable_multi_sell_pattern"`
	EnableMixedStrategyPattern    bool `json:"enable_mixed_strategy_pattern"`
	EnableOpportunityFirstPattern bool `json:"enable_opportunity_first_pattern"`
	EnableDeepRebalancePattern    bool `json:"enable_deep_rebalance_pattern"`
	EnableCashGenerationPattern   bool `json:"enable_cash_generation_pattern"`
	EnableCostOptimizedPattern    bool `json:"enable_cost_optimized_pattern"`
	EnableAdaptivePattern         bool `json:"enable_adaptive_pattern"`
	EnableMarketRegimePattern     bool `json:"enable_market_regime_pattern"`

	// Sequence Generator enabled flags
	EnableCombinatorialGenerator         bool `json:"enable_combinatorial_generator"`
	EnableEnhancedCombinatorialGenerator bool `json:"enable_enhanced_combinatorial_generator"`
	EnableConstraintRelaxationGenerator  bool `json:"enable_constraint_relaxation_generator"`

	// Filter enabled flags
	EnableCorrelationAwareFilter bool `json:"enable_correlation_aware_filter"`
	EnableDiversityFilter        bool `json:"enable_diversity_filter"`
	EnableEligibilityFilter      bool `json:"enable_eligibility_filter"`
	EnableRecentlyTradedFilter   bool `json:"enable_recently_traded_filter"`

	// Tag filtering
	EnableTagFiltering bool `json:"enable_tag_filtering"` // Enable/disable tag-based pre-filtering
}

// NewDefaultConfiguration creates a PlannerConfiguration with default settings.
func NewDefaultConfiguration() *PlannerConfiguration {
	return &PlannerConfiguration{
		Name:                        "default",
		Description:                 "",
		EnableBatchGeneration:       true,
		MaxDepth:                    5,
		MaxOpportunitiesPerCategory: 5,
		MaxSequenceAttempts:         20, // Try top 20 sequences until one passes constraints
		EnableDiverseSelection:      true,
		DiversityWeight:             0.3,
		TransactionCostFixed:        5.0,
		TransactionCostPercent:      0.001,
		AllowSell:                   true,
		AllowBuy:                    true,
		MinHoldDays:                 90,
		SellCooldownDays:            180,
		MaxLossThreshold:            -0.20,
		MaxSellPercentage:           0.20,
		OptimizerBlend:              0.5,   // 50% MV, 50% HRP
		OptimizerTargetReturn:       0.11,  // 11% target annual return
		MinCashReserve:              500.0, // €500 minimum cash
		// All modules enabled by default
		EnableProfitTakingCalc:               true,
		EnableAveragingDownCalc:              true,
		EnableOpportunityBuysCalc:            true,
		EnableRebalanceSellsCalc:             true,
		EnableRebalanceBuysCalc:              true,
		EnableWeightBasedCalc:                true,
		EnableDirectBuyPattern:               true,
		EnableProfitTakingPattern:            true,
		EnableRebalancePattern:               true,
		EnableAveragingDownPattern:           true,
		EnableSingleBestPattern:              true,
		EnableMultiSellPattern:               true,
		EnableMixedStrategyPattern:           true,
		EnableOpportunityFirstPattern:        true,
		EnableDeepRebalancePattern:           true,
		EnableCashGenerationPattern:          true,
		EnableCostOptimizedPattern:           true,
		EnableAdaptivePattern:                true,
		EnableMarketRegimePattern:            true,
		EnableCombinatorialGenerator:         true,
		EnableEnhancedCombinatorialGenerator: true,
		EnableConstraintRelaxationGenerator:  true,
		EnableCorrelationAwareFilter:         true,
		EnableDiversityFilter:                true,
		EnableEligibilityFilter:              true,
		EnableRecentlyTradedFilter:           true,
		EnableTagFiltering:                   true, // Tag filtering enabled by default
	}
}

// GetEnabledCalculators returns a list of enabled opportunity calculator names.
func (c *PlannerConfiguration) GetEnabledCalculators() []string {
	enabled := []string{}
	if c.EnableProfitTakingCalc {
		enabled = append(enabled, "profit_taking")
	}
	if c.EnableAveragingDownCalc {
		enabled = append(enabled, "averaging_down")
	}
	if c.EnableOpportunityBuysCalc {
		enabled = append(enabled, "opportunity_buys")
	}
	if c.EnableRebalanceSellsCalc {
		enabled = append(enabled, "rebalance_sells")
	}
	if c.EnableRebalanceBuysCalc {
		enabled = append(enabled, "rebalance_buys")
	}
	if c.EnableWeightBasedCalc {
		enabled = append(enabled, "weight_based")
	}
	return enabled
}

// GetEnabledPatterns returns a list of enabled pattern generator names.
func (c *PlannerConfiguration) GetEnabledPatterns() []string {
	enabled := []string{}
	if c.EnableDirectBuyPattern {
		enabled = append(enabled, "direct_buy")
	}
	if c.EnableProfitTakingPattern {
		enabled = append(enabled, "profit_taking")
	}
	if c.EnableRebalancePattern {
		enabled = append(enabled, "rebalance")
	}
	if c.EnableAveragingDownPattern {
		enabled = append(enabled, "averaging_down")
	}
	if c.EnableSingleBestPattern {
		enabled = append(enabled, "single_best")
	}
	if c.EnableMultiSellPattern {
		enabled = append(enabled, "multi_sell")
	}
	if c.EnableMixedStrategyPattern {
		enabled = append(enabled, "mixed_strategy")
	}
	if c.EnableOpportunityFirstPattern {
		enabled = append(enabled, "opportunity_first")
	}
	if c.EnableDeepRebalancePattern {
		enabled = append(enabled, "deep_rebalance")
	}
	if c.EnableCashGenerationPattern {
		enabled = append(enabled, "cash_generation")
	}
	if c.EnableCostOptimizedPattern {
		enabled = append(enabled, "cost_optimized")
	}
	if c.EnableAdaptivePattern {
		enabled = append(enabled, "adaptive")
	}
	if c.EnableMarketRegimePattern {
		enabled = append(enabled, "market_regime")
	}
	return enabled
}

// GetEnabledGenerators returns a list of enabled sequence generator names.
func (c *PlannerConfiguration) GetEnabledGenerators() []string {
	enabled := []string{}
	if c.EnableCombinatorialGenerator {
		enabled = append(enabled, "combinatorial")
	}
	if c.EnableEnhancedCombinatorialGenerator {
		enabled = append(enabled, "enhanced_combinatorial")
	}
	if c.EnableConstraintRelaxationGenerator {
		enabled = append(enabled, "constraint_relaxation")
	}
	return enabled
}

// GetEnabledFilters returns a list of enabled filter names.
func (c *PlannerConfiguration) GetEnabledFilters() []string {
	enabled := []string{}
	if c.EnableCorrelationAwareFilter {
		enabled = append(enabled, "correlation_aware")
	}
	if c.EnableDiversityFilter {
		enabled = append(enabled, "diversity")
	}
	if c.EnableEligibilityFilter {
		enabled = append(enabled, "eligibility")
	}
	if c.EnableRecentlyTradedFilter {
		enabled = append(enabled, "recently_traded")
	}
	return enabled
}

// GetCalculatorParams returns parameters for a specific calculator.
func (c *PlannerConfiguration) GetCalculatorParams(name string) map[string]interface{} {
	params := make(map[string]interface{})

	// Pass risk management settings to sell calculators
	if name == "profit_taking" || name == "rebalance_sells" {
		params["max_sell_percentage"] = c.MaxSellPercentage
		params["min_hold_days"] = float64(c.MinHoldDays)
	}

	return params
}

// GetPatternParams returns parameters for a specific pattern.
// Simplified: Returns empty map since we no longer store module-specific parameters.
func (c *PlannerConfiguration) GetPatternParams(name string) map[string]interface{} {
	// Parameters removed in simplified version - return empty map
	return make(map[string]interface{})
}

// GetGeneratorParams returns parameters for a specific generator.
func (c *PlannerConfiguration) GetGeneratorParams(name string) map[string]interface{} {
	params := make(map[string]interface{})
	// MaxDepth applies to all generators
	params["max_depth"] = float64(c.MaxDepth)
	return params
}

// GetFilterParams returns parameters for a specific filter.
func (c *PlannerConfiguration) GetFilterParams(name string) map[string]interface{} {
	params := make(map[string]interface{})
	// Wire DiversityWeight to diversity filter
	if name == "diversity" {
		if c.EnableDiverseSelection {
			// Use DiversityWeight as the minimum diversity score threshold
			// DiversityWeight 0.0-1.0 maps to min_diversity_score
			params["min_diversity_score"] = c.DiversityWeight
		}
	}
	return params
}
