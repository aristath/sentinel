// Package planning provides portfolio planning and strategy generation functionality.
package planning

import (
	"database/sql"
	"fmt"
	"math"
	"strings"
	"sync"
	"time"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
)

// RecommendationRepository handles CRUD operations for recommendations
//
// Provides full CRUD operations for trade recommendations.
// Reference: app/repositories/recommendation.py (Python)
// Database: cache.db (recommendations table)
type RecommendationRepository struct {
	db                    *sql.DB                                         // cache.db
	rejectedOpportunities map[string][]planningdomain.RejectedOpportunity // key: portfolioHash (in-memory)
	preFilteredSecurities map[string][]planningdomain.PreFilteredSecurity // key: portfolioHash (in-memory)
	rejectedSequences     map[string][]planningdomain.RejectedSequence    // key: portfolioHash (in-memory)
	rejectedMu            sync.RWMutex
	preFilteredMu         sync.RWMutex
	rejectedSeqMu         sync.RWMutex
	log                   zerolog.Logger
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
	Status                string // "pending", "executed", "rejected", "expired", "failed"
	PortfolioHash         string
	CreatedAt             time.Time
	UpdatedAt             time.Time
	ExecutedAt            *time.Time
	RetryCount            int        // Number of execution attempts
	LastAttemptAt         *time.Time // Last execution attempt timestamp
	FailureReason         string     // Reason for last failure
}

