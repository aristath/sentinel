package planning

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
)

type InMemoryRecommendationRepository struct {
	recommendations       map[string]*Recommendation
	rejectedOpportunities map[string][]planningdomain.RejectedOpportunity // key: portfolioHash
	preFilteredSecurities map[string][]planningdomain.PreFilteredSecurity // key: portfolioHash
	rejectedSequences     map[string][]planningdomain.RejectedSequence    // key: portfolioHash
	mu                    sync.RWMutex
	log                   zerolog.Logger
}

func NewInMemoryRecommendationRepository(log zerolog.Logger) *InMemoryRecommendationRepository {
	return &InMemoryRecommendationRepository{
		recommendations:       make(map[string]*Recommendation),
		rejectedOpportunities: make(map[string][]planningdomain.RejectedOpportunity),
		preFilteredSecurities: make(map[string][]planningdomain.PreFilteredSecurity),
		rejectedSequences:     make(map[string][]planningdomain.RejectedSequence),
		log:                   log.With().Str("repository", "recommendation_inmemory").Logger(),
	}
}

func (r *InMemoryRecommendationRepository) CreateOrUpdate(rec Recommendation) (string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	var existing *Recommendation
	for _, existingRec := range r.recommendations {
		if existingRec.Symbol == rec.Symbol &&
			existingRec.Side == rec.Side &&
			existingRec.Reason == rec.Reason &&
			existingRec.PortfolioHash == rec.PortfolioHash {
			existing = existingRec
			break
		}
	}

	now := time.Now().UTC()

	if existing != nil {
		existing.Name = rec.Name
		existing.Quantity = rec.Quantity
		existing.EstimatedPrice = rec.EstimatedPrice
		existing.EstimatedValue = rec.EstimatedValue
		existing.Currency = rec.Currency
		existing.Priority = rec.Priority
		existing.CurrentPortfolioScore = rec.CurrentPortfolioScore
		existing.NewPortfolioScore = rec.NewPortfolioScore
		existing.ScoreChange = rec.ScoreChange
		existing.UpdatedAt = now
		return existing.UUID, nil
	}

	newUUID := uuid.New().String()
	newRec := &Recommendation{
		UUID:                  newUUID,
		Symbol:                rec.Symbol,
		Name:                  rec.Name,
		Side:                  rec.Side,
		Quantity:              rec.Quantity,
		EstimatedPrice:        rec.EstimatedPrice,
		EstimatedValue:        rec.EstimatedValue,
		Reason:                rec.Reason,
		Currency:              rec.Currency,
		Priority:              rec.Priority,
		CurrentPortfolioScore: rec.CurrentPortfolioScore,
		NewPortfolioScore:     rec.NewPortfolioScore,
		ScoreChange:           rec.ScoreChange,
		Status:                "pending",
		PortfolioHash:         rec.PortfolioHash,
		CreatedAt:             now,
		UpdatedAt:             now,
		RetryCount:            0,
	}

	r.recommendations[newUUID] = newRec
	return newUUID, nil
}

func (r *InMemoryRecommendationRepository) FindMatchingForExecution(symbol, side, portfolioHash string) ([]Recommendation, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	matches := make([]Recommendation, 0)
	for _, rec := range r.recommendations {
		if rec.Symbol == symbol && rec.Side == side && rec.PortfolioHash == portfolioHash && rec.Status == "pending" {
			matches = append(matches, *rec)
		}
	}
	return matches, nil
}

func (r *InMemoryRecommendationRepository) MarkExecuted(recUUID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec, exists := r.recommendations[recUUID]
	if !exists {
		return fmt.Errorf("recommendation not found: %s", recUUID)
	}

	now := time.Now().UTC()
	rec.Status = "executed"
	rec.ExecutedAt = &now
	rec.UpdatedAt = now
	return nil
}

func (r *InMemoryRecommendationRepository) CountPendingBySide() (buyCount int, sellCount int, err error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for _, rec := range r.recommendations {
		if rec.Status == "pending" {
			if rec.Side == "BUY" {
				buyCount++
			} else if rec.Side == "SELL" {
				sellCount++
			}
		}
	}
	return buyCount, sellCount, nil
}

