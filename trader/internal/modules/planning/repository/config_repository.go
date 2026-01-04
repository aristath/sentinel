package repository

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/planning/config"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ConfigRepository handles database operations for planner configurations.
// Database: agents.db (agent_configs, config_history tables)
type ConfigRepository struct {
	db     *database.DB // agents.db
	loader *config.Loader
	log    zerolog.Logger
}

// NewConfigRepository creates a new config repository.
// db parameter should be agents.db connection
func NewConfigRepository(db *database.DB, loader *config.Loader, log zerolog.Logger) *ConfigRepository {
	return &ConfigRepository{
		db:     db,
		loader: loader,
		log:    log.With().Str("component", "config_repository").Logger(),
	}
}

// ConfigRecord represents a configuration in the database.
type ConfigRecord struct {
	ID          int64
	Name        string
	Description string
	ConfigData  string  // TOML string
	BucketID    *string // Associated bucket (nullable for templates)
	IsDefault   bool
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// ConfigHistoryRecord represents a configuration history entry in the database.
type ConfigHistoryRecord struct {
	ID         int64
	ConfigID   int64
	ConfigData string // TOML string
	ChangedBy  string
	ChangeNote string
	CreatedAt  time.Time
}

// CreateConfig creates a new configuration.
func (r *ConfigRepository) CreateConfig(
	cfg *domain.PlannerConfiguration,
	isDefault bool,
) (int64, error) {
	// Convert config to TOML string
	tomlData, err := r.loader.ToString(cfg)
	if err != nil {
		return 0, fmt.Errorf("failed to convert config to TOML: %w", err)
	}

	now := time.Now()

	// If setting as default, unset any existing default
	if isDefault {
		if err := r.unsetDefaultConfig(); err != nil {
			return 0, fmt.Errorf("failed to unset existing default: %w", err)
		}
	}

	// Insert config
	result, err := r.db.Exec(`
		INSERT INTO planner_configs (name, description, config_data, bucket_id, is_default, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, cfg.Name, cfg.Description, tomlData, cfg.BucketID, isDefault, now, now)

	if err != nil {
		return 0, fmt.Errorf("failed to insert config: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return 0, fmt.Errorf("failed to get last insert id: %w", err)
	}

	r.log.Info().
		Int64("id", id).
		Str("name", cfg.Name).
		Bool("is_default", isDefault).
		Msg("Created config")

	// Create initial history entry
	if err := r.createHistoryEntry(id, tomlData, "system", "Initial configuration created"); err != nil {
		r.log.Warn().Err(err).Msg("Failed to create history entry")
	}

	return id, nil
}

// GetConfig retrieves a configuration by ID.
func (r *ConfigRepository) GetConfig(id int64) (*domain.PlannerConfiguration, error) {
	var record ConfigRecord
	err := r.db.QueryRow(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		WHERE id = ?
	`, id).Scan(
		&record.ID,
		&record.Name,
		&record.Description,
		&record.ConfigData,
		&record.BucketID,
		&record.IsDefault,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get config: %w", err)
	}

	// Parse TOML
	cfg, err := r.loader.LoadFromString(record.ConfigData)
	if err != nil {
		return nil, fmt.Errorf("failed to parse config TOML: %w", err)
	}

	return cfg, nil
}

// GetConfigByName retrieves a configuration by name.
func (r *ConfigRepository) GetConfigByName(name string) (*domain.PlannerConfiguration, error) {
	var record ConfigRecord
	err := r.db.QueryRow(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		WHERE name = ?
	`, name).Scan(
		&record.ID,
		&record.Name,
		&record.Description,
		&record.ConfigData,
		&record.BucketID,
		&record.IsDefault,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get config by name: %w", err)
	}

	// Parse TOML
	cfg, err := r.loader.LoadFromString(record.ConfigData)
	if err != nil {
		return nil, fmt.Errorf("failed to parse config TOML: %w", err)
	}

	return cfg, nil
}

// GetDefaultConfig retrieves the default configuration.
func (r *ConfigRepository) GetDefaultConfig() (*domain.PlannerConfiguration, error) {
	var record ConfigRecord
	err := r.db.QueryRow(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		WHERE is_default = 1
		LIMIT 1
	`).Scan(
		&record.ID,
		&record.Name,
		&record.Description,
		&record.ConfigData,
		&record.BucketID,
		&record.IsDefault,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get default config: %w", err)
	}

	// Parse TOML
	cfg, err := r.loader.LoadFromString(record.ConfigData)
	if err != nil {
		return nil, fmt.Errorf("failed to parse config TOML: %w", err)
	}

	return cfg, nil
}

// GetByBucket retrieves the configuration for a specific bucket.
func (r *ConfigRepository) GetByBucket(bucketID string) (*domain.PlannerConfiguration, error) {
	var record ConfigRecord
	err := r.db.QueryRow(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		WHERE bucket_id = ?
		LIMIT 1
	`).Scan(
		&record.ID,
		&record.Name,
		&record.Description,
		&record.ConfigData,
		&record.BucketID,
		&record.IsDefault,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get config by bucket: %w", err)
	}

	// Parse TOML
	cfg, err := r.loader.LoadFromString(record.ConfigData)
	if err != nil {
		return nil, fmt.Errorf("failed to parse config TOML: %w", err)
	}

	return cfg, nil
}

// UpdateConfig updates an existing configuration.
func (r *ConfigRepository) UpdateConfig(
	id int64,
	cfg *domain.PlannerConfiguration,
	changedBy string,
	changeNote string,
) error {
	// Get existing config for history
	existingRecord, err := r.getConfigRecord(id)
	if err != nil {
		return fmt.Errorf("failed to get existing config: %w", err)
	}
	if existingRecord == nil {
		return fmt.Errorf("config not found")
	}

	// Convert new config to TOML string
	tomlData, err := r.loader.ToString(cfg)
	if err != nil {
		return fmt.Errorf("failed to convert config to TOML: %w", err)
	}

	now := time.Now()

	// Update config
	_, err = r.db.Exec(`
		UPDATE planner_configs
		SET name = ?, description = ?, config_data = ?, bucket_id = ?, updated_at = ?
		WHERE id = ?
	`, cfg.Name, cfg.Description, tomlData, cfg.BucketID, now, id)

	if err != nil {
		return fmt.Errorf("failed to update config: %w", err)
	}

	r.log.Info().
		Int64("id", id).
		Str("name", cfg.Name).
		Msg("Updated config")

	// Create history entry
	if err := r.createHistoryEntry(id, tomlData, changedBy, changeNote); err != nil {
		r.log.Warn().Err(err).Msg("Failed to create history entry")
	}

	return nil
}

// DeleteConfig deletes a configuration.
func (r *ConfigRepository) DeleteConfig(id int64) error {
	// Check if it's the default config
	var isDefault bool
	err := r.db.QueryRow(`SELECT is_default FROM planner_configs WHERE id = ?`, id).Scan(&isDefault)
	if err == sql.ErrNoRows {
		return fmt.Errorf("config not found")
	}
	if err != nil {
		return fmt.Errorf("failed to check config: %w", err)
	}

	if isDefault {
		return fmt.Errorf("cannot delete default config")
	}

	// Delete history entries first
	_, err = r.db.Exec(`DELETE FROM planner_config_history WHERE config_id = ?`, id)
	if err != nil {
		return fmt.Errorf("failed to delete config history: %w", err)
	}

	// Delete config
	_, err = r.db.Exec(`DELETE FROM planner_configs WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("failed to delete config: %w", err)
	}

	r.log.Info().
		Int64("id", id).
		Msg("Deleted config")

	return nil
}

// ListConfigs retrieves all configurations.
func (r *ConfigRepository) ListConfigs() ([]ConfigRecord, error) {
	rows, err := r.db.Query(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		ORDER BY is_default DESC, name ASC
	`)

	if err != nil {
		return nil, fmt.Errorf("failed to list configs: %w", err)
	}
	defer rows.Close()

	var records []ConfigRecord
	for rows.Next() {
		var record ConfigRecord
		if err := rows.Scan(
			&record.ID,
			&record.Name,
			&record.Description,
			&record.ConfigData,
			&record.BucketID,
			&record.IsDefault,
			&record.CreatedAt,
			&record.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan config: %w", err)
		}
		records = append(records, record)
	}

	return records, nil
}

// SetDefaultConfig sets a configuration as the default.
func (r *ConfigRepository) SetDefaultConfig(id int64) error {
	// Unset existing default
	if err := r.unsetDefaultConfig(); err != nil {
		return fmt.Errorf("failed to unset existing default: %w", err)
	}

	// Set new default
	_, err := r.db.Exec(`UPDATE planner_configs SET is_default = 1 WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("failed to set default config: %w", err)
	}

	r.log.Info().
		Int64("id", id).
		Msg("Set default config")

	return nil
}

// GetConfigHistory retrieves the history for a configuration.
func (r *ConfigRepository) GetConfigHistory(configID int64, limit int) ([]ConfigHistoryRecord, error) {
	query := `
		SELECT id, config_id, config_data, changed_by, change_note, created_at
		FROM planner_config_history
		WHERE config_id = ?
		ORDER BY created_at DESC
	`
	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.Query(query, configID)
	if err != nil {
		return nil, fmt.Errorf("failed to get config history: %w", err)
	}
	defer rows.Close()

	var records []ConfigHistoryRecord
	for rows.Next() {
		var record ConfigHistoryRecord
		if err := rows.Scan(
			&record.ID,
			&record.ConfigID,
			&record.ConfigData,
			&record.ChangedBy,
			&record.ChangeNote,
			&record.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan history: %w", err)
		}
		records = append(records, record)
	}

	return records, nil
}

// Helper methods

func (r *ConfigRepository) unsetDefaultConfig() error {
	_, err := r.db.Exec(`UPDATE planner_configs SET is_default = 0 WHERE is_default = 1`)
	return err
}

func (r *ConfigRepository) getConfigRecord(id int64) (*ConfigRecord, error) {
	var record ConfigRecord
	err := r.db.QueryRow(`
		SELECT id, name, description, config_data, bucket_id, is_default, created_at, updated_at
		FROM planner_configs
		WHERE id = ?
	`, id).Scan(
		&record.ID,
		&record.Name,
		&record.Description,
		&record.ConfigData,
		&record.BucketID,
		&record.IsDefault,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	return &record, nil
}

func (r *ConfigRepository) createHistoryEntry(
	configID int64,
	configData string,
	changedBy string,
	changeNote string,
) error {
	_, err := r.db.Exec(`
		INSERT INTO planner_config_history (config_id, config_data, changed_by, change_note, created_at)
		VALUES (?, ?, ?, ?, ?)
	`, configID, configData, changedBy, changeNote, time.Now())

	if err != nil {
		return fmt.Errorf("failed to create history entry: %w", err)
	}

	return nil
}
