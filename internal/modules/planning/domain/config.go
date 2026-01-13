// Package domain provides planning domain models.
package domain

// PlannerConfiguration represents the complete configuration for a planner instance.
type PlannerConfiguration struct {
	Name                  string `json:"name"`
	Description           string `json:"description"`
	EnableBatchGeneration bool   `json:"enable_batch_generation"`

	// Global planner settings
	MaxDepth                    int     `json:"max_depth"`
	MaxOpportunitiesPerCategory int     `json:"max_opportunities_per_category"`
	EnableDiverseSelection      bool    `json:"enable_diverse_selection"`
	DiversityWeight             float64 `json:"diversity_weight"`
	MaxSequenceAttempts         int     `json:"max_sequence_attempts"` // Maximum number of top-scoring sequences to consider

	// Transaction costs
	TransactionCostFixed   float64 `json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `json:"transaction_cost_percent"`

	// Trade permissions
	AllowSell bool `json:"allow_sell"`
	AllowBuy  bool `json:"allow_buy"`

	// Risk management settings
	MinHoldDays          int     `json:"min_hold_days"`          // Minimum days a position must be held before selling
	SellCooldownDays     int     `json:"sell_cooldown_days"`     // Days to wait after selling before buying again
	MaxLossThreshold     float64 `json:"max_loss_threshold"`     // Maximum loss threshold before forced selling consideration
	MaxSellPercentage    float64 `json:"max_sell_percentage"`    // Maximum percentage of position allowed to sell per transaction
	AveragingDownPercent float64 `json:"averaging_down_percent"` // Maximum percentage of position to add when averaging down

	// Portfolio optimizer settings
	OptimizerBlend        float64 `json:"optimizer_blend"`         // 0.0 = pure Mean-Variance, 1.0 = pure HRP
	OptimizerTargetReturn float64 `json:"optimizer_target_return"` // Target annual return for MV component
	MinCashReserve        float64 `json:"min_cash_reserve"`        // Minimum cash to keep (never fully deploy)

	// Opportunity Calculator enabled flags
	EnableProfitTakingCalc    bool `json:"enable_profit_taking_calc"`
	EnableAveragingDownCalc   bool `json:"enable_averaging_down_calc"`
	EnableOpportunityBuysCalc bool `json:"enable_opportunity_buys_calc"`
	EnableRebalanceSellsCalc  bool `json:"enable_rebalance_sells_calc"`
	EnableRebalanceBuysCalc   bool `json:"enable_rebalance_buys_calc"`
	EnableWeightBasedCalc     bool `json:"enable_weight_based_calc"`

	// Filter enabled flags (post-generation filters only)
	// Note: Eligibility and RecentlyTraded filters are now handled during generation
	// via constraints.Enforcer, not as post-generation filters.
	EnableCorrelationAwareFilter bool `json:"enable_correlation_aware_filter"`
	EnableDiversityFilter        bool `json:"enable_diversity_filter"`

	// Tag filtering
	EnableTagFiltering bool `json:"enable_tag_filtering"` // Enable/disable tag-based pre-filtering
}

// NewDefaultConfiguration creates a PlannerConfiguration with default settings.
func NewDefaultConfiguration() *PlannerConfiguration {
	return &PlannerConfiguration{
		Name:                        "default",
		Description:                 "",
		EnableBatchGeneration:       true,
		MaxDepth:                    10, // Maximum complexity for exhaustive generation
		MaxOpportunitiesPerCategory: 10,
		MaxSequenceAttempts:         20, // Evaluate top 20 sequences to select the best one
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
		AveragingDownPercent:        0.10,  // 10% of position
		OptimizerBlend:              0.5,   // 50% MV, 50% HRP
		OptimizerTargetReturn:       0.11,  // 11% target annual return
		MinCashReserve:              500.0, // €500 minimum cash
		// All calculators enabled by default
		EnableProfitTakingCalc:    true,
		EnableAveragingDownCalc:   true,
		EnableOpportunityBuysCalc: true,
		EnableRebalanceSellsCalc:  true,
		EnableRebalanceBuysCalc:   true,
		EnableWeightBasedCalc:     true,
		// Post-generation filters enabled by default
		EnableCorrelationAwareFilter: true,
		EnableDiversityFilter:        true,
		// Tag filtering enabled by default
		EnableTagFiltering: true,
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

// GetEnabledFilters returns a list of enabled post-generation filter names.
// Note: Eligibility and RecentlyTraded filtering is now done during generation.
func (c *PlannerConfiguration) GetEnabledFilters() []string {
	enabled := []string{}
	if c.EnableCorrelationAwareFilter {
		enabled = append(enabled, "correlation_aware")
	}
	if c.EnableDiversityFilter {
		enabled = append(enabled, "diversity")
	}
	return enabled
}

// GetCalculatorParams returns parameters for a specific calculator.
func (c *PlannerConfiguration) GetCalculatorParams(name string) map[string]interface{} {
	params := make(map[string]interface{})

	// Pass risk management settings to sell calculators
	if name == "profit_taking" || name == "rebalance_sells" || name == "weight_based" {
		params["max_sell_percentage"] = c.MaxSellPercentage
		params["min_hold_days"] = float64(c.MinHoldDays)
	}

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
