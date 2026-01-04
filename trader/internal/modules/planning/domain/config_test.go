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
	assert.Equal(t, 0.3, config.PriorityThreshold)
	assert.Equal(t, 10, config.BeamWidth)
	assert.True(t, config.EnableDiverseSelection)
	assert.Equal(t, 0.3, config.DiversityWeight)
	assert.Equal(t, 5.0, config.TransactionCostFixed)
	assert.Equal(t, 0.001, config.TransactionCostPercent)
	assert.True(t, config.AllowSell)
	assert.True(t, config.AllowBuy)
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
				OpportunityCalculators: OpportunityCalculatorsConfig{
					ProfitTaking:    ModuleConfig{Enabled: true},
					AveragingDown:   ModuleConfig{Enabled: true},
					OpportunityBuys: ModuleConfig{Enabled: true},
					RebalanceSells:  ModuleConfig{Enabled: true},
					RebalanceBuys:   ModuleConfig{Enabled: true},
					WeightBased:     ModuleConfig{Enabled: true},
				},
			},
			expected: []string{"profit_taking", "averaging_down", "opportunity_buys", "rebalance_sells", "rebalance_buys", "weight_based"},
		},
		{
			name: "only profit taking enabled",
			config: &PlannerConfiguration{
				OpportunityCalculators: OpportunityCalculatorsConfig{
					ProfitTaking:    ModuleConfig{Enabled: true},
					AveragingDown:   ModuleConfig{Enabled: false},
					OpportunityBuys: ModuleConfig{Enabled: false},
					RebalanceSells:  ModuleConfig{Enabled: false},
					RebalanceBuys:   ModuleConfig{Enabled: false},
					WeightBased:     ModuleConfig{Enabled: false},
				},
			},
			expected: []string{"profit_taking"},
		},
		{
			name: "none enabled",
			config: &PlannerConfiguration{
				OpportunityCalculators: OpportunityCalculatorsConfig{
					ProfitTaking:    ModuleConfig{Enabled: false},
					AveragingDown:   ModuleConfig{Enabled: false},
					OpportunityBuys: ModuleConfig{Enabled: false},
					RebalanceSells:  ModuleConfig{Enabled: false},
					RebalanceBuys:   ModuleConfig{Enabled: false},
					WeightBased:     ModuleConfig{Enabled: false},
				},
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
	assert.Len(t, enabled, 4)
	assert.Contains(t, enabled, "combinatorial")
	assert.Contains(t, enabled, "enhanced_combinatorial")
	assert.Contains(t, enabled, "partial_execution")
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
		OpportunityCalculators: OpportunityCalculatorsConfig{
			ProfitTaking: ModuleConfig{
				Enabled: true,
				Params: map[string]interface{}{
					"min_gain_threshold": 0.15,
					"windfall_threshold": 0.30,
				},
			},
		},
	}

	params := config.GetCalculatorParams("profit_taking")
	assert.NotNil(t, params)
	assert.Equal(t, 0.15, params["min_gain_threshold"])
	assert.Equal(t, 0.30, params["windfall_threshold"])

	// Non-existent calculator should return empty map
	params = config.GetCalculatorParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}

func TestGetPatternParams(t *testing.T) {
	config := &PlannerConfiguration{
		PatternGenerators: PatternGeneratorsConfig{
			Adaptive: ModuleConfig{
				Enabled: true,
				Params: map[string]interface{}{
					"market_regime_threshold": 0.7,
				},
			},
		},
	}

	params := config.GetPatternParams("adaptive")
	assert.NotNil(t, params)
	assert.Equal(t, 0.7, params["market_regime_threshold"])

	// Non-existent pattern should return empty map
	params = config.GetPatternParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}

func TestGetGeneratorParams(t *testing.T) {
	config := &PlannerConfiguration{
		SequenceGenerators: SequenceGeneratorsConfig{
			Combinatorial: ModuleConfig{
				Enabled: true,
				Params: map[string]interface{}{
					"max_combinations": 100,
				},
			},
		},
	}

	params := config.GetGeneratorParams("combinatorial")
	assert.NotNil(t, params)
	assert.Equal(t, 100, params["max_combinations"])

	// Non-existent generator should return empty map
	params = config.GetGeneratorParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}

func TestGetFilterParams(t *testing.T) {
	config := &PlannerConfiguration{
		Filters: FiltersConfig{
			Diversity: ModuleConfig{
				Enabled: true,
				Params: map[string]interface{}{
					"min_diversity_score": 0.5,
				},
			},
		},
	}

	params := config.GetFilterParams("diversity")
	assert.NotNil(t, params)
	assert.Equal(t, 0.5, params["min_diversity_score"])

	// Non-existent filter should return empty map
	params = config.GetFilterParams("non_existent")
	assert.NotNil(t, params)
	assert.Len(t, params, 0)
}