// NewRecommendationRepository creates a new recommendation repository
func NewRecommendationRepository(db *sql.DB, log zerolog.Logger) *RecommendationRepository {
	return &RecommendationRepository{
		db:                    db,
		rejectedOpportunities: make(map[string][]planningdomain.RejectedOpportunity),
		preFilteredSecurities: make(map[string][]planningdomain.PreFilteredSecurity),
		rejectedSequences:     make(map[string][]planningdomain.RejectedSequence),
		log:                   log.With().Str("repository", "recommendation").Logger(),
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
// startingCashEUR is the starting cash balance in EUR (optional, defaults to 0 if not provided)
func (r *RecommendationRepository) GetRecommendationsAsPlan(getEvaluatedCount func(portfolioHash string) (int, error), startingCashEUR float64) (map[string]interface{}, error) {
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
	var portfolioHash string

	// Calculate per-step cash by iterating through steps in order and tracking running cash balance
	currentCash := startingCashEUR

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

		// Calculate available cash before this step
		availableCashBefore := currentCash

		// Calculate available cash after this step
		availableCashAfter := currentCash
		if rec.Side == "BUY" {
			availableCashAfter -= rec.EstimatedValue
			currentCash = availableCashAfter
		} else if rec.Side == "SELL" {
			availableCashAfter += rec.EstimatedValue
			currentCash = availableCashAfter
		}

		// Round price to 2 decimals for display
		roundedPrice := math.Round(rec.EstimatedPrice*100) / 100

		step := map[string]interface{}{
			"step":                   stepNum,
			"symbol":                 rec.Symbol,
			"name":                   rec.Name,
			"side":                   rec.Side,
			"quantity":               rec.Quantity,
			"estimated_price":        roundedPrice,
			"estimated_value":        rec.EstimatedValue,
			"currency":               rec.Currency,
			"reason":                 rec.Reason,
			"portfolio_score_before": rec.CurrentPortfolioScore,
			"portfolio_score_after":  rec.NewPortfolioScore,
			"score_change":           rec.ScoreChange,
			"available_cash_before":  availableCashBefore,
			"available_cash_after":   availableCashAfter,
			"is_emergency":           isEmergencyReason(rec.Reason),
		}

		steps = append(steps, step)
	}

	finalCash := currentCash

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

	// Get rejected opportunities for this portfolio hash
	var rejectedOpportunities interface{} = nil
	r.rejectedMu.RLock()
	if rejected, exists := r.rejectedOpportunities[portfolioHash]; exists && len(rejected) > 0 {
		rejectedOpportunities = rejected
	}
	r.rejectedMu.RUnlock()

	// Get pre-filtered securities for this portfolio hash
	var preFilteredSecurities interface{} = nil
	r.preFilteredMu.RLock()
	if preFiltered, exists := r.preFilteredSecurities[portfolioHash]; exists && len(preFiltered) > 0 {
		preFilteredSecurities = preFiltered
	}
	r.preFilteredMu.RUnlock()

	// Get rejected sequences for this portfolio hash
	var rejectedSequences interface{} = nil
	r.rejectedSeqMu.RLock()
	if rejected, exists := r.rejectedSequences[portfolioHash]; exists && len(rejected) > 0 {
		rejectedSequences = rejected
	}
	r.rejectedSeqMu.RUnlock()

	// Build response matching frontend expectations
	response := map[string]interface{}{
		"steps":                   steps,
		"current_score":           currentScore,
		"end_state_score":         endScore,
		"total_score_improvement": totalScoreImprovement,
		"final_available_cash":    finalCash,
		"evaluated_count":         evaluatedCount,
	}

	if rejectedOpportunities != nil {
		response["rejected_opportunities"] = rejectedOpportunities
	}

	if preFilteredSecurities != nil {
		response["pre_filtered_securities"] = preFilteredSecurities
	}

	if rejectedSequences != nil {
		response["rejected_sequences"] = rejectedSequences
	}

	return response, nil
}

// RecordFailedAttempt increments retry count and records failure reason
// This should be called when a trade execution fails
func (r *RecommendationRepository) RecordFailedAttempt(recUUID string, failureReason string) error {
	now := time.Now().Unix()
	_, err := r.db.Exec(`
		UPDATE recommendations
		SET retry_count = retry_count + 1,
			last_attempt_at = ?,
			failure_reason = ?,
			updated_at = ?
		WHERE uuid = ?
	`,
		now,
		failureReason,
		now,
		recUUID,
	)

	if err != nil {
		return fmt.Errorf("failed to record failed attempt: %w", err)
	}

	return nil
}

// MarkFailed marks a recommendation as permanently failed (exceeded max retries)
func (r *RecommendationRepository) MarkFailed(recUUID string, failureReason string) error {
	now := time.Now().Unix()
	_, err := r.db.Exec(`
		UPDATE recommendations
		SET status = 'failed',
			failure_reason = ?,
			updated_at = ?
		WHERE uuid = ?
	`,
		failureReason,
		now,
		recUUID,
	)

	if err != nil {
		return fmt.Errorf("failed to mark recommendation as failed: %w", err)
	}

	r.log.Warn().
		Str("uuid", recUUID).
		Str("reason", failureReason).
		Msg("Recommendation marked as permanently failed")

	return nil
}

// StorePlan stores a complete trading plan as recommendations
// This method converts plan steps to recommendations and dismisses old ones
// NOTE: This database-backed implementation is deprecated - use InMemoryRecommendationRepository
func (r *RecommendationRepository) StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if plan == nil {
		return fmt.Errorf("plan cannot be nil")
	}

	// Note: Rejected opportunities are stored separately by the rebalancing service/planner
	// They persist along with the plan and are returned in GetRecommendationsAsPlan

	// If plan has no steps, dismiss all pending recommendations
	if len(plan.Steps) == 0 {
		_, _ = r.DismissAllPending()
		return nil
	}

	// Dismiss all existing pending recommendations before storing new plan
	_, _ = r.DismissAllPending()

	// Convert each step to a recommendation
	for stepIdx, step := range plan.Steps {
		rec := Recommendation{
			Symbol:                step.Symbol,
			Name:                  step.Name,
			Side:                  step.Side,
			Quantity:              float64(step.Quantity),
			EstimatedPrice:        step.EstimatedPrice,
			EstimatedValue:        step.EstimatedValue,
			Reason:                step.Reason,
			Currency:              step.Currency,
			Priority:              float64(stepIdx),
			CurrentPortfolioScore: plan.CurrentScore,
			NewPortfolioScore:     plan.EndStateScore,
			ScoreChange:           plan.Improvement,
			Status:                "pending",
			PortfolioHash:         portfolioHash,
		}

		if _, err := r.CreateOrUpdate(rec); err != nil {
			return fmt.Errorf("failed to create recommendation for step %d: %w", stepIdx, err)
		}
	}

	r.log.Info().
		Int("step_count", len(plan.Steps)).
		Str("portfolio_hash", portfolioHash).
		Msg("Stored plan as recommendations")

	return nil
}