func (r *InMemoryRecommendationRepository) DismissAllByPortfolioHash(portfolioHash string) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	count := 0
	now := time.Now().UTC()

	for _, rec := range r.recommendations {
		if rec.PortfolioHash == portfolioHash && rec.Status == "pending" {
			rec.Status = "dismissed"
			rec.UpdatedAt = now
			count++
		}
	}
	return count, nil
}

func (r *InMemoryRecommendationRepository) DismissAllPending() (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	count := 0
	now := time.Now().UTC()

	for _, rec := range r.recommendations {
		if rec.Status == "pending" {
			rec.Status = "dismissed"
			rec.UpdatedAt = now
			count++
		}
	}
	return count, nil
}

func (r *InMemoryRecommendationRepository) GetPendingRecommendations(limit int) ([]Recommendation, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// Pre-allocate with reasonable capacity (not all recommendations are pending)
	pending := make([]Recommendation, 0)
	for _, rec := range r.recommendations {
		if rec.Status == "pending" {
			pending = append(pending, *rec)
		}
	}

	sort.Slice(pending, func(i, j int) bool {
		if pending[i].Priority == pending[j].Priority {
			return pending[i].CreatedAt.Before(pending[j].CreatedAt)
		}
		return pending[i].Priority < pending[j].Priority
	})

	if limit > 0 && len(pending) > limit {
		pending = pending[:limit]
	}

	return pending, nil
}

func (r *InMemoryRecommendationRepository) GetRecommendationsAsPlan(getEvaluatedCount func(portfolioHash string) (int, error), startingCashEUR float64) (map[string]interface{}, error) {
	recs, err := r.GetPendingRecommendations(0)
	if err != nil {
		return nil, fmt.Errorf("failed to get pending recommendations: %w", err)
	}

	steps := make([]map[string]interface{}, 0, len(recs))
	var totalScoreImprovement float64
	var currentScore float64
	var endScore float64
	var portfolioHash string

	currentCash := startingCashEUR

	for i, rec := range recs {
		stepNum := int(rec.Priority) + 1
		if stepNum == 0 {
			stepNum = i + 1
		}

		if i == 0 {
			currentScore = rec.CurrentPortfolioScore
			endScore = rec.NewPortfolioScore
			totalScoreImprovement = rec.ScoreChange
			portfolioHash = rec.PortfolioHash
		}

		availableCashBefore := currentCash
		availableCashAfter := currentCash
		if rec.Side == "BUY" {
			availableCashAfter -= rec.EstimatedValue
			currentCash = availableCashAfter
		} else if rec.Side == "SELL" {
			availableCashAfter += rec.EstimatedValue
			currentCash = availableCashAfter
		}

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
			"is_emergency":           IsEmergencyReason(rec.Reason),
		}

		steps = append(steps, step)
	}

	finalCash := currentCash

	var evaluatedCount interface{} = nil
	if getEvaluatedCount != nil && portfolioHash != "" {
		count, err := getEvaluatedCount(portfolioHash)
		if err != nil {
			r.log.Warn().Err(err).Str("portfolio_hash", portfolioHash).Msg("Failed to get evaluated count")
		} else {
			evaluatedCount = count
		}
	}

	// Get rejected opportunities and pre-filtered securities
	// When there are no recommendations, we need to find the latest portfolioHash from stored data
	r.mu.RLock()
	if portfolioHash == "" {
		// Find the most recently used portfolioHash from pre-filtered or rejected data
		for hash := range r.preFilteredSecurities {
			portfolioHash = hash
			break
		}
		if portfolioHash == "" {
			for hash := range r.rejectedOpportunities {
				portfolioHash = hash
				break
			}
		}
	}

	var rejectedOpportunities interface{} = nil
	if rejected, exists := r.rejectedOpportunities[portfolioHash]; exists && len(rejected) > 0 {
		rejectedOpportunities = rejected
	}

	var preFilteredSecurities interface{} = nil
	if preFiltered, exists := r.preFilteredSecurities[portfolioHash]; exists && len(preFiltered) > 0 {
		preFilteredSecurities = preFiltered
	}

	var rejectedSequences interface{} = nil
	if rejected, exists := r.rejectedSequences[portfolioHash]; exists && len(rejected) > 0 {
		rejectedSequences = rejected
	}
	r.mu.RUnlock()

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

