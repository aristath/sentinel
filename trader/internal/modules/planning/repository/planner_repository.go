package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// PlannerRepository handles database operations for planning module.
// Database: agents.db (sequences, evaluations, best_result tables)
type PlannerRepository struct {
	db  *database.DB // agents.db
	log zerolog.Logger
}

// NewPlannerRepository creates a new planner repository.
// db parameter should be agents.db connection
func NewPlannerRepository(db *database.DB, log zerolog.Logger) *PlannerRepository {
	return &PlannerRepository{
		db:  db,
		log: log.With().Str("component", "planner_repository").Logger(),
	}
}

// SequenceRecord represents a sequence in the database.
type SequenceRecord struct {
	ID            int64
	PortfolioHash string
	SequenceData  string // JSON
	PatternType   string
	Depth         int
	Priority      float64
	Completed     bool
	CreatedAt     time.Time
}

// EvaluationRecord represents an evaluation in the database.
type EvaluationRecord struct {
	ID            int64
	SequenceHash  string
	PortfolioHash string
	EndScore      float64
	DeltaScore    float64
	Metrics       string // JSON
	Completed     bool
	CreatedAt     time.Time
}

// BestResultRecord represents the best result in the database.
type BestResultRecord struct {
	ID            int64
	PortfolioHash string
	SequenceHash  string
	PlanData      string // JSON
	Score         float64
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// InsertSequence inserts a new sequence into the database.
func (r *PlannerRepository) InsertSequence(
	portfolioHash string,
	sequence domain.ActionSequence,
) (int, error) {
	sequenceData, err := json.Marshal(sequence)
	if err != nil {
		return 0, fmt.Errorf("failed to marshal sequence: %w", err)
	}

	result, err := r.db.Exec(`
		INSERT INTO sequences (portfolio_hash, sequence_data, pattern_type, depth, priority, completed, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, portfolioHash, string(sequenceData), sequence.PatternType, sequence.Depth, sequence.Priority, false, time.Now())

	if err != nil {
		return 0, fmt.Errorf("failed to insert sequence: %w", err)
	}

	id, err := result.LastInsertId()
	if err != nil {
		return 0, fmt.Errorf("failed to get last insert id: %w", err)
	}

	r.log.Debug().
		Int64("id", id).
		Str("portfolio_hash", portfolioHash).
		Str("pattern_type", sequence.PatternType).
		Msg("Inserted sequence")

	return int(id), nil
}

// GetSequence retrieves a sequence by ID.
func (r *PlannerRepository) GetSequence(id int64) (*domain.ActionSequence, error) {
	var record SequenceRecord
	err := r.db.QueryRow(`
		SELECT id, portfolio_hash, sequence_data, pattern_type, depth, priority, completed, created_at
		FROM sequences
		WHERE id = ?
	`, id).Scan(
		&record.ID,
		&record.PortfolioHash,
		&record.SequenceData,
		&record.PatternType,
		&record.Depth,
		&record.Priority,
		&record.Completed,
		&record.CreatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get sequence: %w", err)
	}

	var sequence domain.ActionSequence
	if err := json.Unmarshal([]byte(record.SequenceData), &sequence); err != nil {
		return nil, fmt.Errorf("failed to unmarshal sequence: %w", err)
	}

	return &sequence, nil
}

// ListSequencesByPortfolioHash retrieves all sequences for a portfolio hash.
func (r *PlannerRepository) ListSequencesByPortfolioHash(
	portfolioHash string,
	limit int,
) ([]SequenceRecord, error) {
	query := `
		SELECT id, portfolio_hash, sequence_data, pattern_type, depth, priority, completed, created_at
		FROM sequences
		WHERE portfolio_hash = ?
		ORDER BY priority DESC, created_at DESC
	`
	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.Query(query, portfolioHash)
	if err != nil {
		return nil, fmt.Errorf("failed to list sequences: %w", err)
	}
	defer rows.Close()

	var records []SequenceRecord
	for rows.Next() {
		var record SequenceRecord
		if err := rows.Scan(
			&record.ID,
			&record.PortfolioHash,
			&record.SequenceData,
			&record.PatternType,
			&record.Depth,
			&record.Priority,
			&record.Completed,
			&record.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan sequence: %w", err)
		}
		records = append(records, record)
	}

	return records, nil
}

// GetPendingSequences retrieves sequences that haven't been evaluated yet.
func (r *PlannerRepository) GetPendingSequences(
	portfolioHash string,
	limit int,
) ([]SequenceRecord, error) {
	query := `
		SELECT id, portfolio_hash, sequence_data, pattern_type, depth, priority, completed, created_at
		FROM sequences
		WHERE portfolio_hash = ? AND completed = 0
		ORDER BY priority DESC, created_at ASC
	`
	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.db.Query(query, portfolioHash)
	if err != nil {
		return nil, fmt.Errorf("failed to get pending sequences: %w", err)
	}
	defer rows.Close()

	var records []SequenceRecord
	for rows.Next() {
		var record SequenceRecord
		if err := rows.Scan(
			&record.ID,
			&record.PortfolioHash,
			&record.SequenceData,
			&record.PatternType,
			&record.Depth,
			&record.Priority,
			&record.Completed,
			&record.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan sequence: %w", err)
		}
		records = append(records, record)
	}

	return records, nil
}

// MarkSequenceCompleted marks a sequence as completed.
func (r *PlannerRepository) MarkSequenceCompleted(id int64) error {
	_, err := r.db.Exec(`UPDATE sequences SET completed = 1 WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("failed to mark sequence completed: %w", err)
	}

	r.log.Debug().Int64("id", id).Msg("Marked sequence as completed")
	return nil
}

// DeleteSequencesByPortfolioHash deletes all sequences for a portfolio hash.
func (r *PlannerRepository) DeleteSequencesByPortfolioHash(portfolioHash string) error {
	result, err := r.db.Exec(`DELETE FROM sequences WHERE portfolio_hash = ?`, portfolioHash)
	if err != nil {
		return fmt.Errorf("failed to delete sequences: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int64("rows_deleted", rowsAffected).
		Msg("Deleted sequences")

	return nil
}

// InsertEvaluation inserts a new evaluation into the database.
func (r *PlannerRepository) InsertEvaluation(
	evaluation domain.EvaluationResult,
) error {
	metricsData, err := json.Marshal(evaluation.ScoreBreakdown)
	if err != nil {
		return fmt.Errorf("failed to marshal metrics: %w", err)
	}

	// Calculate delta score (improvement over baseline)
	// For now we'll use 0.0 as delta since we don't have baseline score here
	deltaScore := 0.0

	_, err = r.db.Exec(`
		INSERT INTO evaluations (sequence_hash, portfolio_hash, end_score, delta_score, metrics, completed, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, evaluation.SequenceHash, evaluation.PortfolioHash, evaluation.EndScore, deltaScore,
		string(metricsData), true, time.Now())

	if err != nil {
		return fmt.Errorf("failed to insert evaluation: %w", err)
	}

	r.log.Debug().
		Str("sequence_hash", evaluation.SequenceHash).
		Str("portfolio_hash", evaluation.PortfolioHash).
		Float64("end_score", evaluation.EndScore).
		Msg("Inserted evaluation")

	return nil
}

// GetEvaluation retrieves an evaluation by sequence hash.
func (r *PlannerRepository) GetEvaluation(sequenceHash string) (*domain.EvaluationResult, error) {
	var record EvaluationRecord
	err := r.db.QueryRow(`
		SELECT id, sequence_hash, portfolio_hash, end_score, delta_score, metrics, completed, created_at
		FROM evaluations
		WHERE sequence_hash = ?
	`, sequenceHash).Scan(
		&record.ID,
		&record.SequenceHash,
		&record.PortfolioHash,
		&record.EndScore,
		&record.DeltaScore,
		&record.Metrics,
		&record.Completed,
		&record.CreatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get evaluation: %w", err)
	}

	var scoreBreakdown map[string]float64
	if err := json.Unmarshal([]byte(record.Metrics), &scoreBreakdown); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metrics: %w", err)
	}

	evaluation := &domain.EvaluationResult{
		SequenceHash:   record.SequenceHash,
		EndScore:       record.EndScore,
		ScoreBreakdown: scoreBreakdown,
	}

	return evaluation, nil
}

// ListEvaluationsByPortfolioHash retrieves all evaluations for a portfolio hash.
func (r *PlannerRepository) ListEvaluationsByPortfolioHash(
	portfolioHash string,
) ([]EvaluationRecord, error) {
	rows, err := r.db.Query(`
		SELECT id, sequence_hash, portfolio_hash, end_score, delta_score, metrics, completed, created_at
		FROM evaluations
		WHERE portfolio_hash = ?
		ORDER BY end_score DESC, created_at DESC
	`, portfolioHash)

	if err != nil {
		return nil, fmt.Errorf("failed to list evaluations: %w", err)
	}
	defer rows.Close()

	var records []EvaluationRecord
	for rows.Next() {
		var record EvaluationRecord
		if err := rows.Scan(
			&record.ID,
			&record.SequenceHash,
			&record.PortfolioHash,
			&record.EndScore,
			&record.DeltaScore,
			&record.Metrics,
			&record.Completed,
			&record.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan evaluation: %w", err)
		}
		records = append(records, record)
	}

	return records, nil
}

// DeleteEvaluationsByPortfolioHash deletes all evaluations for a portfolio hash.
func (r *PlannerRepository) DeleteEvaluationsByPortfolioHash(portfolioHash string) error {
	result, err := r.db.Exec(`DELETE FROM evaluations WHERE portfolio_hash = ?`, portfolioHash)
	if err != nil {
		return fmt.Errorf("failed to delete evaluations: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int64("rows_deleted", rowsAffected).
		Msg("Deleted evaluations")

	return nil
}

// UpsertBestResult inserts or updates the best result for a portfolio hash.
func (r *PlannerRepository) UpsertBestResult(
	portfolioHash string,
	result domain.EvaluationResult,
	sequence domain.ActionSequence,
) error {
	// Marshal the sequence (plan data)
	sequenceData, err := json.Marshal(sequence)
	if err != nil {
		return fmt.Errorf("failed to marshal sequence: %w", err)
	}

	// Check if a record exists
	var existingID int64
	err = r.db.QueryRow(`
		SELECT id FROM best_result WHERE portfolio_hash = ?
	`, portfolioHash).Scan(&existingID)

	now := time.Now()

	if err == sql.ErrNoRows {
		// Insert new record
		_, err = r.db.Exec(`
			INSERT INTO best_result (portfolio_hash, sequence_hash, plan_data, score, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, ?)
		`, portfolioHash, result.SequenceHash, string(sequenceData), result.EndScore, now, now)

		if err != nil {
			return fmt.Errorf("failed to insert best result: %w", err)
		}

		r.log.Info().
			Str("portfolio_hash", portfolioHash).
			Str("sequence_hash", result.SequenceHash).
			Float64("score", result.EndScore).
			Msg("Inserted best result")
	} else if err == nil {
		// Update existing record
		_, err = r.db.Exec(`
			UPDATE best_result
			SET sequence_hash = ?, plan_data = ?, score = ?, updated_at = ?
			WHERE portfolio_hash = ?
		`, result.SequenceHash, string(sequenceData), result.EndScore, now, portfolioHash)

		if err != nil {
			return fmt.Errorf("failed to update best result: %w", err)
		}

		r.log.Info().
			Str("portfolio_hash", portfolioHash).
			Str("sequence_hash", result.SequenceHash).
			Float64("score", result.EndScore).
			Msg("Updated best result")
	} else {
		return fmt.Errorf("failed to check existing best result: %w", err)
	}

	return nil
}

// GetBestResult retrieves the best result for a portfolio hash.
func (r *PlannerRepository) GetBestResult(portfolioHash string) (*domain.HolisticPlan, error) {
	var record BestResultRecord
	err := r.db.QueryRow(`
		SELECT id, portfolio_hash, sequence_hash, plan_data, score, created_at, updated_at
		FROM best_result
		WHERE portfolio_hash = ?
	`, portfolioHash).Scan(
		&record.ID,
		&record.PortfolioHash,
		&record.SequenceHash,
		&record.PlanData,
		&record.Score,
		&record.CreatedAt,
		&record.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get best result: %w", err)
	}

	var plan domain.HolisticPlan
	if err := json.Unmarshal([]byte(record.PlanData), &plan); err != nil {
		return nil, fmt.Errorf("failed to unmarshal plan: %w", err)
	}

	return &plan, nil
}

// DeleteBestResult deletes the best result for a portfolio hash.
func (r *PlannerRepository) DeleteBestResult(portfolioHash string) error {
	_, err := r.db.Exec(`DELETE FROM best_result WHERE portfolio_hash = ?`, portfolioHash)
	if err != nil {
		return fmt.Errorf("failed to delete best result: %w", err)
	}

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Msg("Deleted best result")

	return nil
}

// CountSequences returns the total number of sequences for a portfolio hash.
func (r *PlannerRepository) CountSequences(portfolioHash string) (int, error) {
	var count int
	err := r.db.QueryRow(`
		SELECT COUNT(*) FROM sequences WHERE portfolio_hash = ?
	`, portfolioHash).Scan(&count)

	if err != nil {
		return 0, fmt.Errorf("failed to count sequences: %w", err)
	}

	return count, nil
}

// CountPendingSequences returns the number of pending sequences for a portfolio hash.
func (r *PlannerRepository) CountPendingSequences(portfolioHash string) (int, error) {
	var count int
	err := r.db.QueryRow(`
		SELECT COUNT(*) FROM sequences WHERE portfolio_hash = ? AND completed = 0
	`, portfolioHash).Scan(&count)

	if err != nil {
		return 0, fmt.Errorf("failed to count pending sequences: %w", err)
	}

	return count, nil
}

// CountEvaluations returns the total number of evaluations for a portfolio hash.
func (r *PlannerRepository) CountEvaluations(portfolioHash string) (int, error) {
	var count int
	err := r.db.QueryRow(`
		SELECT COUNT(*) FROM evaluations WHERE portfolio_hash = ?
	`, portfolioHash).Scan(&count)

	if err != nil {
		return 0, fmt.Errorf("failed to count evaluations: %w", err)
	}

	return count, nil
}
