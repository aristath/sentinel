// Package config provides planning configuration functionality.
package config

import (
	"fmt"
	"strings"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
)

// ValidationError represents a configuration validation error.
type ValidationError struct {
	Field   string
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("%s: %s", e.Field, e.Message)
}

// ValidationErrors represents multiple validation errors.
type ValidationErrors []ValidationError

func (e ValidationErrors) Error() string {
	var messages []string
	for _, err := range e {
		messages = append(messages, err.Error())
	}
	return strings.Join(messages, "; ")
}

// Validator validates planner configurations.
type Validator struct{}

// NewValidator creates a new configuration validator.
func NewValidator() *Validator {
	return &Validator{}
}

// Validate validates a planner configuration.
// Returns ValidationErrors if the configuration is invalid.
func (v *Validator) Validate(config *domain.PlannerConfiguration) error {
	var errors ValidationErrors

	// Validate basic fields
	if config.Name == "" {
		errors = append(errors, ValidationError{
			Field:   "name",
			Message: "name is required",
		})
	}

	// Validate numeric ranges
	if config.MaxDepth <= 0 {
		errors = append(errors, ValidationError{
			Field:   "max_depth",
			Message: "must be greater than 0",
		})
	}

	if config.MaxDepth > 10 {
		errors = append(errors, ValidationError{
			Field:   "max_depth",
			Message: "must be <= 10 (higher values can cause performance issues)",
		})
	}

	if config.MaxOpportunitiesPerCategory <= 0 {
		errors = append(errors, ValidationError{
			Field:   "max_opportunities_per_category",
			Message: "must be greater than 0",
		})
	}

	if config.DiversityWeight < 0.0 || config.DiversityWeight > 1.0 {
		errors = append(errors, ValidationError{
			Field:   "diversity_weight",
			Message: "must be between 0.0 and 1.0",
		})
	}

	if config.TransactionCostFixed < 0.0 {
		errors = append(errors, ValidationError{
			Field:   "transaction_cost_fixed",
			Message: "must be >= 0.0",
		})
	}

	if config.TransactionCostPercent < 0.0 {
		errors = append(errors, ValidationError{
			Field:   "transaction_cost_percent",
			Message: "must be >= 0.0",
		})
	}

	if config.MinHoldDays < 0 || config.MinHoldDays > 365 {
		errors = append(errors, ValidationError{
			Field:   "min_hold_days",
			Message: "must be between 0 and 365",
		})
	}

	if config.SellCooldownDays < 0 || config.SellCooldownDays > 365 {
		errors = append(errors, ValidationError{
			Field:   "sell_cooldown_days",
			Message: "must be between 0 and 365",
		})
	}

	if config.MaxLossThreshold < -1.0 || config.MaxLossThreshold > 0.0 {
		errors = append(errors, ValidationError{
			Field:   "max_loss_threshold",
			Message: "must be between -1.0 and 0.0",
		})
	}

	if config.MaxSellPercentage < 0.01 || config.MaxSellPercentage > 1.0 {
		errors = append(errors, ValidationError{
			Field:   "max_sell_percentage",
			Message: "must be between 0.01 and 1.0",
		})
	}

	// Validate that at least one opportunity calculator is enabled
	enabledCalculators := config.GetEnabledCalculators()
	if len(enabledCalculators) == 0 {
		errors = append(errors, ValidationError{
			Field:   "opportunity_calculators",
			Message: "at least one opportunity calculator must be enabled",
		})
	}

	// NOTE: Patterns and generators are no longer validated - ExhaustiveGenerator always runs
	// NOTE: Filters validation is relaxed - filters are optional post-generation optimizations

	// Validate buy/sell permissions
	if !config.AllowBuy && !config.AllowSell {
		errors = append(errors, ValidationError{
			Field:   "allow_buy/allow_sell",
			Message: "at least one of allow_buy or allow_sell must be true",
		})
	}

	if len(errors) > 0 {
		return errors
	}

	return nil
}

// ValidateQuick performs basic validation without deep checks.
// Useful for quick validation during loading.
func (v *Validator) ValidateQuick(config *domain.PlannerConfiguration) error {
	var errors ValidationErrors

	if config.Name == "" {
		errors = append(errors, ValidationError{
			Field:   "name",
			Message: "name is required",
		})
	}

	if config.MaxDepth <= 0 {
		errors = append(errors, ValidationError{
			Field:   "max_depth",
			Message: "must be greater than 0",
		})
	}

	if len(errors) > 0 {
		return errors
	}

	return nil
}

