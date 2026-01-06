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
	config.EnableProfitTakingCalc = false
	config.EnableAveragingDownCalc = false
	config.EnableOpportunityBuysCalc = false
	config.EnableRebalanceSellsCalc = false
	config.EnableRebalanceBuysCalc = false
	config.EnableWeightBasedCalc = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "opportunity_calculators")
	assert.Contains(t, err.Error(), "at least one opportunity calculator must be enabled")
}

func TestValidator_Validate_NoPatternsEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all patterns
	config.EnableDirectBuyPattern = false
	config.EnableProfitTakingPattern = false
	config.EnableRebalancePattern = false
	config.EnableAveragingDownPattern = false
	config.EnableSingleBestPattern = false
	config.EnableMultiSellPattern = false
	config.EnableMixedStrategyPattern = false
	config.EnableOpportunityFirstPattern = false
	config.EnableDeepRebalancePattern = false
	config.EnableCashGenerationPattern = false
	config.EnableCostOptimizedPattern = false
	config.EnableAdaptivePattern = false
	config.EnableMarketRegimePattern = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "pattern_generators")
	assert.Contains(t, err.Error(), "at least one pattern generator must be enabled")
}

func TestValidator_Validate_NoGeneratorsEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all generators
	config.EnableCombinatorialGenerator = false
	config.EnableEnhancedCombinatorialGenerator = false
	config.EnableConstraintRelaxationGenerator = false

	err := validator.Validate(config)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "sequence_generators")
	assert.Contains(t, err.Error(), "at least one sequence generator must be enabled")
}

func TestValidator_Validate_NoFiltersEnabled(t *testing.T) {
	validator := NewValidator()
	config := domain.NewDefaultConfiguration()

	// Disable all filters
	config.EnableCorrelationAwareFilter = false
	config.EnableDiversityFilter = false
	config.EnableEligibilityFilter = false
	config.EnableRecentlyTradedFilter = false

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
	config.MaxOpportunitiesPerCategory = 0

	err := validator.Validate(config)
	assert.Error(t, err)

	errMsg := err.Error()
	assert.Contains(t, errMsg, "name is required")
	assert.Contains(t, errMsg, "max_depth")
	assert.Contains(t, errMsg, "max_opportunities_per_category")

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
		config.EnableProfitTakingCalc = false
		config.EnableAveragingDownCalc = false
		config.EnableOpportunityBuysCalc = false
		config.EnableRebalanceSellsCalc = false
		config.EnableRebalanceBuysCalc = false
		config.EnableWeightBasedCalc = false

		// Quick validation should pass (doesn't check module enablement)
		err := validator.ValidateQuick(config)
		assert.NoError(t, err)
	})
}

