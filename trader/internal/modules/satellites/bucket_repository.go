package satellites

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// BucketRepository handles CRUD operations for buckets and satellite settings
// Faithful translation from Python: app/modules/satellites/database/bucket_repository.py
type BucketRepository struct {
	satellitesDB *sql.DB // satellites.db connection
	log          zerolog.Logger
}

// NewBucketRepository creates a new bucket repository
func NewBucketRepository(satellitesDB *sql.DB, log zerolog.Logger) *BucketRepository {
	return &BucketRepository{
		satellitesDB: satellitesDB,
		log:          log.With().Str("repository", "bucket").Logger(),
	}
}

// GetByID gets a bucket by ID
func (r *BucketRepository) GetByID(bucketID string) (*Bucket, error) {
	query := "SELECT * FROM buckets WHERE id = ?"
	row := r.satellitesDB.QueryRow(query, bucketID)

	bucket, err := r.scanBucket(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket by ID: %w", err)
	}

	return bucket, nil
}

// GetAll gets all buckets
func (r *BucketRepository) GetAll() ([]*Bucket, error) {
	query := "SELECT * FROM buckets ORDER BY type, created_at"
	rows, err := r.satellitesDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get all buckets: %w", err)
	}
	defer rows.Close()

	return r.scanBuckets(rows)
}

// GetActive gets all active buckets (not retired or paused)
func (r *BucketRepository) GetActive() ([]*Bucket, error) {
	query := `SELECT * FROM buckets
	          WHERE status NOT IN ('retired', 'paused')
	          ORDER BY type, created_at`
	rows, err := r.satellitesDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to get active buckets: %w", err)
	}
	defer rows.Close()

	return r.scanBuckets(rows)
}

// GetByType gets all buckets of a specific type
func (r *BucketRepository) GetByType(bucketType BucketType) ([]*Bucket, error) {
	query := "SELECT * FROM buckets WHERE type = ? ORDER BY created_at"
	rows, err := r.satellitesDB.Query(query, string(bucketType))
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets by type: %w", err)
	}
	defer rows.Close()

	return r.scanBuckets(rows)
}

// GetByStatus gets all buckets with a specific status
func (r *BucketRepository) GetByStatus(status BucketStatus) ([]*Bucket, error) {
	query := "SELECT * FROM buckets WHERE status = ? ORDER BY type, created_at"
	rows, err := r.satellitesDB.Query(query, string(status))
	if err != nil {
		return nil, fmt.Errorf("failed to get buckets by status: %w", err)
	}
	defer rows.Close()

	return r.scanBuckets(rows)
}

// GetSatellites gets all satellite buckets (excluding core)
func (r *BucketRepository) GetSatellites() ([]*Bucket, error) {
	return r.GetByType(BucketTypeSatellite)
}

// GetCore gets the core bucket
func (r *BucketRepository) GetCore() (*Bucket, error) {
	return r.GetByID("core")
}

