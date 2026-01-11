package scheduler

import (
	"fmt"

	"github.com/aristath/sentinel/internal/events"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// StoreRecommendationsJob stores a generated plan as recommendations
type StoreRecommendationsJob struct {
	JobBase
	log                   zerolog.Logger
	eventManager          EventManagerInterface
	recommendationRepo    RecommendationRepositoryInterface
	portfolioHash         string
	plan                  *planningdomain.HolisticPlan
	rejectedOpportunities []planningdomain.RejectedOpportunity
}

// NewStoreRecommendationsJob creates a new StoreRecommendationsJob
func NewStoreRecommendationsJob(
	recommendationRepo RecommendationRepositoryInterface,
	eventManager EventManagerInterface,
	portfolioHash string,
) *StoreRecommendationsJob {
	return &StoreRecommendationsJob{
		log:                zerolog.Nop(),
		eventManager:       eventManager,
		recommendationRepo: recommendationRepo,
		portfolioHash:      portfolioHash,
	}
}

// SetLogger sets the logger for the job
func (j *StoreRecommendationsJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// SetPlan sets the plan to store
func (j *StoreRecommendationsJob) SetPlan(plan *planningdomain.HolisticPlan) {
	j.plan = plan
}

// GetPlan returns the plan to store
func (j *StoreRecommendationsJob) GetPlan() *planningdomain.HolisticPlan {
	return j.plan
}

// SetPortfolioHash sets the portfolio hash
func (j *StoreRecommendationsJob) SetPortfolioHash(hash string) {
	j.portfolioHash = hash
}

// SetRejectedOpportunities sets the rejected opportunities to store
func (j *StoreRecommendationsJob) SetRejectedOpportunities(rejected []planningdomain.RejectedOpportunity) {
	j.rejectedOpportunities = rejected
}

// Name returns the job name
func (j *StoreRecommendationsJob) Name() string {
	return "store_recommendations"
}

// Run executes the store recommendations job
func (j *StoreRecommendationsJob) Run() error {
	if j.recommendationRepo == nil {
		return fmt.Errorf("recommendation repository not available")
	}

	if j.plan == nil {
		return fmt.Errorf("plan not set")
	}

	// Store rejected opportunities first (if available)
	if len(j.rejectedOpportunities) > 0 && j.portfolioHash != "" {
		if err := j.recommendationRepo.StoreRejectedOpportunities(j.rejectedOpportunities, j.portfolioHash); err != nil {
			j.log.Warn().Err(err).Msg("Failed to store rejected opportunities")
			// Don't fail - continue to store plan
		} else {
			j.log.Info().
				Int("rejected_count", len(j.rejectedOpportunities)).
				Str("portfolio_hash", j.portfolioHash).
				Msg("Stored rejected opportunities")
		}
	}

	err := j.recommendationRepo.StorePlan(j.plan, j.portfolioHash)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to store plan")
		return fmt.Errorf("failed to store plan: %w", err)
	}

	j.log.Info().
		Str("portfolio_hash", j.portfolioHash).
		Int("steps", len(j.plan.Steps)).
		Msg("Successfully stored recommendations")

	// Emit event to notify UI that recommendations are ready
	if j.eventManager != nil && len(j.plan.Steps) > 0 {
		j.eventManager.EmitTyped(events.RecommendationsReady, "planner", &events.RecommendationsReadyData{
			PortfolioHash: j.portfolioHash,
			Count:         len(j.plan.Steps),
		})
		j.log.Debug().
			Str("portfolio_hash", j.portfolioHash).
			Int("count", len(j.plan.Steps)).
			Msg("Emitted RECOMMENDATIONS_READY event")
	}

	return nil
}
