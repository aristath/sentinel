package config

import (
	"strings"
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/stretchr/testify/assert"
)

func TestValidator_Validate_ValidConfig(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	err := validator.Validate(config)
	assert.NoError(t, err)
}

func TestValidator_Validate_MissingName(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()
	config.Name = ""

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "name is required")
}

func TestValidator_Validate_InvalidMaxDepth(t *testing.T) {
	tests := []struct {
		name     string
		maxDepth int
		wantErr  bool
		errMsg   string
	}{
		{
			name:     "zero depth",
			maxDepth: 0,
			wantErr:  true,
			errMsg:   "must be greater than 0",
		},
		{
			name:     "negative depth",
			maxDepth: -1,
			wantErr:  true,
			errMsg:   "must be greater than 0",
		},
		{
			name:     "too high depth",
			maxDepth: 15,
			wantErr:  true,
			errMsg:   "must be <= 10",
		},
		{
			name:     "valid depth",
			maxDepth: 5,
			wantErr:  false,
		},
	}

	validator := NewValidator()

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := domain.NewDefaultConfiguration()
			config.MaxDepth = tt.maxDepth

			err := validator.Validate(config)
			if tt.wantErr {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), tt.errMsg)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestValidator_Validate_InvalidMaxOpportunitiesPerCategory(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()
	config.MaxOpportunitiesPerCategory = 0

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "max_opportunities_per_category")
	assert.Contains(t, err.Error(), "must be greater than 0")
}

func TestValidator_Validate_InvalidPriorityThreshold(t *testing.T) {
	tests := []struct {
		name      string
		threshold float64
		wantErr   bool
	}{
		{
			name:      "negative threshold",
			threshold: -0.1,
			wantErr:   true,
		},
		{
			name:      "too high threshold",
			threshold: 1.5,
			wantErr:   true,
		},
		{
			name:      "valid threshold 0.0",
			threshold: 0.0,
			wantErr:   false,
		},
		{
			name:      "valid threshold 1.0",
			threshold: 1.0,
			wantErr:   false,
		},
		{
			name:      "valid threshold 0.5",
			threshold: 0.5,
			wantErr:   false,
		},
	}

	validator := NewValidator()

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := domain.NewDefaultConfiguration()
			config.PriorityThreshold = tt.threshold

			err := validator.Validate(config)
			if tt.wantErr {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), "priority_threshold")
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestValidator_Validate_InvalidBeamWidth(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()
	config.BeamWidth = 0

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "beam_width")
	assert.Contains(t, err.Error(), "must be greater than 0")
}

func TestValidator_Validate_InvalidDiversityWeight(t *testing.T) {
	tests := []struct {
		name   string
		weight float64
		valid  bool
	}{
		{"negative", -0.1, false},
		{"too high", 1.5, false},
		{"zero", 0.0, true},
		{"one", 1.0, true},
		{"middle", 0.5, true},
	}

	validator := NewValidator()

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := domain.NewDefaultConfiguration()
			config.DiversityWeight = tt.weight

			err := validator.Validate(config)
			if !tt.valid {
				assert.Error(t, err)
				assert.Contains(t, err.Error(), "diversity_weight")
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestValidator_Validate_InvalidTransactionCosts(t *testing.T) {
	validator := NewValidator()

	t.Run("negative fixed cost", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		config.TransactionCostFixed = -1.0

		err := validator.Validate(config)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "transaction_cost_fixed")
	})

	t.Run("negative percent cost", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		config.TransactionCostPercent = -0.01

		err := validator.Validate(config)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "transaction_cost_percent")
	})
}

func TestValidator_Validate_NoCalculatorsEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all calculators
	config.OpportunityCalculators.ProfitTaking.Enabled = false
	config.OpportunityCalculators.AveragingDown.Enabled = false
	config.OpportunityCalculators.OpportunityBuys.Enabled = false
	config.OpportunityCalculators.RebalanceSells.Enabled = false
	config.OpportunityCalculators.RebalanceBuys.Enabled = false
	config.OpportunityCalculators.WeightBased.Enabled = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "opportunity_calculators")
	assert.Contains(t, err.Error(), "at least one opportunity calculator must be enabled")
}