// ValidateParams validates module-specific parameters.
func (v *Validator) ValidateParams(moduleName string, params map[string]interface{}) error {
	var errors ValidationErrors

	// Define validation rules for common parameter types
	validators := map[string]func(interface{}) error{
		"threshold": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f < 0.0 || f > 1.0 {
					return fmt.Errorf("must be between 0.0 and 1.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
		"weight": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f < 0.0 || f > 1.0 {
					return fmt.Errorf("must be between 0.0 and 1.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
		"min_value": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f < 0.0 {
					return fmt.Errorf("must be >= 0.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
		"max_value": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f < 0.0 {
					return fmt.Errorf("must be >= 0.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
		"count": func(val interface{}) error {
			if i, ok := val.(int); ok {
				if i <= 0 {
					return fmt.Errorf("must be > 0")
				}
				return nil
			}
			if f, ok := val.(float64); ok {
				if f <= 0 {
					return fmt.Errorf("must be > 0")
				}
				return nil
			}
			return fmt.Errorf("must be an integer")
		},
		"percentage": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f < 0.0 || f > 100.0 {
					return fmt.Errorf("must be between 0.0 and 100.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
		"factor": func(val interface{}) error {
			if f, ok := val.(float64); ok {
				if f <= 0.0 {
					return fmt.Errorf("must be > 0.0")
				}
				return nil
			}
			return fmt.Errorf("must be a number")
		},
	}

	// Module-specific parameter requirements
	requiredParams := getRequiredParams(moduleName)

	// Check required parameters
	for paramName, paramType := range requiredParams {
		value, exists := params[paramName]
		if !exists {
			errors = append(errors, ValidationError{
				Field:   fmt.Sprintf("%s.%s", moduleName, paramName),
				Message: "required parameter is missing",
			})
			continue
		}

		// Validate parameter type and value
		if validator, ok := validators[paramType]; ok {
			if err := validator(value); err != nil {
				errors = append(errors, ValidationError{
					Field:   fmt.Sprintf("%s.%s", moduleName, paramName),
					Message: err.Error(),
				})
			}
		}
	}

	// Validate cross-parameter constraints
	if err := validateCrossConstraints(moduleName, params); err != nil {
		errors = append(errors, ValidationError{
			Field:   moduleName,
			Message: err.Error(),
		})
	}

	if len(errors) > 0 {
		return errors
	}

	return nil
}

// getRequiredParams returns required parameters for each module type.
// NOTE: Pattern and generator entries kept for backwards compatibility with
// any code that calls ValidateParams, but these modules no longer exist.
func getRequiredParams(moduleName string) map[string]string {
	// Define required parameters per module (paramName -> paramType)
	paramMap := map[string]map[string]string{
		// Opportunity Calculators
		"profit_taking": {
			"gain_threshold": "threshold",
			"windfall_score": "threshold",
			"min_hold_days":  "count",
			"sell_cooldown":  "count",
		},
		"averaging_down": {
			"loss_threshold":    "threshold",
			"max_loss_allowed":  "threshold",
			"buy_cooldown_days": "count",
		},
		"opportunity_buys": {
			"scoring_weight":    "weight",
			"max_opportunities": "count",
		},
		"rebalance_sells": {
			"over_weight_threshold": "threshold",
		},
		"rebalance_buys": {
			"under_weight_threshold": "threshold",
		},
		"weight_based": {
			"target_weight_tolerance": "threshold",
		},

		// Post-generation Filters
		"correlation_aware": {
			"correlation_threshold": "threshold",
		},
		"diversity": {
			"diversity_threshold": "threshold",
		},

		// Legacy entries for backwards compatibility (no longer used)
		"combinatorial": {
			"max_combinations": "count",
		},
		"enhanced_combinatorial": {
			"max_combinations":  "count",
			"pruning_threshold": "threshold",
		},
		"constraint_relaxation": {
			"relaxation_factor": "factor",
		},
		"market_regime": {
			"regime_threshold": "threshold",
		},
		"recently_traded": {
			"cooldown_days": "count",
		},
	}

	if params, ok := paramMap[moduleName]; ok {
		return params
	}

	// Unknown module - no required params (accept any)
	return map[string]string{}
}

// validateCrossConstraints validates cross-parameter constraints.
func validateCrossConstraints(moduleName string, params map[string]interface{}) error {
	// Check module-specific cross-parameter constraints
	switch moduleName {
	case "profit_taking":
		// Ensure min_hold_days < sell_cooldown
		if minHold, ok1 := params["min_hold_days"].(float64); ok1 {
			if cooldown, ok2 := params["sell_cooldown"].(float64); ok2 {
				if minHold >= cooldown {
					return fmt.Errorf("min_hold_days must be less than sell_cooldown")
				}
			}
		}

	case "averaging_down":
		// Ensure loss_threshold <= max_loss_allowed
		if lossThresh, ok1 := params["loss_threshold"].(float64); ok1 {
			if maxLoss, ok2 := params["max_loss_allowed"].(float64); ok2 {
				if lossThresh > maxLoss {
					return fmt.Errorf("loss_threshold cannot exceed max_loss_allowed")
				}
			}
		}

	case "enhanced_combinatorial":
		// Ensure pruning_threshold is reasonable for max_combinations
		if maxComb, ok1 := params["max_combinations"].(float64); ok1 {
			if pruning, ok2 := params["pruning_threshold"].(float64); ok2 {
				if pruning > 0.9 && maxComb > 1000 {
					return fmt.Errorf("high pruning_threshold with large max_combinations may filter too aggressively")
				}
			}
		}
	}

	return nil
}
