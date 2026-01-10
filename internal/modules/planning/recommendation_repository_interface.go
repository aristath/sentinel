package planning

import (
	"time"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
)

// RecommendationRepositoryInterface defines the contract for recommendation repository operations
type RecommendationRepositoryInterface interface {
	// CreateOrUpdate creates or updates a recommendation
	CreateOrUpdate(rec Recommendation) (string, error)

	// FindMatchingForExecution finds recommendations matching execution criteria
	FindMatchingForExecution(symbol, side, portfolioHash string) ([]Recommendation, error)

	// MarkExecuted marks a recommendation as executed
	MarkExecuted(recUUID string) error

	// CountPendingBySide returns count of pending recommendations by side (buy/sell)
	CountPendingBySide() (buyCount int, sellCount int, err error)

	// DismissAllByPortfolioHash dismisses all recommendations for a portfolio hash
	DismissAllByPortfolioHash(portfolioHash string) (int, error)

	// DismissAllPending dismisses all pending recommendations
	DismissAllPending() (int, error)

	// GetPendingRecommendations retrieves pending recommendations with optional limit
	GetPendingRecommendations(limit int) ([]Recommendation, error)

	// GetRecommendationsAsPlan returns recommendations formatted as a plan
	// startingCashEUR is the starting cash balance in EUR (optional, defaults to 0 if not provided)
	GetRecommendationsAsPlan(getEvaluatedCount func(portfolioHash string) (int, error), startingCashEUR float64) (map[string]interface{}, error)

	// StorePlan stores a complete trading plan as recommendations
	// Used by StoreRecommendationsJob to convert plans to actionable recommendations
	StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error

	// StoreRejectedOpportunities stores rejected opportunities for a portfolio hash
	// Used to track why opportunities were not selected in the final plan
	StoreRejectedOpportunities(rejected []planningdomain.RejectedOpportunity, portfolioHash string) error

	// DeleteOlderThan deletes recommendations older than the specified duration
	// Used by RecommendationGCJob for garbage collection (24h TTL)
	DeleteOlderThan(maxAge time.Duration) (int, error)

	// RecordFailedAttempt increments retry count and records failure reason
	// Used by EventBasedTradingJob when a trade execution fails but can be retried
	RecordFailedAttempt(recUUID string, failureReason string) error

	// MarkFailed marks a recommendation as permanently failed (exceeded max retries)
	// Used by EventBasedTradingJob when a trade cannot be executed after multiple attempts
	MarkFailed(recUUID string, failureReason string) error
}

// Compile-time check that RecommendationRepository implements RecommendationRepositoryInterface
var _ RecommendationRepositoryInterface = (*RecommendationRepository)(nil)

// Compile-time check that InMemoryRecommendationRepository implements RecommendationRepositoryInterface
var _ RecommendationRepositoryInterface = (*InMemoryRecommendationRepository)(nil)
