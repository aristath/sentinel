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
	assert.Equal(t, 10, config.MaxDepth)
	assert.Equal(t, 10, config.MaxOpportunitiesPerCategory)
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

	// All calculators should be enabled by default
	assert.True(t, config.EnableProfitTakingCalc)
	assert.True(t, config.EnableAveragingDownCalc)
	assert.True(t, config.EnableOpportunityBuysCalc)
	assert.True(t, config.EnableRebalanceSellsCalc)
	assert.True(t, config.EnableRebalanceBuysCalc)
	assert.True(t, config.EnableWeightBasedCalc)

	// Post-generation filters should be enabled by default
	assert.True(t, config.EnableCorrelationAwareFilter)
	assert.True(t, config.EnableDiversityFilter)

	// Tag filtering should be enabled by default
	assert.True(t, config.EnableTagFiltering)
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

func TestGetEnabledFilters(t *testing.T) {
	config := NewDefaultConfiguration()
	enabled := config.GetEnabledFilters()

	// Default config has post-generation filters enabled
	assert.Len(t, enabled, 2)
	assert.Contains(t, enabled, "correlation_aware")
	assert.Contains(t, enabled, "diversity")
}

func TestGetEnabledFilters_SelectiveEnable(t *testing.T) {
	tests := []struct {
		name     string
		config   *PlannerConfiguration
		expected []string
	}{
		{
			name: "all filters enabled",
			config: &PlannerConfiguration{
				EnableCorrelationAwareFilter: true,
				EnableDiversityFilter:        true,
			},
			expected: []string{"correlation_aware", "diversity"},
		},
		{
			name: "only correlation enabled",
			config: &PlannerConfiguration{
				EnableCorrelationAwareFilter: true,
				EnableDiversityFilter:        false,
			},
			expected: []string{"correlation_aware"},
		},
		{
			name: "only diversity enabled",
			config: &PlannerConfiguration{
				EnableCorrelationAwareFilter: false,
				EnableDiversityFilter:        true,
			},
			expected: []string{"diversity"},
		},
		{
			name: "none enabled",
			config: &PlannerConfiguration{
				EnableCorrelationAwareFilter: false,
				EnableDiversityFilter:        false,
			},
			expected: []string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			enabled := tt.config.GetEnabledFilters()
			assert.ElementsMatch(t, tt.expected, enabled)
		})
	}
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

	t.Run("weight_based calculator", func(t *testing.T) {
		params := config.GetCalculatorParams("weight_based")
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

	// Test correlation_aware filter returns empty map
	params = config.GetFilterParams("correlation_aware")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}
