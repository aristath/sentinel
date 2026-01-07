// Package planning provides portfolio planning and strategy generation functionality.
package planning

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
)

// RecommendationRepository handles CRUD operations for recommendations
//
// Minimal implementation for emergency rebalancing.
// TODO: Full implementation matching Python can be added later.
//
// Faithful translation from Python: app/repositories/recommendation.py
// Database: cache.db (recommendations table)
type RecommendationRepository struct {
	db  *sql.DB // cache.db
	log zerolog.Logger
}

// Recommendation represents a stored recommendation
type Recommendation struct {
	UUID                  string
	Symbol                string
	Name                  string
	Side                  string
	Quantity              float64
	EstimatedPrice        float64
	EstimatedValue        float64
	Reason                string
	Currency              string
	Priority              float64
	CurrentPortfolioScore float64
	NewPortfolioScore     float64
	ScoreChange           float64
	Status                string // "pending", "executed", "dismissed"
	PortfolioHash         string
	CreatedAt             time.Time
	UpdatedAt             time.Time
	ExecutedAt            *time.Time
}

// NewRecommendationRepository creates a new recommendation repository
func NewRecommendationRepository(db *sql.DB, log zerolog.Logger) *RecommendationRepository {
	return &RecommendationRepository{
		db:  db,
		log: log.With().Str("repository", "recommendation").Logger(),
	}
}

// CreateOrUpdate creates or updates a recommendation
func (r *RecommendationRepository) CreateOrUpdate(rec Recommendation) (string, error) {
	// Check if recommendation exists
	existing, err := r.findExisting(rec.Symbol, rec.Side, rec.Reason, rec.PortfolioHash)
	if err != nil {
		r.log.Warn().Err(err).Msg("Error checking for existing recommendation")
	}

	now := time.Now().Unix()

	if existing != nil {
		// Update existing
		_, err := r.db.Exec(`
			UPDATE recommendations
			SET updated_at = ?,
				name = ?,
				quantity = ?,
				estimated_price = ?,
				estimated_value = ?,
				currency = ?,
				priority = ?,
				current_portfolio_score = ?,
				new_portfolio_score = ?,
				score_change = ?
			WHERE uuid = ?
		`,
			now,
			rec.Name,
			rec.Quantity,
			rec.EstimatedPrice,
			rec.EstimatedValue,
			rec.Currency,
			rec.Priority,
			rec.CurrentPortfolioScore,
			rec.NewPortfolioScore,
			rec.ScoreChange,
			existing.UUID,
		)

		if err != nil {
			return "", fmt.Errorf("failed to update recommendation: %w", err)
		}

		return existing.UUID, nil
	}

	// Create new
	newUUID := uuid.New().String()
	_, err = r.db.Exec(`
		INSERT INTO recommendations
		(uuid, symbol, name, side, quantity, estimated_price, estimated_value,
		 reason, currency, priority, current_portfolio_score, new_portfolio_score,
		 score_change, status, portfolio_hash, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`,
		newUUID,
		rec.Symbol,
		rec.Name,
		rec.Side,
		rec.Quantity,
		rec.EstimatedPrice,
		rec.EstimatedValue,
		rec.Reason,
		rec.Currency,
		rec.Priority,
		rec.CurrentPortfolioScore,
		rec.NewPortfolioScore,
		rec.ScoreChange,
		"pending",
		rec.PortfolioHash,
		now,
		now,
	)

	if err != nil {
		return "", fmt.Errorf("failed to insert recommendation: %w", err)
	}

	return newUUID, nil
}

