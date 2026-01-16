// Package repository provides planning data repository functionality.
// This file implements the ConfigRepository, which handles planner configuration
// stored in config.db. The planner configuration is a single-row table that stores
// all planner settings (opportunity calculators, filters, transaction costs, etc.).
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
// The planner configuration is stored as a single row in planner_settings table (id = 'main').
// This simplified design avoids the complexity of multiple configurations and history tracking.
//
// Database: config.db (planner_settings table - single row)
type ConfigRepository struct {
	db  *database.DB // config.db - planner_settings table
	log zerolog.Logger
}

// NewConfigRepository creates a new config repository.
// The repository manages the single planner configuration stored in planner_settings.
//
// Parameters:
//   - db: Database connection to config.db
//   - log: Structured logger
//
// Returns:
//   - *ConfigRepository: Initialized repository instance
func NewConfigRepository(db *database.DB, log zerolog.Logger) *ConfigRepository {
	return &ConfigRepository{
		db:  db,
		log: log.With().Str("component", "config_repository").Logger(),
	}
}

// ConfigRecord represents a configuration record.
type ConfigRecord struct {
	ID          int64
	Name        string
	Description string
	IsDefault   bool // Always true (only one config exists)
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// GetDefaultConfig retrieves the planner configuration (single config exists).
// Since there's only one configuration, this always returns the same config.
// Returns default configuration if no config exists in database.
//
// Returns:
//   - *domain.PlannerConfiguration: Planner configuration (or defaults if not found)
//   - error: Error if query fails
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
			min_hold_days, sell_cooldown_days, max_loss_threshold, max_sell_percentage, averaging_down_percent,
			optimizer_blend, optimizer_target_return, min_cash_reserve,
			enable_profit_taking_calc,
			enable_averaging_down_calc,
			enable_opportunity_buys_calc,
			enable_rebalance_sells_calc,
			enable_rebalance_buys_calc,
			enable_weight_based_calc,
			enable_correlation_aware_filter,
			enable_diversity_filter,
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
		&cfg.MinHoldDays, &cfg.SellCooldownDays, &cfg.MaxLossThreshold, &cfg.MaxSellPercentage, &cfg.AveragingDownPercent,
		&cfg.OptimizerBlend, &cfg.OptimizerTargetReturn, &cfg.MinCashReserve,
		&cfg.EnableProfitTakingCalc,
		&cfg.EnableAveragingDownCalc,
		&cfg.EnableOpportunityBuysCalc,
		&cfg.EnableRebalanceSellsCalc,
		&cfg.EnableRebalanceBuysCalc,
		&cfg.EnableWeightBasedCalc,
		&cfg.EnableCorrelationAwareFilter,
		&cfg.EnableDiversityFilter,
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
			averaging_down_percent = ?,
			optimizer_blend = ?,
			optimizer_target_return = ?,
			min_cash_reserve = ?,
			enable_profit_taking_calc = ?,
			enable_averaging_down_calc = ?,
			enable_opportunity_buys_calc = ?,
			enable_rebalance_sells_calc = ?,
			enable_rebalance_buys_calc = ?,
			enable_weight_based_calc = ?,
			enable_correlation_aware_filter = ?,
			enable_diversity_filter = ?,
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
		cfg.MinHoldDays, cfg.SellCooldownDays, cfg.MaxLossThreshold, cfg.MaxSellPercentage, cfg.AveragingDownPercent,
		cfg.OptimizerBlend, cfg.OptimizerTargetReturn, cfg.MinCashReserve,
		cfg.EnableProfitTakingCalc,
		cfg.EnableAveragingDownCalc,
		cfg.EnableOpportunityBuysCalc,
		cfg.EnableRebalanceSellsCalc,
		cfg.EnableRebalanceBuysCalc,
		cfg.EnableWeightBasedCalc,
		cfg.EnableCorrelationAwareFilter,
		cfg.EnableDiversityFilter,
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

// GetConfig retrieves a configuration by ID (always returns the single config).
func (r *ConfigRepository) GetConfig(id int64) (*domain.PlannerConfiguration, error) {
	return r.getSettings()
}

// GetConfigByName retrieves a configuration by name (always returns the single config).
func (r *ConfigRepository) GetConfigByName(name string) (*domain.PlannerConfiguration, error) {
	return r.getSettings()
}

// UpdateConfig updates the planner configuration (single config exists).
// The id, changedBy, and changeNote parameters are ignored since there's only one config
// and no history tracking in the simplified version.
//
// Parameters:
//   - id: Configuration ID (ignored - single config exists)
//   - cfg: PlannerConfiguration object to save
//   - changedBy: User who made the change (ignored - no history)
//   - changeNote: Change description (ignored - no history)
//
// Returns:
//   - error: Error if database operation fails
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
	return 1, nil
}

// ListConfigs returns a list of configurations (always returns single config).
func (r *ConfigRepository) ListConfigs() ([]ConfigRecord, error) {
	cfg, err := r.getSettings()
	if err != nil {
		return nil, err
	}

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

// ConfigHistoryRecord represents a configuration history entry.
type ConfigHistoryRecord struct {
	ID         int64
	ConfigID   int64
	ConfigData string
	ChangedBy  string
	ChangeNote string
	CreatedAt  time.Time
}
