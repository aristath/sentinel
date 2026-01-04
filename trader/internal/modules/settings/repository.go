package settings

import (
	"database/sql"
	"fmt"
	"strconv"
	"time"

	"github.com/rs/zerolog"
)

// Repository handles settings database operations
// Faithful translation from Python: app/repositories/settings.py -> SettingsRepository
// Database: config.db (settings table)
type Repository struct {
	db  *sql.DB // config.db
	log zerolog.Logger
}

// NewRepository creates a new settings repository
// db parameter should be config.db connection
func NewRepository(db *sql.DB, log zerolog.Logger) *Repository {
	return &Repository{
		db:  db,
		log: log.With().Str("repository", "settings").Logger(),
	}
}

// Get retrieves a setting value by key
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

// Set sets a setting value
func (r *Repository) Set(key string, value string, description *string) error {
	now := time.Now().Format(time.RFC3339)

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

// GetAll retrieves all settings as a map
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

// GetFloat retrieves a setting value as float
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

// SetFloat sets a setting value as float
func (r *Repository) SetFloat(key string, value float64) error {
	return r.Set(key, fmt.Sprintf("%f", value), nil)
}

// GetInt retrieves a setting value as integer
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

// SetInt sets a setting value as integer
func (r *Repository) SetInt(key string, value int) error {
	return r.Set(key, fmt.Sprintf("%d", value), nil)
}

// GetBool retrieves a setting value as boolean
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

// SetBool sets a setting value as boolean
func (r *Repository) SetBool(key string, value bool) error {
	strVal := "false"
	if value {
		strVal = "true"
	}
	return r.Set(key, strVal, nil)
}

// Delete deletes a setting
func (r *Repository) Delete(key string) error {
	_, err := r.db.Exec("DELETE FROM settings WHERE key = ?", key)
	if err != nil {
		return fmt.Errorf("failed to delete setting %s: %w", key, err)
	}
	return nil
}
