// Package repository provides planning data repository functionality.
package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ConfigRepository handles database operations for planner configurations.
// Database: config.db (planner_settings table - single row)
type ConfigRepository struct {
	db  *database.DB // config.db
	log zerolog.Logger
}

// NewConfigRepository creates a new config repository.
// db parameter should be config.db connection
func NewConfigRepository(db *database.DB, log zerolog.Logger) *ConfigRepository {
	return &ConfigRepository{
		db:  db,
		log: log.With().Str("component", "config_repository").Logger(),
	}
}

// ConfigRecord represents a configuration record (for backward compatibility).
// Note: This is simplified - we only have one config now.
type ConfigRecord struct {
	ID          int64
	Name        string
	Description string
	IsDefault   bool // Always true (only one config exists)
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// GetDefaultConfig retrieves the planner configuration (single config exists).
func (r *ConfigRepository) GetDefaultConfig() (*domain.PlannerConfiguration, error) {
	return r.getSettings()
}

// GetSettings retrieves the planner settings (single config exists).
func (r *ConfigRepository) getSettings() (*domain.PlannerConfiguration, error) {
	var cfg domain.PlannerConfiguration

	err := r.db.QueryRow(`
		SELECT
			name, description,
			enable_batch_generation,
			max_depth, max_opportunities_per_category,
			enable_diverse_selection, diversity_weight,
			transaction_cost_fixed, transaction_cost_percent,
			allow_sell, allow_buy,
			min_hold_days, sell_cooldown_days, max_loss_threshold, max_sell_percentage,
			optimizer_blend,
			enable_profit_taking_calc,
			enable_averaging_down_calc,
			enable_opportunity_buys_calc,
			enable_rebalance_sells_calc,
			enable_rebalance_buys_calc,
			enable_weight_based_calc,
			enable_direct_buy_pattern,
			enable_profit_taking_pattern,
			enable_rebalance_pattern,
			enable_averaging_down_pattern,
			enable_single_best_pattern,
			enable_multi_sell_pattern,
			enable_mixed_strategy_pattern,
			enable_opportunity_first_pattern,
			enable_deep_rebalance_pattern,
			enable_cash_generation_pattern,
			enable_cost_optimized_pattern,
			enable_adaptive_pattern,
			enable_market_regime_pattern,
			enable_combinatorial_generator,
			enable_enhanced_combinatorial_generator,
			enable_constraint_relaxation_generator,
			enable_correlation_aware_filter,
			enable_diversity_filter,
			enable_eligibility_filter,
			enable_recently_traded_filter,
			enable_tag_filtering
		FROM planner_settings
		WHERE id = 'main'
	`).Scan(
		&cfg.Name, &cfg.Description,
		&cfg.EnableBatchGeneration,
		&cfg.MaxDepth, &cfg.MaxOpportunitiesPerCategory,
		&cfg.EnableDiverseSelection, &cfg.DiversityWeight,
		&cfg.TransactionCostFixed, &cfg.TransactionCostPercent,
		&cfg.AllowSell, &cfg.AllowBuy,
		&cfg.MinHoldDays, &cfg.SellCooldownDays, &cfg.MaxLossThreshold, &cfg.MaxSellPercentage,
		&cfg.OptimizerBlend,
		&cfg.EnableProfitTakingCalc,
		&cfg.EnableAveragingDownCalc,
		&cfg.EnableOpportunityBuysCalc,
		&cfg.EnableRebalanceSellsCalc,
		&cfg.EnableRebalanceBuysCalc,
		&cfg.EnableWeightBasedCalc,
		&cfg.EnableDirectBuyPattern,
		&cfg.EnableProfitTakingPattern,
		&cfg.EnableRebalancePattern,
		&cfg.EnableAveragingDownPattern,
		&cfg.EnableSingleBestPattern,
		&cfg.EnableMultiSellPattern,
		&cfg.EnableMixedStrategyPattern,
		&cfg.EnableOpportunityFirstPattern,
		&cfg.EnableDeepRebalancePattern,
		&cfg.EnableCashGenerationPattern,
		&cfg.EnableCostOptimizedPattern,
		&cfg.EnableAdaptivePattern,
		&cfg.EnableMarketRegimePattern,
		&cfg.EnableCombinatorialGenerator,
		&cfg.EnableEnhancedCombinatorialGenerator,
		&cfg.EnableConstraintRelaxationGenerator,
		&cfg.EnableCorrelationAwareFilter,
		&cfg.EnableDiversityFilter,
		&cfg.EnableEligibilityFilter,
		&cfg.EnableRecentlyTradedFilter,
		&cfg.EnableTagFiltering,
	)

	if err == sql.ErrNoRows {
		// No config exists, return defaults
		r.log.Debug().Msg("No planner settings found in database, returning defaults")
		return domain.NewDefaultConfiguration(), nil
	}
	if err != nil {
		// Log detailed error information for debugging
		r.log.Error().
			Err(err).
			Str("error_type", fmt.Sprintf("%T", err)).
			Msg("Failed to query planner settings from database")
		return nil, fmt.Errorf("failed to get planner settings: %w", err)
	}

	r.log.Debug().Str("name", cfg.Name).Msg("Successfully retrieved planner settings from database")
	return &cfg, nil
}

// UpdateSettings updates the planner settings (single config exists).
func (r *ConfigRepository) updateSettings(cfg *domain.PlannerConfiguration) error {
	now := time.Now().Unix()

	_, err := r.db.Exec(`
		UPDATE planner_settings SET
			name = ?,
			description = ?,
			enable_batch_generation = ?,
			max_depth = ?,
			max_opportunities_per_category = ?,
			enable_diverse_selection = ?,
			diversity_weight = ?,
			transaction_cost_fixed = ?,
			transaction_cost_percent = ?,
			allow_sell = ?,
			allow_buy = ?,
			min_hold_days = ?,
			sell_cooldown_days = ?,
			max_loss_threshold = ?,
			max_sell_percentage = ?,
			optimizer_blend = ?,
			enable_profit_taking_calc = ?,
			enable_averaging_down_calc = ?,
			enable_opportunity_buys_calc = ?,
			enable_rebalance_sells_calc = ?,
			enable_rebalance_buys_calc = ?,
			enable_weight_based_calc = ?,
			enable_direct_buy_pattern = ?,
			enable_profit_taking_pattern = ?,
			enable_rebalance_pattern = ?,
			enable_averaging_down_pattern = ?,
			enable_single_best_pattern = ?,
			enable_multi_sell_pattern = ?,
			enable_mixed_strategy_pattern = ?,
			enable_opportunity_first_pattern = ?,
			enable_deep_rebalance_pattern = ?,
			enable_cash_generation_pattern = ?,
			enable_cost_optimized_pattern = ?,
			enable_adaptive_pattern = ?,
			enable_market_regime_pattern = ?,
			enable_combinatorial_generator = ?,
			enable_enhanced_combinatorial_generator = ?,
			enable_constraint_relaxation_generator = ?,
			enable_correlation_aware_filter = ?,
			enable_diversity_filter = ?,
			enable_eligibility_filter = ?,
			enable_recently_traded_filter = ?,
			enable_tag_filtering = ?,
			updated_at = ?
		WHERE id = 'main'
	`,
		cfg.Name, cfg.Description,
		cfg.EnableBatchGeneration,
		cfg.MaxDepth, cfg.MaxOpportunitiesPerCategory,
		cfg.EnableDiverseSelection, cfg.DiversityWeight,
		cfg.TransactionCostFixed, cfg.TransactionCostPercent,
		cfg.AllowSell, cfg.AllowBuy,
		cfg.MinHoldDays, cfg.SellCooldownDays, cfg.MaxLossThreshold, cfg.MaxSellPercentage,
		cfg.OptimizerBlend,
		cfg.EnableProfitTakingCalc,
		cfg.EnableAveragingDownCalc,
		cfg.EnableOpportunityBuysCalc,
		cfg.EnableRebalanceSellsCalc,
		cfg.EnableRebalanceBuysCalc,
		cfg.EnableWeightBasedCalc,
		cfg.EnableDirectBuyPattern,
		cfg.EnableProfitTakingPattern,
		cfg.EnableRebalancePattern,
		cfg.EnableAveragingDownPattern,
		cfg.EnableSingleBestPattern,
		cfg.EnableMultiSellPattern,
		cfg.EnableMixedStrategyPattern,
		cfg.EnableOpportunityFirstPattern,
		cfg.EnableDeepRebalancePattern,
		cfg.EnableCashGenerationPattern,
		cfg.EnableCostOptimizedPattern,
		cfg.EnableAdaptivePattern,
		cfg.EnableMarketRegimePattern,
		cfg.EnableCombinatorialGenerator,
		cfg.EnableEnhancedCombinatorialGenerator,
		cfg.EnableConstraintRelaxationGenerator,
		cfg.EnableCorrelationAwareFilter,
		cfg.EnableDiversityFilter,
		cfg.EnableEligibilityFilter,
		cfg.EnableRecentlyTradedFilter,
		cfg.EnableTagFiltering,
		now,
	)

	if err != nil {
		return fmt.Errorf("failed to update planner settings: %w", err)
	}

	r.log.Info().
		Str("name", cfg.Name).
		Msg("Updated planner settings")

	return nil
}

// Backward compatibility methods (simplified implementations)

// GetConfig retrieves a configuration by ID (always returns the single config).
func (r *ConfigRepository) GetConfig(id int64) (*domain.PlannerConfiguration, error) {
	return r.getSettings()
}

// GetConfigByName retrieves a configuration by name (always returns the single config).
func (r *ConfigRepository) GetConfigByName(name string) (*domain.PlannerConfiguration, error) {
	return r.getSettings()
}

// UpdateConfig updates the planner configuration (single config exists).
func (r *ConfigRepository) UpdateConfig(
	id int64,
	cfg *domain.PlannerConfiguration,
	changedBy string,
	changeNote string,
) error {
	// Ignore id, changedBy, changeNote - single config exists, no history
	return r.updateSettings(cfg)
}

// CreateConfig creates a new configuration (actually updates the single config).
func (r *ConfigRepository) CreateConfig(
	cfg *domain.PlannerConfiguration,
	isDefault bool,
) (int64, error) {
	// Ignore isDefault - single config exists
	if err := r.updateSettings(cfg); err != nil {
		return 0, err
	}
	// Return dummy ID (1) for backward compatibility
	return 1, nil
}

// ListConfigs returns a list of configurations (always returns single config).
func (r *ConfigRepository) ListConfigs() ([]ConfigRecord, error) {
	cfg, err := r.getSettings()
	if err != nil {
		return nil, err
	}

	// Return as single record for backward compatibility
	record := ConfigRecord{
		ID:          1,
		Name:        cfg.Name,
		Description: cfg.Description,
		IsDefault:   true,
		CreatedAt:   time.Now(), // Not stored, use current time
		UpdatedAt:   time.Now(), // Not stored, use current time
	}

	return []ConfigRecord{record}, nil
}

// DeleteConfig deletes a configuration (resets to defaults).
func (r *ConfigRepository) DeleteConfig(id int64) error {
	// Reset to defaults
	defaultCfg := domain.NewDefaultConfiguration()
	return r.updateSettings(defaultCfg)
}

// SetDefaultConfig sets a configuration as default (no-op, single config exists).
func (r *ConfigRepository) SetDefaultConfig(id int64) error {
	// No-op: single config is always default
	return nil
}

// GetConfigHistory returns configuration history (empty, no history table).
func (r *ConfigRepository) GetConfigHistory(configID int64, limit int) ([]ConfigHistoryRecord, error) {
	// No history in simplified version
	return []ConfigHistoryRecord{}, nil
}

// ConfigHistoryRecord represents a configuration history entry (for backward compatibility).
// Note: History is removed in simplified version.
type ConfigHistoryRecord struct {
	ID         int64
	ConfigID   int64
	ConfigData string
	ChangedBy  string
	ChangeNote string
	CreatedAt  time.Time
}