func TestValidator_ValidateParams(t *testing.T) {
	validator := NewValidator()

	t.Run("valid profit_taking params", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": 0.15,
			"windfall_score": 0.7,
			"min_hold_days":  float64(90),
			"sell_cooldown":  float64(180),
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.NoError(t, err)
	})

	t.Run("missing required parameter", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": 0.15,
			// Missing windfall_score, min_hold_days, sell_cooldown
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "required parameter is missing")
	})

	t.Run("invalid threshold range", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": 1.5, // Invalid: > 1.0
			"windfall_score": 0.7,
			"min_hold_days":  float64(90),
			"sell_cooldown":  float64(180),
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "must be between 0.0 and 1.0")
	})

	t.Run("invalid count parameter", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": 0.15,
			"windfall_score": 0.7,
			"min_hold_days":  float64(-10), // Invalid: negative
			"sell_cooldown":  float64(180),
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "must be > 0")
	})

	t.Run("cross-parameter constraint violation", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": 0.15,
			"windfall_score": 0.7,
			"min_hold_days":  float64(200), // Invalid: >= sell_cooldown
			"sell_cooldown":  float64(180),
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "min_hold_days must be less than sell_cooldown")
	})

	t.Run("unknown module accepts any params", func(t *testing.T) {
		params := map[string]interface{}{
			"arbitrary_key": "arbitrary_value",
		}
		err := validator.ValidateParams("unknown_module", params)
		assert.NoError(t, err) // Unknown modules accept any params
	})

	t.Run("module with no required params", func(t *testing.T) {
		params := map[string]interface{}{}
		err := validator.ValidateParams("direct_buy", params)
		assert.NoError(t, err) // direct_buy has no required params
	})

	t.Run("averaging_down cross-constraint", func(t *testing.T) {
		params := map[string]interface{}{
			"loss_threshold":    0.25, // Invalid: > max_loss_allowed
			"max_loss_allowed":  0.20,
			"buy_cooldown_days": float64(180),
		}
		err := validator.ValidateParams("averaging_down", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "loss_threshold cannot exceed max_loss_allowed")
	})

	t.Run("enhanced_combinatorial cross-constraint", func(t *testing.T) {
		params := map[string]interface{}{
			"max_combinations":  float64(2000), // High combinations
			"pruning_threshold": 0.95,          // High pruning
		}
		err := validator.ValidateParams("enhanced_combinatorial", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "may filter too aggressively")
	})

	t.Run("invalid parameter types", func(t *testing.T) {
		params := map[string]interface{}{
			"gain_threshold": "not a number", // Invalid type
			"windfall_score": 0.7,
			"min_hold_days":  float64(90),
			"sell_cooldown":  float64(180),
		}
		err := validator.ValidateParams("profit_taking", params)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "must be a number")
	})

	t.Run("validation errors formatting", func(t *testing.T) {
		err := ValidationError{
			Field:   "test_field",
			Message: "test message",
		}
		assert.Equal(t, "test_field: test message", err.Error())

		errors := ValidationErrors{
			{Field: "field1", Message: "msg1"},
			{Field: "field2", Message: "msg2"},
		}
		errStr := errors.Error()
		assert.Contains(t, errStr, "field1: msg1")
		assert.Contains(t, errStr, "field2: msg2")
		assert.Contains(t, errStr, ";")
	})

	t.Run("ValidateParams edge cases", func(t *testing.T) {
		t.Run("invalid threshold value", func(t *testing.T) {
			params := map[string]interface{}{
				"gain_threshold": 1.5, // > 1.0
				"windfall_score": 0.7,
				"min_hold_days":  float64(90),
				"sell_cooldown":  float64(180),
			}
			err := validator.ValidateParams("profit_taking", params)
			assert.Error(t, err)
		})

		t.Run("invalid weight value", func(t *testing.T) {
			params := map[string]interface{}{
				"scoring_weight":    1.5, // > 1.0
				"max_opportunities": float64(5),
			}
			err := validator.ValidateParams("opportunity_buys", params)
			assert.Error(t, err)
		})

		t.Run("invalid count as float zero", func(t *testing.T) {
			params := map[string]interface{}{
				"gain_threshold": 0.15,
				"windfall_score": 0.7,
				"min_hold_days":  float64(0), // Zero
				"sell_cooldown":  float64(180),
			}
			err := validator.ValidateParams("profit_taking", params)
			assert.Error(t, err)
		})

		t.Run("invalid count as negative int", func(t *testing.T) {
			params := map[string]interface{}{
				"max_combinations": -10,
			}
			err := validator.ValidateParams("combinatorial", params)
			assert.Error(t, err)
		})

		t.Run("invalid percentage", func(t *testing.T) {
			// Test with a module that uses percentage (if any)
			// For now, just test that validators work
			params := map[string]interface{}{
				"correlation_threshold": 0.85,
			}
			err := validator.ValidateParams("correlation_aware", params)
			assert.NoError(t, err) // Should pass with valid threshold
		})

		t.Run("invalid factor", func(t *testing.T) {
			params := map[string]interface{}{
				"adaptation_rate": 0.0, // Zero factor
			}
			err := validator.ValidateParams("adaptive", params)
			assert.Error(t, err)
		})
	})

	t.Run("ValidateParams all module types", func(t *testing.T) {
		modules := []struct {
			name   string
			params map[string]interface{}
			valid  bool
		}{
			{"rebalance_sells", map[string]interface{}{"over_weight_threshold": 0.05}, true},
			{"rebalance_buys", map[string]interface{}{"under_weight_threshold": 0.05}, true},
			{"weight_based", map[string]interface{}{"target_weight_tolerance": 0.02}, true},
			{"combinatorial", map[string]interface{}{"max_combinations": float64(100)}, true},
			{"constraint_relaxation", map[string]interface{}{"relaxation_factor": 1.5}, true},
			{"diversity", map[string]interface{}{"diversity_threshold": 0.3}, true},
			{"recently_traded", map[string]interface{}{"cooldown_days": float64(30)}, true},
			{"market_regime", map[string]interface{}{"regime_threshold": 0.5}, true},
		}

		for _, tt := range modules {
			t.Run(tt.name, func(t *testing.T) {
				err := validator.ValidateParams(tt.name, tt.params)
				if tt.valid {
					assert.NoError(t, err, "Module %s should be valid", tt.name)
				} else {
					assert.Error(t, err, "Module %s should be invalid", tt.name)
				}
			})
		}
	})
}
