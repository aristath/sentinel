package scheduler

import (
	"fmt"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// BuildOpportunityContextJob builds the opportunity context from current portfolio state
// using the unified OpportunityContextBuilder service.
type BuildOpportunityContextJob struct {
	JobBase
	log                    zerolog.Logger
	contextBuilder         *services.OpportunityContextBuilder
	optimizerTargetWeights map[string]float64
	opportunityContext     *planningdomain.OpportunityContext
}

// NewBuildOpportunityContextJob creates a new BuildOpportunityContextJob
func NewBuildOpportunityContextJob(
	contextBuilder *services.OpportunityContextBuilder,
) *BuildOpportunityContextJob {
	return &BuildOpportunityContextJob{
		log:            zerolog.Nop(),
		contextBuilder: contextBuilder,
	}
}

// SetLogger sets the logger for the job
func (j *BuildOpportunityContextJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// SetOptimizerTargetWeights sets the optimizer target weights
// These weights are applied to the context after building
func (j *BuildOpportunityContextJob) SetOptimizerTargetWeights(weights map[string]float64) {
	j.optimizerTargetWeights = weights
}

// GetOpportunityContext returns the built opportunity context
func (j *BuildOpportunityContextJob) GetOpportunityContext() *planningdomain.OpportunityContext {
	return j.opportunityContext
}

// Name returns the job name
func (j *BuildOpportunityContextJob) Name() string {
	return "build_opportunity_context"
}

// Run executes the build opportunity context job
func (j *BuildOpportunityContextJob) Run() error {
	j.log.Debug().Msg("Building opportunity context using unified builder")

	// Check for nil builder
	if j.contextBuilder == nil {
		return fmt.Errorf("context builder is nil")
	}

	// Build context using the unified builder
	// Pass optimizer weights directly to Build() instead of applying post-hoc
	ctx, err := j.contextBuilder.Build(j.optimizerTargetWeights)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to build opportunity context")
		return fmt.Errorf("failed to build opportunity context: %w", err)
	}

	// Log weights application if present
	if len(j.optimizerTargetWeights) > 0 {
		j.log.Debug().Int("count", len(j.optimizerTargetWeights)).Msg("Applied optimizer target weights")
	}

	// Store the context
	j.opportunityContext = ctx

	j.log.Info().
		Int("positions", len(ctx.EnrichedPositions)).
		Int("securities", len(ctx.Securities)).
		Float64("total_value", ctx.TotalPortfolioValueEUR).
		Float64("available_cash", ctx.AvailableCashEUR).
		Int("recently_sold", len(ctx.RecentlySoldISINs)).
		Int("recently_bought", len(ctx.RecentlyBoughtISINs)).
		Msg("Opportunity context built successfully")

	return nil
}
