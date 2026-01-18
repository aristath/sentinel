package market_regime

import (
	"database/sql"
	"time"

	"github.com/rs/zerolog"
)

// RegimePersistence handles regime score history and smoothing
type RegimePersistence struct {
	db  *sql.DB
	log zerolog.Logger
	// Smoothing parameters
	smoothingAlpha float64 // Exponential moving average alpha (default 0.1)
}

// RegimeHistoryEntry represents a single regime score record
type RegimeHistoryEntry struct {
	ID             int64
	RecordedAt     time.Time
	Region         string  // Region: US, EU, ASIA, or GLOBAL
	RawScore       float64 // Raw score before smoothing
	SmoothedScore  float64 // Smoothed score (EMA)
	DiscreteRegime string  // Discrete regime classification (bull, bear, neutral)
}

// NewRegimePersistence creates a new regime persistence manager
func NewRegimePersistence(db *sql.DB, log zerolog.Logger) *RegimePersistence {
	return &RegimePersistence{
		db:             db,
		log:            log.With().Str("component", "regime_persistence").Logger(),
		smoothingAlpha: 0.1, // Default: slow adaptation (matches slow-growth strategy)
	}
}

// GetCurrentRegimeScore returns the current smoothed regime score
// Uses GLOBAL region for backwards compatibility
func (rp *RegimePersistence) GetCurrentRegimeScore() (MarketRegimeScore, error) {
	return rp.GetCurrentRegimeScoreForRegion("GLOBAL")
}

// RecordRegimeScore records a raw regime score and calculates smoothed score
// Uses GLOBAL region for backwards compatibility
func (rp *RegimePersistence) RecordRegimeScore(rawScore MarketRegimeScore) error {
	return rp.RecordRegimeScoreForRegion("GLOBAL", rawScore)
}

// GetSmoothedScore returns the exponentially smoothed score
// This is a convenience method that wraps GetCurrentRegimeScore
func (rp *RegimePersistence) GetSmoothedScore() (MarketRegimeScore, error) {
	return rp.GetCurrentRegimeScore()
}

// GetScoreChange calculates the change in regime score from the last check
func (rp *RegimePersistence) GetScoreChange() (float64, error) {
	query := `SELECT smoothed_score FROM market_regime_history
	          ORDER BY recorded_at DESC LIMIT 2`

	rows, err := rp.db.Query(query)
	if err != nil {
		return 0.0, err
	}
	defer rows.Close()

	var scores []float64
	for rows.Next() {
		var score float64
		if err := rows.Scan(&score); err != nil {
			return 0.0, err
		}
		scores = append(scores, score)
	}

	if len(scores) < 2 {
		// Not enough history
		return 0.0, nil
	}

	// Calculate change (current - previous)
	change := scores[0] - scores[1]
	return change, nil
}

