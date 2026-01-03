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
type RecommendationRepository struct {
	db  *sql.DB
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

	now := time.Now()

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
	var executedAt sql.NullTime

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
		&rec.CreatedAt,
		&rec.UpdatedAt,
		&executedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if executedAt.Valid {
		rec.ExecutedAt = &executedAt.Time
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
		var executedAt sql.NullTime

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
			&rec.CreatedAt,
			&rec.UpdatedAt,
			&executedAt,
		)

		if err != nil {
			return nil, err
		}

		if executedAt.Valid {
			rec.ExecutedAt = &executedAt.Time
		}

		recs = append(recs, rec)
	}

	return recs, rows.Err()
}

// MarkExecuted marks a recommendation as executed
func (r *RecommendationRepository) MarkExecuted(recUUID string) error {
	now := time.Now()
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