func (r *InMemoryRecommendationRepository) RecordFailedAttempt(recUUID string, failureReason string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec, exists := r.recommendations[recUUID]
	if !exists {
		return fmt.Errorf("recommendation not found: %s", recUUID)
	}

	now := time.Now().UTC()
	rec.RetryCount++
	rec.LastAttemptAt = &now
	rec.FailureReason = failureReason
	rec.UpdatedAt = now
	return nil
}

func (r *InMemoryRecommendationRepository) MarkFailed(recUUID string, failureReason string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	rec, exists := r.recommendations[recUUID]
	if !exists {
		return fmt.Errorf("recommendation not found: %s", recUUID)
	}

	now := time.Now().UTC()
	rec.Status = "failed"
	rec.FailureReason = failureReason
	rec.UpdatedAt = now
	return nil
}

func (r *InMemoryRecommendationRepository) StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if plan == nil || plan.Steps == nil {
		return fmt.Errorf("plan and plan.Steps cannot be nil")
	}

	// Note: Rejected opportunities are stored separately by the rebalancing service/planner
	// They persist along with the plan and are returned in GetRecommendationsAsPlan

	if len(plan.Steps) == 0 {
		if _, err := r.DismissAllPending(); err != nil {
			r.log.Warn().Err(err).Msg("Failed to dismiss pending recommendations (empty plan)")
		}
		return nil
	}

	if _, err := r.DismissAllPending(); err != nil {
		r.log.Warn().Err(err).Msg("Failed to dismiss pending recommendations before storing plan")
	}

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
			return err
		}
	}

	r.log.Info().Int("step_count", len(plan.Steps)).Str("portfolio_hash", portfolioHash).Msg("Stored plan as recommendations")
	return nil
}

func (r *InMemoryRecommendationRepository) DeleteOlderThan(maxAge time.Duration) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	count := 0
	cutoff := time.Now().UTC().Add(-maxAge)

	for uuid, rec := range r.recommendations {
		if rec.CreatedAt.Before(cutoff) {
			delete(r.recommendations, uuid)
			count++
		}
	}

	if count > 0 {
		r.log.Info().Int("deleted_count", count).Dur("max_age", maxAge).Msg("Deleted stale recommendations")
	}

	return count, nil
}

func (r *InMemoryRecommendationRepository) StoreRejectedOpportunities(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.rejectedOpportunities[portfolioHash] = rejected

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("rejected_count", len(rejected)).
		Msg("Stored rejected opportunities")

	return nil
}

func (r *InMemoryRecommendationRepository) StorePreFilteredSecurities(preFiltered []planningdomain.PreFilteredSecurity, portfolioHash string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.preFilteredSecurities[portfolioHash] = preFiltered

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("pre_filtered_count", len(preFiltered)).
		Msg("Stored pre-filtered securities")

	return nil
}

func (r *InMemoryRecommendationRepository) GetPreFilteredSecurities(portfolioHash string) []planningdomain.PreFilteredSecurity {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if preFiltered, exists := r.preFilteredSecurities[portfolioHash]; exists {
		return preFiltered
	}
	return nil
}

// GetRejectedOpportunities retrieves rejected opportunities for a portfolio hash (in-memory).
// Returns nil if no rejected opportunities exist for the given hash.
func (r *InMemoryRecommendationRepository) GetRejectedOpportunities(portfolioHash string) []planningdomain.RejectedOpportunity {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if rejected, exists := r.rejectedOpportunities[portfolioHash]; exists {
		return rejected
	}
	return nil
}

// StoreRejectedSequences stores rejected sequences for a portfolio hash (in-memory).
// Rejected sequences are evaluated action sequences that were not selected for the final plan.
func (r *InMemoryRecommendationRepository) StoreRejectedSequences(rejected []planningdomain.RejectedSequence, portfolioHash string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.rejectedSequences[portfolioHash] = rejected

	r.log.Info().
		Str("portfolio_hash", portfolioHash).
		Int("rejected_sequences_count", len(rejected)).
		Msg("Stored rejected sequences")

	return nil
}

// GetRejectedSequences retrieves rejected sequences for a portfolio hash.
func (r *InMemoryRecommendationRepository) GetRejectedSequences(portfolioHash string) []planningdomain.RejectedSequence {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if rejected, exists := r.rejectedSequences[portfolioHash]; exists {
		return rejected
	}
	return nil
}