// DeleteOlderThan deletes recommendations older than the specified duration
// Returns the count of deleted recommendations
// NOTE: This database-backed implementation is deprecated - use InMemoryRecommendationRepository
func (r *RecommendationRepository) DeleteOlderThan(maxAge time.Duration) (int, error) {
	cutoff := time.Now().UTC().Add(-maxAge).Unix()

	result, err := r.db.Exec(`
		DELETE FROM recommendations
		WHERE created_at < ?
	`, cutoff)

	if err != nil {
		return 0, fmt.Errorf("failed to delete old recommendations: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return 0, fmt.Errorf("failed to get rows affected: %w", err)
	}

	count := int(rowsAffected)
	if count > 0 {
		r.log.Info().
			Int("deleted_count", count).
			Dur("max_age", maxAge).
			Msg("Deleted stale recommendations")
	}

	return count, nil
}

// StoreRejectedOpportunities stores rejected opportunities for a portfolio hash (in-memory)
// NOTE: Rejected opportunities stay in-memory per the design
func (r *RecommendationRepository) StoreRejectedOpportunities(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error {
	r.rejectedMu.Lock()
	defer r.rejectedMu.Unlock()

	r.rejectedOpportunities[portfolioHash] = rejected

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("rejected_count", len(rejected)).
		Msg("Stored rejected opportunities")

	return nil
}

// StorePreFilteredSecurities stores pre-filtered securities for a portfolio hash (in-memory)
// Pre-filtered securities are those excluded before reaching the opportunity stage
func (r *RecommendationRepository) StorePreFilteredSecurities(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error {
	r.preFilteredMu.Lock()
	defer r.preFilteredMu.Unlock()

	r.preFilteredSecurities[portfolioHash] = preFiltered

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("pre_filtered_count", len(preFiltered)).
		Msg("Stored pre-filtered securities")

	return nil
}

// GetPreFilteredSecurities retrieves pre-filtered securities for a portfolio hash
func (r *RecommendationRepository) GetPreFilteredSecurities(portfolioHash string) []planningdomain.PreFilteredSecurity {
	r.preFilteredMu.RLock()
	defer r.preFilteredMu.RUnlock()

	if preFiltered, exists := r.preFilteredSecurities[portfolioHash]; exists {
		return preFiltered
	}
	return nil
}

// isEmergencyReason determines if a recommendation reason indicates an emergency
func isEmergencyReason(reason string) bool {
	emergencyPatterns := []string{
		"emergency",
		"negative balance",
		"margin call",
		"urgent",
		"critical",
		"risk limit",
		"stop loss",
		"forced",
	}

	reasonLower := strings.ToLower(reason)
	for _, pattern := range emergencyPatterns {
		if strings.Contains(reasonLower, pattern) {
			return true
		}
	}
	return false
}

// StoreRejectedSequences stores rejected sequences for a portfolio hash (in-memory).
// Rejected sequences are evaluated action sequences that were not selected for the final plan.
func (r *RecommendationRepository) StoreRejectedSequences(rejected []planningdomain.RejectedSequence, portfolioHash string) error {
	r.rejectedSeqMu.Lock()
	defer r.rejectedSeqMu.Unlock()

	r.rejectedSequences[portfolioHash] = rejected

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("rejected_sequences_count", len(rejected)).
		Msg("Stored rejected sequences")

	return nil
}

// GetRejectedSequences retrieves rejected sequences for a portfolio hash.
func (r *RecommendationRepository) GetRejectedSequences(portfolioHash string) []planningdomain.RejectedSequence {
	r.rejectedSeqMu.RLock()
	defer r.rejectedSeqMu.RUnlock()

	if rejected, exists := r.rejectedSequences[portfolioHash]; exists {
		return rejected
	}
	return nil
}