// findExisting finds an existing recommendation by matching criteria
func (r *RecommendationRepository) findExisting(symbol, side, reason, portfolioHash string) (*Recommendation, error) {
	var rec Recommendation
	var createdAtUnix, updatedAtUnix, executedAtUnix sql.NullInt64

	err := r.db.QueryRow(`
		SELECT uuid, symbol, name, side, quantity, estimated_price, estimated_value,
			   reason, currency, priority, current_portfolio_score, new_portfolio_score,
			   score_change, status, portfolio_hash, created_at, updated_at, executed_at
		FROM recommendations
		WHERE symbol = ? AND side = ? AND reason = ? AND portfolio_hash = ?
		LIMIT 1
	`,
		symbol,
		side,
		reason,
		portfolioHash,
	).Scan(
		&rec.UUID,
		&rec.Symbol,
		&rec.Name,
		&rec.Side,
		&rec.Quantity,
		&rec.EstimatedPrice,
		&rec.EstimatedValue,
		&rec.Reason,
		&rec.Currency,
		&rec.Priority,
		&rec.CurrentPortfolioScore,
		&rec.NewPortfolioScore,
		&rec.ScoreChange,
		&rec.Status,
		&rec.PortfolioHash,
		&createdAtUnix,
		&updatedAtUnix,
		&executedAtUnix,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	// Convert Unix timestamps to time.Time
	if createdAtUnix.Valid {
		rec.CreatedAt = time.Unix(createdAtUnix.Int64, 0).UTC()
	}
	if updatedAtUnix.Valid {
		rec.UpdatedAt = time.Unix(updatedAtUnix.Int64, 0).UTC()
	}
	if executedAtUnix.Valid {
		t := time.Unix(executedAtUnix.Int64, 0).UTC()
		rec.ExecutedAt = &t
	}

	return &rec, nil
}

// FindMatchingForExecution finds recommendations matching criteria for execution
func (r *RecommendationRepository) FindMatchingForExecution(symbol, side, portfolioHash string) ([]Recommendation, error) {
	rows, err := r.db.Query(`
		SELECT uuid, symbol, name, side, quantity, estimated_price, estimated_value,
			   reason, currency, priority, current_portfolio_score, new_portfolio_score,
			   score_change, status, portfolio_hash, created_at, updated_at, executed_at
		FROM recommendations
		WHERE symbol = ? AND side = ? AND portfolio_hash = ? AND status = 'pending'
	`,
		symbol,
		side,
		portfolioHash,
	)

	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var recs []Recommendation
	for rows.Next() {
		var rec Recommendation
		var createdAtUnix, updatedAtUnix, executedAtUnix sql.NullInt64

		err := rows.Scan(
			&rec.UUID,
			&rec.Symbol,
			&rec.Name,
			&rec.Side,
			&rec.Quantity,
			&rec.EstimatedPrice,
			&rec.EstimatedValue,
			&rec.Reason,
			&rec.Currency,
			&rec.Priority,
			&rec.CurrentPortfolioScore,
			&rec.NewPortfolioScore,
			&rec.ScoreChange,
			&rec.Status,
			&rec.PortfolioHash,
			&createdAtUnix,
			&updatedAtUnix,
			&executedAtUnix,
		)

		if err != nil {
			return nil, err
		}

		// Convert Unix timestamps to time.Time
		if createdAtUnix.Valid {
			rec.CreatedAt = time.Unix(createdAtUnix.Int64, 0).UTC()
		}
		if updatedAtUnix.Valid {
			rec.UpdatedAt = time.Unix(updatedAtUnix.Int64, 0).UTC()
		}
		if executedAtUnix.Valid {
			t := time.Unix(executedAtUnix.Int64, 0).UTC()
			rec.ExecutedAt = &t
		}

		recs = append(recs, rec)
	}

	return recs, rows.Err()
}

// MarkExecuted marks a recommendation as executed
func (r *RecommendationRepository) MarkExecuted(recUUID string) error {
	now := time.Now().Unix()
	_, err := r.db.Exec(`
		UPDATE recommendations
		SET status = 'executed',
			executed_at = ?,
			updated_at = ?
		WHERE uuid = ?
	`,
		now,
		now,
		recUUID,
	)

	if err != nil {
		return fmt.Errorf("failed to mark recommendation as executed: %w", err)
	}

	return nil
}

// CountPendingBySide counts pending recommendations by side (BUY vs SELL)
func (r *RecommendationRepository) CountPendingBySide() (buyCount int, sellCount int, err error) {
	// Count BUY recommendations
	err = r.db.QueryRow(`
		SELECT COUNT(*) FROM recommendations
		WHERE status = 'pending' AND side = 'BUY'
	`).Scan(&buyCount)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to count BUY recommendations: %w", err)
	}

	// Count SELL recommendations
	err = r.db.QueryRow(`
		SELECT COUNT(*) FROM recommendations
		WHERE status = 'pending' AND side = 'SELL'
	`).Scan(&sellCount)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to count SELL recommendations: %w", err)
	}

	return buyCount, sellCount, nil
}