func TestValidator_Validate_NoPatternsEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all patterns
	config.PatternGenerators.DirectBuy.Enabled = false
	config.PatternGenerators.ProfitTaking.Enabled = false
	config.PatternGenerators.Rebalance.Enabled = false
	config.PatternGenerators.AveragingDown.Enabled = false
	config.PatternGenerators.SingleBest.Enabled = false
	config.PatternGenerators.MultiSell.Enabled = false
	config.PatternGenerators.MixedStrategy.Enabled = false
	config.PatternGenerators.OpportunityFirst.Enabled = false
	config.PatternGenerators.DeepRebalance.Enabled = false
	config.PatternGenerators.CashGeneration.Enabled = false
	config.PatternGenerators.CostOptimized.Enabled = false
	config.PatternGenerators.Adaptive.Enabled = false
	config.PatternGenerators.MarketRegime.Enabled = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "pattern_generators")
	assert.Contains(t, err.Error(), "at least one pattern generator must be enabled")
}

func TestValidator_Validate_NoGeneratorsEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all generators
	config.SequenceGenerators.Combinatorial.Enabled = false
	config.SequenceGenerators.EnhancedCombinatorial.Enabled = false
	config.SequenceGenerators.PartialExecution.Enabled = false
	config.SequenceGenerators.ConstraintRelaxation.Enabled = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "sequence_generators")
	assert.Contains(t, err.Error(), "at least one sequence generator must be enabled")
}

func TestValidator_Validate_NoFiltersEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all filters
	config.Filters.CorrelationAware.Enabled = false
	config.Filters.Diversity.Enabled = false
	config.Filters.Eligibility.Enabled = false
	config.Filters.RecentlyTraded.Enabled = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "filters")
	assert.Contains(t, err.Error(), "at least one filter must be enabled")
}

func TestValidator_Validate_NoBuyOrSellAllowed(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()
	config.AllowBuy = false
	config.AllowSell = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "allow_buy/allow_sell")
	assert.Contains(t, err.Error(), "at least one of allow_buy or allow_sell must be true")
}

func TestValidator_Validate_MultipleErrors(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Introduce multiple errors
	config.Name = ""
	config.MaxDepth = 0
	config.PriorityThreshold = 1.5

	err := validator.Validate(config)
	assert.Error(t, err)

	errMsg := err.Error()
	assert.Contains(t, errMsg, "name is required")
	assert.Contains(t, errMsg, "max_depth")
	assert.Contains(t, errMsg, "priority_threshold")

	// Check that errors are separated by semicolon
	assert.True(t, strings.Count(errMsg, ";") >= 2)
}

func TestValidator_ValidateQuick(t *testing.T) {
	validator := NewValidator()

	t.Run("valid config", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		err := validator.ValidateQuick(config)
		assert.NoError(t, err)
	})

	t.Run("missing name", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		config.Name = ""
		err := validator.ValidateQuick(config)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "name is required")
	})

	t.Run("invalid max depth", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		config.MaxDepth = 0
		err := validator.ValidateQuick(config)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "max_depth")
	})

	t.Run("quick validation doesn't check modules", func(t *testing.T) {
		config := domain.NewDefaultConfiguration()
		// Disable all calculators
		config.OpportunityCalculators.ProfitTaking.Enabled = false
		config.OpportunityCalculators.AveragingDown.Enabled = false
		config.OpportunityCalculators.OpportunityBuys.Enabled = false
		config.OpportunityCalculators.RebalanceSells.Enabled = false
		config.OpportunityCalculators.RebalanceBuys.Enabled = false
		config.OpportunityCalculators.WeightBased.Enabled = false

		// Quick validation should pass (doesn't check module enablement)
		err := validator.ValidateQuick(config)
		assert.NoError(t, err)
	})
}

func TestValidator_ValidateParams(t *testing.T) {
	validator := NewValidator()

	// Currently a placeholder - should always return nil
	params := map[string]interface{}{
		"key": "value",
	}

	err := validator.ValidateParams("some_module", params)
	assert.NoError(t, err)

	err = validator.ValidateParams("", nil)
	assert.NoError(t, err)
}