// GetRegimeHistory returns recent regime history entries
func (rp *RegimePersistence) GetRegimeHistory(limit int) ([]RegimeHistoryEntry, error) {
	query := `SELECT id, recorded_at, region, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          WHERE region = 'GLOBAL'
	          ORDER BY recorded_at DESC
	          LIMIT ?`

	rows, err := rp.db.Query(query, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []RegimeHistoryEntry
	for rows.Next() {
		var entry RegimeHistoryEntry
		var recordedAtUnix sql.NullInt64

		if err := rows.Scan(
			&entry.ID,
			&recordedAtUnix,
			&entry.Region,
			&entry.RawScore,
			&entry.SmoothedScore,
			&entry.DiscreteRegime,
		); err != nil {
			return nil, err
		}

		if recordedAtUnix.Valid {
			entry.RecordedAt = time.Unix(recordedAtUnix.Int64, 0).UTC()
		}

		entries = append(entries, entry)
	}

	return entries, nil
}

// ApplySmoothing applies exponential moving average smoothing
// This is a helper method that can be used independently
func (rp *RegimePersistence) ApplySmoothing(currentScore, lastSmoothed, alpha float64) float64 {
	detector := NewMarketRegimeDetector(rp.log)
	return detector.ApplySmoothing(currentScore, lastSmoothed, alpha)
}

// ============================================================================
// Per-Region Methods
// ============================================================================

// GetCurrentRegimeScoreForRegion returns the current smoothed regime score for a specific region
func (rp *RegimePersistence) GetCurrentRegimeScoreForRegion(region string) (MarketRegimeScore, error) {
	query := `SELECT smoothed_score FROM market_regime_history
	          WHERE region = ?
	          ORDER BY id DESC LIMIT 1`

	var score float64
	err := rp.db.QueryRow(query, region).Scan(&score)
	if err == sql.ErrNoRows {
		// No history for this region yet, return neutral
		return NeutralScore, nil
	}
	if err != nil {
		return NeutralScore, err
	}

	return MarketRegimeScore(score), nil
}

// RecordRegimeScoreForRegion records a raw regime score for a specific region and calculates smoothed score
func (rp *RegimePersistence) RecordRegimeScoreForRegion(region string, rawScore MarketRegimeScore) error {
	// Get last smoothed score for this specific region
	lastSmoothed, err := rp.GetCurrentRegimeScoreForRegion(region)
	if err != nil {
		return err
	}

	// Apply smoothing
	var smoothed float64
	if lastSmoothed == NeutralScore {
		// Check if we actually have history for this region
		var count int
		err := rp.db.QueryRow("SELECT COUNT(*) FROM market_regime_history WHERE region = ?", region).Scan(&count)
		if err == nil && count == 0 {
			// No history for this region - use raw score directly (first entry)
			smoothed = float64(rawScore)
		} else {
			// We have history but last smoothed is 0.0 - apply smoothing
			smoothed = rp.ApplySmoothing(float64(rawScore), float64(lastSmoothed), rp.smoothingAlpha)
		}
	} else {
		// Apply EMA smoothing
		smoothed = rp.smoothingAlpha*float64(rawScore) + (1.0-rp.smoothingAlpha)*float64(lastSmoothed)
	}

	// Insert into database with region
	query := `INSERT INTO market_regime_history
	          (recorded_at, region, raw_score, smoothed_score, discrete_regime)
	          VALUES (?, ?, ?, ?, ?)`

	_, err = rp.db.Exec(query, time.Now().Unix(), region, float64(rawScore), smoothed, "n/a")
	if err != nil {
		return err
	}

	rp.log.Debug().
		Str("region", region).
		Float64("raw_score", float64(rawScore)).
		Float64("smoothed_score", smoothed).
		Msg("Recorded per-region regime score")

	return nil
}

// GetAllCurrentScores returns the current smoothed regime score for all regions that have data
func (rp *RegimePersistence) GetAllCurrentScores() (map[string]float64, error) {
	// Get the latest score for each region using a subquery
	query := `
		SELECT region, smoothed_score
		FROM market_regime_history h1
		WHERE id = (
			SELECT MAX(id) FROM market_regime_history h2
			WHERE h2.region = h1.region
		)
	`

	rows, err := rp.db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	scores := make(map[string]float64)
	for rows.Next() {
		var region string
		var score float64
		if err := rows.Scan(&region, &score); err != nil {
			return nil, err
		}
		scores[region] = score
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	return scores, nil
}

// GetRegimeHistoryForRegion returns recent regime history entries for a specific region
func (rp *RegimePersistence) GetRegimeHistoryForRegion(region string, limit int) ([]RegimeHistoryEntry, error) {
	query := `SELECT id, recorded_at, region, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          WHERE region = ?
	          ORDER BY id DESC
	          LIMIT ?`

	rows, err := rp.db.Query(query, region, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []RegimeHistoryEntry
	for rows.Next() {
		var entry RegimeHistoryEntry
		var recordedAtUnix sql.NullInt64

		if err := rows.Scan(
			&entry.ID,
			&recordedAtUnix,
			&entry.Region,
			&entry.RawScore,
			&entry.SmoothedScore,
			&entry.DiscreteRegime,
		); err != nil {
			return nil, err
		}

		if recordedAtUnix.Valid {
			entry.RecordedAt = time.Unix(recordedAtUnix.Int64, 0).UTC()
		}

		entries = append(entries, entry)
	}

	return entries, nil
}

// GetLatestEntry returns the most recent regime history entry for GLOBAL region
// This includes all fields: raw_score, smoothed_score, discrete_regime, and recorded_at
func (rp *RegimePersistence) GetLatestEntry() (*RegimeHistoryEntry, error) {
	query := `SELECT id, recorded_at, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          WHERE region = 'GLOBAL'
	          ORDER BY id DESC
	          LIMIT 1`

	var entry RegimeHistoryEntry
	var recordedAtUnix sql.NullInt64

	err := rp.db.QueryRow(query).Scan(
		&entry.ID,
		&recordedAtUnix,
		&entry.RawScore,
		&entry.SmoothedScore,
		&entry.DiscreteRegime,
	)
	if err == sql.ErrNoRows {
		return nil, nil // No history yet
	}
	if err != nil {
		return nil, err
	}

	if recordedAtUnix.Valid {
		entry.RecordedAt = time.Unix(recordedAtUnix.Int64, 0).UTC()
	}
	entry.Region = "GLOBAL"

	return &entry, nil
}

// GetLatestEntryForRegion returns the most recent regime history entry for a specific region
func (rp *RegimePersistence) GetLatestEntryForRegion(region string) (*RegimeHistoryEntry, error) {
	query := `SELECT id, recorded_at, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          WHERE region = ?
	          ORDER BY id DESC
	          LIMIT 1`

	var entry RegimeHistoryEntry
	var recordedAtUnix sql.NullInt64

	err := rp.db.QueryRow(query, region).Scan(
		&entry.ID,
		&recordedAtUnix,
		&entry.RawScore,
		&entry.SmoothedScore,
		&entry.DiscreteRegime,
	)
	if err == sql.ErrNoRows {
		return nil, nil // No history yet
	}
	if err != nil {
		return nil, err
	}

	if recordedAtUnix.Valid {
		entry.RecordedAt = time.Unix(recordedAtUnix.Int64, 0).UTC()
	}
	entry.Region = region

	return &entry, nil
}

// GetEntryAtOrBeforeDate returns the most recent regime history entry at or before the given date
// Uses GLOBAL region by default. Returns nil if no entry exists before or at the given date.
func (rp *RegimePersistence) GetEntryAtOrBeforeDate(targetDate time.Time) (*RegimeHistoryEntry, error) {
	return rp.GetEntryAtOrBeforeDateForRegion("GLOBAL", targetDate)
}

// GetEntryAtOrBeforeDateForRegion returns the most recent regime history entry at or before the given date for a specific region
// Returns nil if no entry exists before or at the given date.
func (rp *RegimePersistence) GetEntryAtOrBeforeDateForRegion(region string, targetDate time.Time) (*RegimeHistoryEntry, error) {
	// Convert target date to Unix timestamp (midnight UTC for the date)
	targetTimestamp := time.Date(targetDate.Year(), targetDate.Month(), targetDate.Day(), 23, 59, 59, 0, time.UTC).Unix()

	query := `SELECT id, recorded_at, raw_score, smoothed_score, discrete_regime
	          FROM market_regime_history
	          WHERE region = ? AND recorded_at <= ?
	          ORDER BY recorded_at DESC
	          LIMIT 1`

	var entry RegimeHistoryEntry
	var recordedAtUnix sql.NullInt64

	err := rp.db.QueryRow(query, region, targetTimestamp).Scan(
		&entry.ID,
		&recordedAtUnix,
		&entry.RawScore,
		&entry.SmoothedScore,
		&entry.DiscreteRegime,
	)
	if err == sql.ErrNoRows {
		return nil, nil // No entry at or before this date
	}
	if err != nil {
		return nil, err
	}

	if recordedAtUnix.Valid {
		entry.RecordedAt = time.Unix(recordedAtUnix.Int64, 0).UTC()
	}
	entry.Region = region

	return &entry, nil
}
