// Package settings provides repository implementations for managing application settings.
// This file implements the Repository, which handles settings stored in config.db.
// Settings are key-value pairs that configure various aspects of the application
// (trading mode, API credentials, display settings, job schedules, etc.).
package settings

import (
	"database/sql"
	"fmt"
	"strconv"
	"time"

	"github.com/rs/zerolog"
)

// Repository handles settings database operations.
// Settings are stored in config.db and take precedence over environment variables.
// This allows runtime configuration changes without restarting the application.
//
// Settings are stored as strings and converted to appropriate types (int, float, bool)
// when retrieved. The repository provides type-safe getters and setters for convenience.
//
// Faithful translation from Python: app/repositories/settings.py -> SettingsRepository
// Database: config.db (settings table)
type Repository struct {
	db  *sql.DB        // config.db - settings table
	log zerolog.Logger // Structured logger
}

// NewRepository creates a new settings repository.
// The repository manages application settings stored in the settings table.
//
// Parameters:
//   - db: Database connection to config.db
//   - log: Structured logger
//
// Returns:
//   - *Repository: Initialized repository instance
func NewRepository(db *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		db:  db,
		log: log.With().Str("repository", "settings").Logger(),
	}
}

// Get retrieves a setting value by key.
// Returns nil if the setting doesn't exist (not an error).
//
// Parameters:
//   - key: Setting key (e.g., "trading_mode", "tradernet_api_key")
//
// Returns:
//   - *string: Setting value if found, nil if not found
//   - error: Error if query fails
func (r *Repository) Get(key string) (*string, error) {
	var value string
	err := r.db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get setting %s: %w", key, err)
	}
	return &value, nil
}

// Set sets a setting value.
// Uses INSERT OR REPLACE to handle both insert and update in a single operation.
// The description is optional and can be used to document the setting's purpose.
//
// Parameters:
//   - key: Setting key
//   - value: Setting value (stored as string)
//   - description: Optional description of the setting
//
// Returns:
//   - error: Error if database operation fails
func (r *Repository) Set(key string, value string, description *string) error {
	now := time.Now().Unix()

	if description != nil {
		_, err := r.db.Exec(`
			INSERT INTO settings (key, value, description, updated_at)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(key) DO UPDATE SET
				value = excluded.value,
				description = excluded.description,
				updated_at = excluded.updated_at
		`, key, value, *description, now)
		return err
	}

	_, err := r.db.Exec(`
		INSERT INTO settings (key, value, updated_at)
		VALUES (?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET
			value = excluded.value,
			updated_at = excluded.updated_at
	`, key, value, now)
	return err
}

// GetAll retrieves all settings as a map.
// This is useful for bulk loading settings or displaying all configuration.
//
// Returns:
//   - map[string]string: Map of setting keys to values
//   - error: Error if query fails
func (r *Repository) GetAll() (map[string]string, error) {
	rows, err := r.db.Query("SELECT key, value FROM settings")
	if err != nil {
		return nil, fmt.Errorf("failed to get all settings: %w", err)
	}
	defer rows.Close()

	result := make(map[string]string)
	for rows.Next() {
		var key, value string
		if err := rows.Scan(&key, &value); err != nil {
			r.log.Warn().Err(err).Msg("Failed to scan setting row")
			continue
		}
		result[key] = value
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating settings: %w", err)
	}

	return result, nil
}

// GetFloat retrieves a setting value as float64.
// Returns defaultValue if the setting doesn't exist or parsing fails.
// This provides type-safe access to numeric settings.
//
// Parameters:
//   - key: Setting key
//   - defaultValue: Default value to return if setting not found or invalid
//
// Returns:
//   - float64: Setting value as float, or defaultValue
//   - error: Error if query fails (parsing errors are logged but not returned)
func (r *Repository) GetFloat(key string, defaultValue float64) (float64, error) {
	value, err := r.Get(key)
	if err != nil {
		return defaultValue, err
	}
	if value == nil {
		return defaultValue, nil
	}

	floatVal, err := strconv.ParseFloat(*value, 64)
	if err != nil {
		r.log.Warn().
			Err(err).
			Str("key", key).
			Str("value", *value).
			Msg("Failed to parse float setting")
		return defaultValue, nil
	}

	return floatVal, nil
}

// SetFloat sets a setting value as float64.
// The value is converted to a string for storage.
//
// Parameters:
//   - key: Setting key
//   - value: Float value to store
//
// Returns:
//   - error: Error if database operation fails
func (r *Repository) SetFloat(key string, value float64) error {
	return r.Set(key, fmt.Sprintf("%f", value), nil)
}

// GetInt retrieves a setting value as integer.
// Returns defaultValue if the setting doesn't exist or parsing fails.
// This provides type-safe access to integer settings.
// Handles "12.0" strings from database by parsing via float first.
//
// Parameters:
//   - key: Setting key
//   - defaultValue: Default value to return if setting not found or invalid
//
// Returns:
//   - int: Setting value as int, or defaultValue
//   - error: Error if query fails (parsing errors are logged but not returned)
func (r *Repository) GetInt(key string, defaultValue int) (int, error) {
	value, err := r.Get(key)
	if err != nil {
		return defaultValue, err
	}
	if value == nil {
		return defaultValue, nil
	}

	// Parse via float first to handle "12.0" strings from database
	floatVal, err := strconv.ParseFloat(*value, 64)
	if err != nil {
		r.log.Warn().
			Err(err).
			Str("key", key).
			Str("value", *value).
			Msg("Failed to parse int setting")
		return defaultValue, nil
	}

	return int(floatVal), nil
}

// SetInt sets a setting value as integer.
// The value is converted to a string for storage.
//
// Parameters:
//   - key: Setting key
//   - value: Integer value to store
//
// Returns:
//   - error: Error if database operation fails
func (r *Repository) SetInt(key string, value int) error {
	return r.Set(key, fmt.Sprintf("%d", value), nil)
}

// GetBool retrieves a setting value as boolean.
// Returns defaultValue if the setting doesn't exist.
// Recognizes various truthy values: "true", "1", "yes", "on" (case-insensitive).
// All other values are treated as false.
//
// Parameters:
//   - key: Setting key
//   - defaultValue: Default value to return if setting not found
//
// Returns:
//   - bool: Setting value as bool, or defaultValue
//   - error: Error if query fails
func (r *Repository) GetBool(key string, defaultValue bool) (bool, error) {
	value, err := r.Get(key)
	if err != nil {
		return defaultValue, err
	}
	if value == nil {
		return defaultValue, nil
	}

	// Check for various truthy values
	lower := *value
	if lower == "true" || lower == "1" || lower == "yes" || lower == "on" {
		return true, nil
	}

	return false, nil
}

// SetBool sets a setting value as boolean.
// The value is stored as "true" or "false" string.
//
// Parameters:
//   - key: Setting key
//   - value: Boolean value to store
//
// Returns:
//   - error: Error if database operation fails
func (r *Repository) SetBool(key string, value bool) error {
	strVal := "false"
	if value {
		strVal = "true"
	}
	return r.Set(key, strVal, nil)
}

// Delete deletes a setting.
// This operation is idempotent - it does not error if the setting doesn't exist.
// Useful for removing settings that are no longer needed.
//
// Parameters:
//   - key: Setting key to delete
//
// Returns:
//   - error: Error if database operation fails
func (r *Repository) Delete(key string) error {
	_, err := r.db.Exec("DELETE FROM settings WHERE key = ?", key)
	if err != nil {
		return fmt.Errorf("failed to delete setting %s: %w", key, err)
	}
	return nil
}
