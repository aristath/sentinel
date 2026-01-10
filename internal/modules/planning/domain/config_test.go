package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNewDefaultConfiguration(t *testing.T) {
	config := NewDefaultConfiguration()

	assert.NotNil(t, config)
	assert.Equal(t, "default", config.Name)
	assert.True(t, config.EnableBatchGeneration)
	assert.Equal(t, 5, config.MaxDepth)
	assert.Equal(t, 5, config.MaxOpportunitiesPerCategory)
	assert.True(t, config.EnableDiverseSelection)
	assert.Equal(t, 0.3, config.DiversityWeight)
	assert.Equal(t, 5.0, config.TransactionCostFixed)
	assert.Equal(t, 0.001, config.TransactionCostPercent)
	assert.True(t, config.AllowSell)
	assert.True(t, config.AllowBuy)
	assert.Equal(t, 90, config.MinHoldDays)
	assert.Equal(t, 180, config.SellCooldownDays)
	assert.Equal(t, -0.20, config.MaxLossThreshold)
	assert.Equal(t, 0.20, config.MaxSellPercentage)

	// All modules should be enabled by default
	assert.True(t, config.EnableProfitTakingCalc)
	assert.True(t, config.EnableAveragingDownCalc)
	assert.True(t, config.EnableOpportunityBuysCalc)
	assert.True(t, config.EnableRebalanceSellsCalc)
	assert.True(t, config.EnableRebalanceBuysCalc)
	assert.True(t, config.EnableWeightBasedCalc)
	assert.True(t, config.EnableDirectBuyPattern)
	assert.True(t, config.EnableProfitTakingPattern)
	assert.True(t, config.EnableRebalancePattern)
	assert.True(t, config.EnableAdaptivePattern)
	assert.True(t, config.EnableCombinatorialGenerator)
	assert.True(t, config.EnableCorrelationAwareFilter)
}

func TestGetEnabledCalculators(t *testing.T) {
	tests := []struct {
		name     string
		config   *PlannerConfiguration
		expected []string
	}{
		{
			name: "all enabled",
			config: &PlannerConfiguration{
				EnableProfitTakingCalc:    true,
				EnableAveragingDownCalc:   true,
				EnableOpportunityBuysCalc: true,
				EnableRebalanceSellsCalc:  true,
				EnableRebalanceBuysCalc:   true,
				EnableWeightBasedCalc:     true,
			},
			expected: []string{"profit_taking", "averaging_down", "opportunity_buys", "rebalance_sells", "rebalance_buys", "weight_based"},
		},
		{
			name: "only profit taking enabled",
			config: &PlannerConfiguration{
				EnableProfitTakingCalc:    true,
				EnableAveragingDownCalc:   false,
				EnableOpportunityBuysCalc: false,
				EnableRebalanceSellsCalc:  false,
				EnableRebalanceBuysCalc:   false,
				EnableWeightBasedCalc:     false,
			},
			expected: []string{"profit_taking"},
		},
		{
			name: "none enabled",
			config: &PlannerConfiguration{
				EnableProfitTakingCalc:    false,
				EnableAveragingDownCalc:   false,
				EnableOpportunityBuysCalc: false,
				EnableRebalanceSellsCalc:  false,
				EnableRebalanceBuysCalc:   false,
				EnableWeightBasedCalc:     false,
			},
			expected: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			enabled := tt.config.GetEnabledCalculators()
			assert.ElementsMatch(t, tt.expected, enabled)
		})
	}
}

func TestGetEnabledPatterns(t *testing.T) {
	config := NewDefaultConfiguration()
	enabled := config.GetEnabledPatterns()

	// Default config has all patterns enabled
	assert.Len(t, enabled, 13)
	assert.Contains(t, enabled, "direct_buy")
	assert.Contains(t, enabled, "profit_taking")
	assert.Contains(t, enabled, "rebalance")
	assert.Contains(t, enabled, "averaging_down")
	assert.Contains(t, enabled, "single_best")
	assert.Contains(t, enabled, "multi_sell")
	assert.Contains(t, enabled, "mixed_strategy")
	assert.Contains(t, enabled, "opportunity_first")
	assert.Contains(t, enabled, "deep_rebalance")
	assert.Contains(t, enabled, "cash_generation")
	assert.Contains(t, enabled, "cost_optimized")
	assert.Contains(t, enabled, "adaptive")
	assert.Contains(t, enabled, "market_regime")
}

