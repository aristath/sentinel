package scheduler

import (
	"fmt"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/planner"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/aristath/sentinel/internal/queue"
	"github.com/rs/zerolog"
)

// CreateTradePlanJob creates a holistic trade plan from opportunity context
type CreateTradePlanJob struct {
	JobBase
	log                      zerolog.Logger
	plannerService           PlannerServiceInterface
	configRepo               ConfigRepositoryInterface
	opportunityContext       *planningdomain.OpportunityContext
	plan                     *planningdomain.HolisticPlan
	rejectedOpportunities    []planningdomain.RejectedOpportunity
	preFilteredSecurities    []planningdomain.PreFilteredSecurity
	rejectedSequences        []planningdomain.RejectedSequence
	detailedProgressCallback progress.DetailedCallback
}

// NewCreateTradePlanJob creates a new CreateTradePlanJob
func NewCreateTradePlanJob(
	plannerService PlannerServiceInterface,
	configRepo ConfigRepositoryInterface,
) *CreateTradePlanJob {
	return &CreateTradePlanJob{
		log:            zerolog.Nop(),
		plannerService: plannerService,
		configRepo:     configRepo,
	}
}

// SetLogger sets the logger for the job
func (j *CreateTradePlanJob) SetLogger(log zerolog.Logger) {
	j.log = log
}

// SetOpportunityContext sets the opportunity context for plan creation
func (j *CreateTradePlanJob) SetOpportunityContext(ctx *planningdomain.OpportunityContext) {
	j.opportunityContext = ctx
}

// SetDetailedProgressCallback sets the detailed progress callback for rich progress reporting
func (j *CreateTradePlanJob) SetDetailedProgressCallback(callback progress.DetailedCallback) {
	j.detailedProgressCallback = callback
}

// GetPlan returns the created plan
func (j *CreateTradePlanJob) GetPlan() *planningdomain.HolisticPlan {
	return j.plan
}

// GetRejectedOpportunities returns the rejected opportunities from plan creation
func (j *CreateTradePlanJob) GetRejectedOpportunities() []planningdomain.RejectedOpportunity {
	return j.rejectedOpportunities
}

// GetPreFilteredSecurities returns the pre-filtered securities from plan creation
func (j *CreateTradePlanJob) GetPreFilteredSecurities() []planningdomain.PreFilteredSecurity {
	return j.preFilteredSecurities
}

// GetRejectedSequences returns the rejected sequences from plan creation
func (j *CreateTradePlanJob) GetRejectedSequences() []planningdomain.RejectedSequence {
	return j.rejectedSequences
}

// Name returns the job name
func (j *CreateTradePlanJob) Name() string {
	return "create_trade_plan"
}

// Run executes the create trade plan job
func (j *CreateTradePlanJob) Run() error {
	if j.plannerService == nil {
		return fmt.Errorf("planner service not available")
	}

	if j.opportunityContext == nil {
		return fmt.Errorf("opportunity context not set")
	}

	// Load planner configuration
	config, err := j.loadPlannerConfig()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to load planner config, using defaults")
		config = planningdomain.NewDefaultConfiguration()
	}

	var planResultInterface interface{}

	// Use detailed progress callback if available
	if j.detailedProgressCallback != nil {
		j.log.Debug().Msg("Using detailed progress callback for plan creation")
		planResultInterface, err = j.plannerService.CreatePlanWithDetailedProgress(j.opportunityContext, config, j.detailedProgressCallback)
	} else {
		// Fallback to legacy progress callback from the job's progress reporter
		var progressCallback progress.Callback
		if r := j.GetProgressReporter(); r != nil {
			if reporter, ok := r.(*queue.ProgressReporter); ok && reporter != nil {
				progressCallback = func(current, total int, message string) {
					reporter.Report(current, total, message)
				}
			}
		}
		planResultInterface, err = j.plannerService.CreatePlanWithRejections(j.opportunityContext, config, progressCallback)
	}

	if err != nil {
		j.log.Error().Err(err).Msg("Failed to create plan")
		return fmt.Errorf("failed to create plan: %w", err)
	}

	// Type assert to PlanResult
	planResult, ok := planResultInterface.(*planner.PlanResult)
	if !ok {
		return fmt.Errorf("plan result has invalid type: expected *planner.PlanResult")
	}

	j.plan = planResult.Plan
	j.rejectedOpportunities = planResult.RejectedOpportunities
	j.preFilteredSecurities = planResult.PreFilteredSecurities
	j.rejectedSequences = planResult.RejectedSequences

	j.log.Info().
		Int("rejected_opportunities_count", len(j.rejectedOpportunities)).
		Int("pre_filtered_count", len(j.preFilteredSecurities)).
		Int("rejected_sequences_count", len(j.rejectedSequences)).
		Msg("Successfully created trade plan")

	return nil
}

// loadPlannerConfig loads the planner configuration from the repository or uses defaults
func (j *CreateTradePlanJob) loadPlannerConfig() (*planningdomain.PlannerConfiguration, error) {
	// Try to load default config from repository
	if j.configRepo != nil {
		configInterface, err := j.configRepo.GetDefaultConfig()
		if err != nil {
			j.log.Warn().Err(err).Msg("Failed to load default config from repository, using defaults")
		} else if configInterface != nil {
			if config, ok := configInterface.(*planningdomain.PlannerConfiguration); ok {
				j.log.Debug().Str("config_name", config.Name).Msg("Loaded planner config from repository")
				return config, nil
			}
		}
	}

	// Use default config
	j.log.Debug().Msg("Using default planner configuration")
	return planningdomain.NewDefaultConfiguration(), nil
}