// Create creates a new bucket
func (r *BucketRepository) Create(bucket *Bucket) error {
	now := time.Now().Format(time.RFC3339)
	bucket.CreatedAt = now
	bucket.UpdatedAt = now

	tx, err := r.satellitesDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := `INSERT INTO buckets
	          (id, name, type, notes, target_pct, min_pct, max_pct,
	           consecutive_losses, max_consecutive_losses, high_water_mark,
	           high_water_mark_date, loss_streak_paused_at, status,
	           created_at, updated_at)
	          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

	_, err = tx.Exec(query,
		bucket.ID,
		bucket.Name,
		string(bucket.Type),
		bucket.Notes,
		bucket.TargetPct,
		bucket.MinPct,
		bucket.MaxPct,
		bucket.ConsecutiveLosses,
		bucket.MaxConsecutiveLosses,
		bucket.HighWaterMark,
		bucket.HighWaterMarkDate,
		bucket.LossStreakPausedAt,
		string(bucket.Status),
		bucket.CreatedAt,
		bucket.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to insert bucket: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("bucket_id", bucket.ID).Str("name", bucket.Name).Msg("Created bucket")
	return nil
}

// Update updates bucket fields
// Allowed columns are whitelisted to prevent SQL injection
func (r *BucketRepository) Update(bucketID string, updates map[string]interface{}) (*Bucket, error) {
	if len(updates) == 0 {
		return r.GetByID(bucketID)
	}

	// Add updated_at timestamp
	updates["updated_at"] = time.Now().Format(time.RFC3339)

	// Whitelist allowed columns
	allowedColumns := map[string]bool{
		"name":                   true,
		"notes":                  true,
		"type":                   true,
		"status":                 true,
		"target_pct":             true,
		"min_pct":                true,
		"max_pct":                true,
		"high_water_mark":        true,
		"high_water_mark_date":   true,
		"consecutive_losses":     true,
		"max_consecutive_losses": true,
		"loss_streak_paused_at":  true,
		"updated_at":             true,
	}

	// Validate all column names
	for col := range updates {
		if !allowedColumns[col] {
			return nil, fmt.Errorf("invalid column name in update: %s", col)
		}
	}

	// Convert enum values to strings
	if typeVal, ok := updates["type"].(BucketType); ok {
		updates["type"] = string(typeVal)
	}
	if statusVal, ok := updates["status"].(BucketStatus); ok {
		updates["status"] = string(statusVal)
	}

	// Build SET clause
	setClauses := make([]string, 0, len(updates))
	values := make([]interface{}, 0, len(updates)+1)
	for col, val := range updates {
		setClauses = append(setClauses, fmt.Sprintf("%s = ?", col))
		values = append(values, val)
	}
	values = append(values, bucketID)

	query := fmt.Sprintf("UPDATE buckets SET %s WHERE id = ?", strings.Join(setClauses, ", "))

	_, err := r.satellitesDB.Exec(query, values...)
	if err != nil {
		return nil, fmt.Errorf("failed to update bucket: %w", err)
	}

	r.log.Info().Str("bucket_id", bucketID).Msg("Updated bucket")
	return r.GetByID(bucketID)
}

// UpdateStatus updates bucket status
func (r *BucketRepository) UpdateStatus(bucketID string, status BucketStatus) (*Bucket, error) {
	return r.Update(bucketID, map[string]interface{}{
		"status": status,
	})
}

// IncrementConsecutiveLosses increments consecutive losses counter
// Returns new count of consecutive losses
func (r *BucketRepository) IncrementConsecutiveLosses(bucketID string) (int, error) {
	now := time.Now().Format(time.RFC3339)

	query := `UPDATE buckets
	          SET consecutive_losses = consecutive_losses + 1,
	              updated_at = ?
	          WHERE id = ?`

	_, err := r.satellitesDB.Exec(query, now, bucketID)
	if err != nil {
		return 0, fmt.Errorf("failed to increment consecutive losses: %w", err)
	}

	// Get updated count
	var count int
	err = r.satellitesDB.QueryRow(
		"SELECT consecutive_losses FROM buckets WHERE id = ?",
		bucketID,
	).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get consecutive losses: %w", err)
	}

	r.log.Info().Str("bucket_id", bucketID).Int("count", count).Msg("Incremented consecutive losses")
	return count, nil
}

// ResetConsecutiveLosses resets consecutive losses counter to 0
func (r *BucketRepository) ResetConsecutiveLosses(bucketID string) error {
	now := time.Now().Format(time.RFC3339)

	query := `UPDATE buckets
	          SET consecutive_losses = 0,
	              loss_streak_paused_at = NULL,
	              updated_at = ?
	          WHERE id = ?`

	_, err := r.satellitesDB.Exec(query, now, bucketID)
	if err != nil {
		return fmt.Errorf("failed to reset consecutive losses: %w", err)
	}

	r.log.Info().Str("bucket_id", bucketID).Msg("Reset consecutive losses")
	return nil
}

// UpdateHighWaterMark updates high water mark if new value is higher
func (r *BucketRepository) UpdateHighWaterMark(bucketID string, value float64) (*Bucket, error) {
	now := time.Now().Format(time.RFC3339)

	query := `UPDATE buckets
	          SET high_water_mark = ?,
	              high_water_mark_date = ?,
	              updated_at = ?
	          WHERE id = ? AND (high_water_mark IS NULL OR high_water_mark < ?)`

	result, err := r.satellitesDB.Exec(query, value, now, now, bucketID, value)
	if err != nil {
		return nil, fmt.Errorf("failed to update high water mark: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected > 0 {
		r.log.Info().Str("bucket_id", bucketID).Float64("value", value).Msg("Updated high water mark")
	}

	return r.GetByID(bucketID)
}

// Delete deletes a bucket (typically only for satellites)
// Core bucket should never be deleted
func (r *BucketRepository) Delete(bucketID string) error {
	if bucketID == "core" {
		return fmt.Errorf("cannot delete core bucket")
	}

	result, err := r.satellitesDB.Exec("DELETE FROM buckets WHERE id = ?", bucketID)
	if err != nil {
		return fmt.Errorf("failed to delete bucket: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return fmt.Errorf("bucket not found: %s", bucketID)
	}

	r.log.Info().Str("bucket_id", bucketID).Msg("Deleted bucket")
	return nil
}

// --- Satellite Settings Methods ---

// GetSettings gets settings for a satellite
func (r *BucketRepository) GetSettings(satelliteID string) (*SatelliteSettings, error) {
	query := "SELECT * FROM satellite_settings WHERE satellite_id = ?"
	row := r.satellitesDB.QueryRow(query, satelliteID)

	settings, err := r.scanSettings(row)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get satellite settings: %w", err)
	}

	return settings, nil
}

// SaveSettings saves or updates satellite settings
func (r *BucketRepository) SaveSettings(settings *SatelliteSettings) error {
	if err := settings.Validate(); err != nil {
		return fmt.Errorf("invalid settings: %w", err)
	}

	query := `INSERT OR REPLACE INTO satellite_settings
	          (satellite_id, preset, risk_appetite, hold_duration, entry_style,
	           position_spread, profit_taking, trailing_stops, follow_regime,
	           auto_harvest, pause_high_volatility, dividend_handling,
	           risk_free_rate, sortino_mar, evaluation_period_days, volatility_window)
	          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`

	_, err := r.satellitesDB.Exec(query,
		settings.SatelliteID,
		settings.Preset,
		settings.RiskAppetite,
		settings.HoldDuration,
		settings.EntryStyle,
		settings.PositionSpread,
		settings.ProfitTaking,
		boolToInt(settings.TrailingStops),
		boolToInt(settings.FollowRegime),
		boolToInt(settings.AutoHarvest),
		boolToInt(settings.PauseHighVolatility),
		settings.DividendHandling,
		settings.RiskFreeRate,
		settings.SortinoMAR,
		settings.EvaluationPeriodDays,
		settings.VolatilityWindow,
	)
	if err != nil {
		return fmt.Errorf("failed to save satellite settings: %w", err)
	}

	r.log.Info().Str("satellite_id", settings.SatelliteID).Msg("Saved satellite settings")
	return nil
}

// DeleteSettings deletes satellite settings
func (r *BucketRepository) DeleteSettings(satelliteID string) error {
	result, err := r.satellitesDB.Exec(
		"DELETE FROM satellite_settings WHERE satellite_id = ?",
		satelliteID,
	)
	if err != nil {
		return fmt.Errorf("failed to delete satellite settings: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return fmt.Errorf("satellite settings not found: %s", satelliteID)
	}

	r.log.Info().Str("satellite_id", satelliteID).Msg("Deleted satellite settings")
	return nil
}

// --- Helper Methods ---

// scanBucket scans a single bucket row
func (r *BucketRepository) scanBucket(row interface{ Scan(...interface{}) error }) (*Bucket, error) {
	var bucket Bucket
	var typeStr, statusStr string
	var notes, targetPct, minPct, maxPct sql.NullString
	var highWaterMarkDate, lossStreakPausedAt sql.NullString
	var agentID sql.NullString // Scan agent_id but ignore it (not in Bucket struct)

	err := row.Scan(
		&bucket.ID,
		&bucket.Name,
		&typeStr,
		&notes,
		&targetPct,
		&minPct,
		&maxPct,
		&bucket.ConsecutiveLosses,
		&bucket.MaxConsecutiveLosses,
		&bucket.HighWaterMark,
		&highWaterMarkDate,
		&lossStreakPausedAt,
		&statusStr,
		&bucket.CreatedAt,
		&bucket.UpdatedAt,
		&agentID, // Scan agent_id (16th column) but ignore it
	)
	if err != nil {
		return nil, err
	}

	bucket.Type = BucketType(typeStr)
	bucket.Status = BucketStatus(statusStr)

	if notes.Valid {
		bucket.Notes = &notes.String
	}
	if targetPct.Valid {
		val := parseFloat(targetPct.String)
		bucket.TargetPct = &val
	}
	if minPct.Valid {
		val := parseFloat(minPct.String)
		bucket.MinPct = &val
	}
	if maxPct.Valid {
		val := parseFloat(maxPct.String)
		bucket.MaxPct = &val
	}
	if highWaterMarkDate.Valid {
		bucket.HighWaterMarkDate = &highWaterMarkDate.String
	}
	if lossStreakPausedAt.Valid {
		bucket.LossStreakPausedAt = &lossStreakPausedAt.String
	}

	return &bucket, nil
}

// scanBuckets scans multiple bucket rows
func (r *BucketRepository) scanBuckets(rows *sql.Rows) ([]*Bucket, error) {
	buckets := make([]*Bucket, 0)

	for rows.Next() {
		bucket, err := r.scanBucket(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bucket row: %w", err)
		}
		buckets = append(buckets, bucket)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating bucket rows: %w", err)
	}

	return buckets, nil
}

// scanSettings scans satellite settings row
func (r *BucketRepository) scanSettings(row interface{ Scan(...interface{}) error }) (*SatelliteSettings, error) {
	var settings SatelliteSettings
	var preset sql.NullString
	var trailingStops, followRegime, autoHarvest, pauseHighVolatility int

	err := row.Scan(
		&settings.SatelliteID,
		&preset,
		&settings.RiskAppetite,
		&settings.HoldDuration,
		&settings.EntryStyle,
		&settings.PositionSpread,
		&settings.ProfitTaking,
		&trailingStops,
		&followRegime,
		&autoHarvest,
		&pauseHighVolatility,
		&settings.DividendHandling,
		&settings.RiskFreeRate,
		&settings.SortinoMAR,
		&settings.EvaluationPeriodDays,
		&settings.VolatilityWindow,
	)
	if err != nil {
		return nil, err
	}

	if preset.Valid {
		settings.Preset = &preset.String
	}

	settings.TrailingStops = intToBool(trailingStops)
	settings.FollowRegime = intToBool(followRegime)
	settings.AutoHarvest = intToBool(autoHarvest)
	settings.PauseHighVolatility = intToBool(pauseHighVolatility)

	return &settings, nil
}

// Helper functions
func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func intToBool(i int) bool {
	return i != 0
}

func parseFloat(s string) float64 {
	var f float64
	fmt.Sscanf(s, "%f", &f)
	return f
}