func TestGetEnabledGenerators(t *testing.T) {
	config := NewDefaultConfiguration()
	enabled := config.GetEnabledGenerators()

	// Default config has all generators enabled
	assert.Len(t, enabled, 3)
	assert.Contains(t, enabled, "combinatorial")
	assert.Contains(t, enabled, "enhanced_combinatorial")
	assert.Contains(t, enabled, "constraint_relaxation")
}

func TestGetEnabledFilters(t *testing.T) {
	config := NewDefaultConfiguration()
	enabled := config.GetEnabledFilters()

	// Default config has all filters enabled
	assert.Len(t, enabled, 4)
	assert.Contains(t, enabled, "correlation_aware")
	assert.Contains(t, enabled, "diversity")
	assert.Contains(t, enabled, "eligibility")
	assert.Contains(t, enabled, "recently_traded")
}

func TestGetCalculatorParams(t *testing.T) {
	config := &PlannerConfiguration{
		MaxSellPercentage: 0.28,
		MinHoldDays:       90,
	}

	// Sell calculators should receive max_sell_percentage and min_hold_days
	t.Run("profit_taking calculator", func(t *testing.T) {
		params := config.GetCalculatorParams("profit_taking")
		assert.NotNil(t, params)
		assert.Contains(t, params, "max_sell_percentage")
		assert.Equal(t, 0.28, params["max_sell_percentage"])
		assert.Contains(t, params, "min_hold_days")
		assert.Equal(t, float64(90), params["min_hold_days"])
	})

	t.Run("rebalance_sells calculator", func(t *testing.T) {
		params := config.GetCalculatorParams("rebalance_sells")
		assert.NotNil(t, params)
		assert.Contains(t, params, "max_sell_percentage")
		assert.Equal(t, 0.28, params["max_sell_percentage"])
		assert.Contains(t, params, "min_hold_days")
		assert.Equal(t, float64(90), params["min_hold_days"])
	})

	// Buy calculators should return empty map
	t.Run("non-sell calculator", func(t *testing.T) {
		params := config.GetCalculatorParams("opportunity_buys")
		assert.NotNil(t, params)
		assert.Len(t, params, 0)
	})

	// Non-existent calculator should return empty map
	t.Run("non-existent calculator", func(t *testing.T) {
		params := config.GetCalculatorParams("non_existent")
		assert.NotNil(t, params)
		assert.Len(t, params, 0)
	})
}

func TestGetPatternParams(t *testing.T) {
	config := &PlannerConfiguration{}

	// Simplified: Returns empty map (parameters removed)
	params := config.GetPatternParams("adaptive")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)

	// Non-existent pattern should return empty map
	params = config.GetPatternParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}

func TestGetGeneratorParams(t *testing.T) {
	config := &PlannerConfiguration{}

	// GetGeneratorParams always returns max_depth parameter
	params := config.GetGeneratorParams("combinatorial")
	assert.NotNil(t, params)
	assert.Contains(t, params, "max_depth")
	assert.Equal(t, float64(0), params["max_depth"])

	// Non-existent generator still returns max_depth
	params = config.GetGeneratorParams("non_existent")
	assert.NotNil(t, params)
	assert.Contains(t, params, "max_depth")
}

func TestGetFilterParams(t *testing.T) {
	config := &PlannerConfiguration{
		EnableDiverseSelection: true,
		DiversityWeight:        0.5,
	}

	// Diversity filter should return params with DiversityWeight
	params := config.GetFilterParams("diversity")
	assert.NotNil(t, params)
	assert.Contains(t, params, "min_diversity_score")
	assert.Equal(t, 0.5, params["min_diversity_score"])

	// Non-existent filter should return empty map
	params = config.GetFilterParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)

	// If EnableDiverseSelection is false, should return empty map (filter disabled)
	config.EnableDiverseSelection = false
	params = config.GetFilterParams("diversity")
	assert.NotNil(t, params)
	// When disabled, params are not returned
	assert.NotContains(t, params, "min_diversity_score")
	assert.Len(t, params, 0)

	// Test with DiversityWeight at boundaries
	config.EnableDiverseSelection = true
	config.DiversityWeight = 0.0
	params = config.GetFilterParams("diversity")
	assert.Contains(t, params, "min_diversity_score")
	assert.Equal(t, 0.0, params["min_diversity_score"])

	config.DiversityWeight = 1.0
	params = config.GetFilterParams("diversity")
	assert.Contains(t, params, "min_diversity_score")
	assert.Equal(t, 1.0, params["min_diversity_score"])

	// Test other filters return empty map
	params = config.GetFilterParams("correlation_aware")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)

	params = config.GetFilterParams("eligibility")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)

	params = config.GetFilterParams("recently_traded")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}