// DismissAllByPortfolioHash dismisses all recommendations for a given portfolio hash
func (r *RecommendationRepository) DismissAllByPortfolioHash(portfolioHash string) (int, error) {
	now := time.Now().Unix()
	result, err := r.db.Exec(`
		UPDATE recommendations
		SET status = 'dismissed',
			updated_at = ?
		WHERE portfolio_hash = ? AND status = 'pending'
	`,
		now,
		portfolioHash,
	)

	if err != nil {
		return 0, fmt.Errorf("failed to dismiss recommendations: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int64("dismissed_count", rowsAffected).
		Msg("Dismissed recommendations by portfolio hash")

	return int(rowsAffected), nil
}

// DismissAllPending dismisses all pending recommendations regardless of portfolio hash
func (r *RecommendationRepository) DismissAllPending() (int, error) {
	now := time.Now().Unix()
	result, err := r.db.Exec(`
		UPDATE recommendations
		SET status = 'dismissed',
			updated_at = ?
		WHERE status = 'pending'
	`,
		now,
	)

	if err != nil {
		return 0, fmt.Errorf("failed to dismiss all pending recommendations: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	r.log.Info().
		Int64("dismissed_count", rowsAffected).
		Msg("Dismissed all pending recommendations")

	return int(rowsAffected), nil
}

// GetPendingRecommendations retrieves all pending recommendations ordered by priority
func (r *RecommendationRepository) GetPendingRecommendations(limit int) ([]Recommendation, error) {
	query := `
		SELECT uuid, symbol, name, side, quantity, estimated_price, estimated_value,
			   reason, currency, priority, current_portfolio_score, new_portfolio_score,
			   score_change, status, portfolio_hash, created_at, updated_at, executed_at
		FROM recommendations
		WHERE status = 'pending'
		ORDER BY priority ASC, created_at ASC
	`

	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query pending recommendations: %w", err)
	}
	defer rows.Close()

	var recs []Recommendation
	for rows.Next() {
		var rec Recommendation
		var createdAtUnix, updatedAtUnix, executedAtUnix sql.NullInt64

		err := rows.Scan(
			&rec.UUID,
			&rec.Symbol,
			&rec.Name,
			&rec.Side,
			&rec.Quantity,
			&rec.EstimatedPrice,
			&rec.EstimatedValue,
			&rec.Reason,
			&rec.Currency,
			&rec.Priority,
			&rec.CurrentPortfolioScore,
			&rec.NewPortfolioScore,
			&rec.ScoreChange,
			&rec.Status,
			&rec.PortfolioHash,
			&createdAtUnix,
			&updatedAtUnix,
			&executedAtUnix,
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan recommendation: %w", err)
		}

		// Convert Unix timestamps to time.Time
		if createdAtUnix.Valid {
			rec.CreatedAt = time.Unix(createdAtUnix.Int64, 0).UTC()
		}
		if updatedAtUnix.Valid {
			rec.UpdatedAt = time.Unix(updatedAtUnix.Int64, 0).UTC()
		}
		if executedAtUnix.Valid {
			t := time.Unix(executedAtUnix.Int64, 0).UTC()
			rec.ExecutedAt = &t
		}

		recs = append(recs, rec)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating recommendations: %w", err)
	}

	return recs, nil
}

// GetRecommendationsAsPlan retrieves pending recommendations and formats them as a plan structure
// Returns a plan-like structure with steps array for frontend consumption
// getEvaluatedCount is an optional function to retrieve the evaluated count for a portfolio hash
func (r *RecommendationRepository) GetRecommendationsAsPlan(getEvaluatedCount func(portfolioHash string) (int, error)) (map[string]interface{}, error) {
	recs, err := r.GetPendingRecommendations(0) // Get all pending
	if err != nil {
		return nil, fmt.Errorf("failed to get pending recommendations: %w", err)
	}

	if len(recs) == 0 {
		return map[string]interface{}{
			"steps": []interface{}{},
		}, nil
	}

	// Convert recommendations to steps format expected by frontend
	steps := make([]map[string]interface{}, 0, len(recs))
	var totalScoreImprovement float64
	var currentScore float64
	var endScore float64
	var finalCash float64
	var portfolioHash string

	for i, rec := range recs {
		// Use priority as step number (1-based)
		stepNum := int(rec.Priority) + 1
		if stepNum == 0 {
			stepNum = i + 1
		}

		// Track scores from first recommendation
		if i == 0 {
			currentScore = rec.CurrentPortfolioScore
			endScore = rec.NewPortfolioScore
			totalScoreImprovement = rec.ScoreChange
			portfolioHash = rec.PortfolioHash
		}

		step := map[string]interface{}{
			"step":                   stepNum,
			"symbol":                 rec.Symbol,
			"name":                   rec.Name,
			"side":                   rec.Side,
			"quantity":               rec.Quantity,
			"estimated_price":        rec.EstimatedPrice,
			"estimated_value":        rec.EstimatedValue,
			"currency":               rec.Currency,
			"reason":                 rec.Reason,
			"portfolio_score_before": rec.CurrentPortfolioScore,
			"portfolio_score_after":  rec.NewPortfolioScore,
			"score_change":           rec.ScoreChange,
			"available_cash_before":  0.0,   // TODO: Calculate from portfolio state
			"available_cash_after":   0.0,   // TODO: Calculate from portfolio state
			"is_emergency":           false, // TODO: Determine from reason or other criteria
		}

		steps = append(steps, step)
	}

	// Get evaluated count if function is provided
	var evaluatedCount interface{} = nil
	if getEvaluatedCount != nil && portfolioHash != "" {
		count, err := getEvaluatedCount(portfolioHash)
		if err != nil {
			r.log.Warn().Err(err).Str("portfolio_hash", portfolioHash).Msg("Failed to get evaluated count")
		} else {
			evaluatedCount = count
		}
	}

	// Build response matching frontend expectations
	response := map[string]interface{}{
		"steps":                   steps,
		"current_score":           currentScore,
		"end_state_score":         endScore,
		"total_score_improvement": totalScoreImprovement,
		"final_available_cash":    finalCash,
		"evaluated_count":         evaluatedCount,
	}

	return response, nil
}
