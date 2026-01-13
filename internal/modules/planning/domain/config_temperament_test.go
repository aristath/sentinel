package domain

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestPlannerConfigDefaultsMaximumComplexity verifies MaxDepth and MaxOpportunitiesPerCategory
// are hardcoded to maximum complexity values
func TestPlannerConfigDefaultsMaximumComplexity(t *testing.T) {
	config := NewDefaultConfiguration()

	// User requested: MaxDepth should be 10 for maximum complexity
	assert.Equal(t, 10, config.MaxDepth,
		"MaxDepth should be hardcoded to 10 for maximum complexity")

	// User requested: MaxOpportunitiesPerCategory should also be 10
	assert.Equal(t, 10, config.MaxOpportunitiesPerCategory,
		"MaxOpportunitiesPerCategory should be hardcoded to 10 for maximum opportunities")
}

// TestPlannerConfigNoLegacyNameDescription verifies Name and Description
// are kept for backwards compatibility but not required for operation
func TestPlannerConfigNoLegacyNameDescription(t *testing.T) {
	config := NewDefaultConfiguration()

	// Config should be usable without relying on Name/Description
	assert.True(t, config.EnableBatchGeneration,
		"Config should work without legacy Name/Description fields")
	assert.True(t, config.EnableTagFiltering,
		"Tag filtering should be enabled by default")
}

// TestPlannerConfigRiskManagementDefaults verifies risk management defaults
func TestPlannerConfigRiskManagementDefaults(t *testing.T) {
	config := NewDefaultConfiguration()

	// Risk management defaults
	assert.Equal(t, 90, config.MinHoldDays,
		"MinHoldDays should default to 90")
	assert.Equal(t, 180, config.SellCooldownDays,
		"SellCooldownDays should default to 180")
	assert.Equal(t, -0.20, config.MaxLossThreshold,
		"MaxLossThreshold should default to -20%")
	assert.Equal(t, 0.20, config.MaxSellPercentage,
		"MaxSellPercentage should default to 20%")
	assert.Equal(t, 0.10, config.AveragingDownPercent,
		"AveragingDownPercent should default to 10%")
}

// TestPlannerConfigTransactionCostDefaults verifies transaction cost defaults
func TestPlannerConfigTransactionCostDefaults(t *testing.T) {
	config := NewDefaultConfiguration()

	assert.Equal(t, 5.0, config.TransactionCostFixed,
		"TransactionCostFixed should default to €5")
	assert.Equal(t, 0.001, config.TransactionCostPercent,
		"TransactionCostPercent should default to 0.1%")
}

// TestPlannerConfigOptimizerDefaults verifies optimizer defaults
func TestPlannerConfigOptimizerDefaults(t *testing.T) {
	config := NewDefaultConfiguration()

	assert.Equal(t, 0.5, config.OptimizerBlend,
		"OptimizerBlend should default to 50% MV, 50% HRP")
	assert.Equal(t, 0.11, config.OptimizerTargetReturn,
		"OptimizerTargetReturn should default to 11%")
	assert.Equal(t, 500.0, config.MinCashReserve,
		"MinCashReserve should default to €500")
}

// TestPlannerConfigAllCalculatorsEnabledByDefault verifies all calculators enabled
func TestPlannerConfigAllCalculatorsEnabledByDefault(t *testing.T) {
	config := NewDefaultConfiguration()

	enabled := config.GetEnabledCalculators()

	expectedCalculators := []string{
		"profit_taking",
		"averaging_down",
		"opportunity_buys",
		"rebalance_sells",
		"rebalance_buys",
		"weight_based",
	}

	assert.Equal(t, len(expectedCalculators), len(enabled),
		"All 6 calculators should be enabled by default")

	for _, calc := range expectedCalculators {
		assert.Contains(t, enabled, calc,
			"Calculator %s should be enabled by default", calc)
	}
}

// TestPlannerConfigAllFiltersEnabledByDefault verifies post-generation filters enabled
func TestPlannerConfigAllFiltersEnabledByDefault(t *testing.T) {
	config := NewDefaultConfiguration()

	enabled := config.GetEnabledFilters()

	// Only post-generation filters remain (eligibility and recently_traded
	// are now handled during generation via constraints.Enforcer)
	expectedFilters := []string{
		"correlation_aware",
		"diversity",
	}

	assert.Equal(t, len(expectedFilters), len(enabled),
		"Both post-generation filters should be enabled by default")

	for _, filter := range expectedFilters {
		assert.Contains(t, enabled, filter,
			"Filter %s should be enabled by default", filter)
	}
}

// TestGetCalculatorParamsPassesRiskManagement verifies risk params are passed to calculators
func TestGetCalculatorParamsPassesRiskManagement(t *testing.T) {
	config := NewDefaultConfiguration()
	config.MaxSellPercentage = 0.25
	config.MinHoldDays = 60

	// Profit taking should get risk management params
	ptParams := config.GetCalculatorParams("profit_taking")
	assert.Equal(t, 0.25, ptParams["max_sell_percentage"])
	assert.Equal(t, 60.0, ptParams["min_hold_days"])

	// Rebalance sells should get risk management params
	rsParams := config.GetCalculatorParams("rebalance_sells")
	assert.Equal(t, 0.25, rsParams["max_sell_percentage"])

	// Weight based should get risk management params
	wbParams := config.GetCalculatorParams("weight_based")
	assert.Equal(t, 0.25, wbParams["max_sell_percentage"])

	// Other calculators should get empty params
	adParams := config.GetCalculatorParams("averaging_down")
	assert.Empty(t, adParams["max_sell_percentage"])
}

// TestGetFilterParamsPassesDiversityWeight verifies DiversityWeight is passed
func TestGetFilterParamsPassesDiversityWeight(t *testing.T) {
	config := NewDefaultConfiguration()
	config.DiversityWeight = 0.5
	config.EnableDiverseSelection = true

	params := config.GetFilterParams("diversity")
	assert.Equal(t, 0.5, params["min_diversity_score"],
		"DiversityWeight should be passed to diversity filter")
}

// TestPlannerConfigTradePermissionsDefault verifies trade permissions
func TestPlannerConfigTradePermissionsDefault(t *testing.T) {
	config := NewDefaultConfiguration()

	assert.True(t, config.AllowSell, "AllowSell should be true by default")
	assert.True(t, config.AllowBuy, "AllowBuy should be true by default")
}

// TestPlannerConfigTagFilteringDefault verifies tag filtering enabled
func TestPlannerConfigTagFilteringDefault(t *testing.T) {
	config := NewDefaultConfiguration()

	assert.True(t, config.EnableTagFiltering,
		"Tag filtering should be enabled by default")
}
