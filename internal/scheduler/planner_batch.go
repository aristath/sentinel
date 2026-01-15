package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/planning"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/queue"
	"github.com/rs/zerolog"
)

// StageInfo represents a stage in the planner batch execution
type StageInfo struct {
	Name       string  `json:"name"`
	Status     string  `json:"status"` // "pending", "running", "completed", "failed"
	DurationMs float64 `json:"duration_ms,omitempty"`
}

// PlannerBatchJob orchestrates individual planning jobs to generate trading recommendations
type PlannerBatchJob struct {
	JobBase
	log                zerolog.Logger
	eventManager       EventManagerInterface
	recommendationRepo planning.RecommendationRepositoryInterface
	plannerRepo        planningrepo.PlannerRepositoryInterface
	// Individual planning jobs
	generatePortfolioHashJob   Job
	getOptimizerWeightsJob     Job
	buildOpportunityContextJob Job
	createTradePlanJob         Job
	storeRecommendationsJob    Job
}

// PlannerBatchConfig holds configuration for planner batch job
type PlannerBatchConfig struct {
	Log                        zerolog.Logger
	EventManager               EventManagerInterface
	RecommendationRepo         planning.RecommendationRepositoryInterface
	PlannerRepo                planningrepo.PlannerRepositoryInterface
	GeneratePortfolioHashJob   Job
	GetOptimizerWeightsJob     Job
	BuildOpportunityContextJob Job
	CreateTradePlanJob         Job
	StoreRecommendationsJob    Job
}

// NewPlannerBatchJob creates a new planner batch job
func NewPlannerBatchJob(cfg PlannerBatchConfig) *PlannerBatchJob {
	return &PlannerBatchJob{
		log:                        cfg.Log.With().Str("job", "planner_batch").Logger(),
		eventManager:               cfg.EventManager,
		recommendationRepo:         cfg.RecommendationRepo,
		plannerRepo:                cfg.PlannerRepo,
		generatePortfolioHashJob:   cfg.GeneratePortfolioHashJob,
		getOptimizerWeightsJob:     cfg.GetOptimizerWeightsJob,
		buildOpportunityContextJob: cfg.BuildOpportunityContextJob,
		createTradePlanJob:         cfg.CreateTradePlanJob,
		storeRecommendationsJob:    cfg.StoreRecommendationsJob,
	}
}

// Name returns the job name
func (j *PlannerBatchJob) Name() string {
	return "planner_batch"
}

// Run executes the planner batch job by orchestrating individual planning jobs
func (j *PlannerBatchJob) Run() error {
	j.log.Info().Msg("Starting planner batch generation (triggered by state change)")
	startTime := time.Now()

	// ALWAYS invalidate when running (we only run when state changed)
	j.log.Info().Msg("Invalidating all sequences, evaluations, and recommendations")

	// Dismiss all pending recommendations
	if j.recommendationRepo != nil {
		count, _ := j.recommendationRepo.DismissAllPending()
		j.log.Info().Int("count", count).Msg("Dismissed pending recommendations")
	}

	// Delete all sequences and evaluations
	if j.plannerRepo != nil {
		_ = j.plannerRepo.DeleteAllSequences()
		_ = j.plannerRepo.DeleteAllEvaluations()
		_ = j.plannerRepo.DeleteAllBestResults()
		j.log.Info().Msg("Cleared all sequences and evaluations")
	}

	var reporter *queue.ProgressReporter
	if r := j.GetProgressReporter(); r != nil {
		reporter, _ = r.(*queue.ProgressReporter)
	}
	const totalSteps = 5

	// Initialize stage tracking
	stages := []StageInfo{
		{Name: "Portfolio hash", Status: "pending"},
		{Name: "Optimizer weights", Status: "pending"},
		{Name: "Opportunity context", Status: "pending"},
		{Name: "Create trade plan", Status: "pending"},
		{Name: "Store recommendations", Status: "pending"},
	}

	// Helper to report current stages state
	reportStages := func(current int, message string) {
		if reporter != nil {
			stagesAsAny := make([]interface{}, len(stages))
			for i, s := range stages {
				stagesAsAny[i] = s
			}
			reporter.ReportWithDetails(current, totalSteps, message, "planner_batch", stages[current-1].Name, map[string]interface{}{
				"stages": stagesAsAny,
			})
		}
	}

	// Helper to mark stage as running and report
	startStage := func(idx int) {
		stages[idx].Status = "running"
		reportStages(idx+1, stages[idx].Name)
	}

	// Helper to update stage status and report progress
	updateStage := func(idx int, status string, durationMs float64) {
		stages[idx].Status = status
		stages[idx].DurationMs = durationMs
		reportStages(idx+1, stages[idx].Name)
	}

	// Step 1: Generate portfolio hash (still needed for plan metadata)
	step1Start := time.Now()
	startStage(0)
	if j.generatePortfolioHashJob == nil {
		return fmt.Errorf("generate portfolio hash job not available")
	}
	if err := j.generatePortfolioHashJob.Run(); err != nil {
		updateStage(0, "failed", float64(time.Since(step1Start).Milliseconds()))
		return fmt.Errorf("failed to generate portfolio hash: %w", err)
	}
	updateStage(0, "completed", float64(time.Since(step1Start).Milliseconds()))

	// Get portfolio hash from job (for metadata/logging only, not for skip logic)
	hashJob, ok := j.generatePortfolioHashJob.(*GeneratePortfolioHashJob)
	if !ok {
		return fmt.Errorf("generate portfolio hash job has wrong type")
	}
	portfolioHash := hashJob.GetLastPortfolioHash()

	j.log.Info().
		Str("portfolio_hash", portfolioHash).
		Msg("Generating new plan")

	// Step 2: Get optimizer weights (optional - if available)
	step2Start := time.Now()
	startStage(1)
	var optimizerWeights map[string]float64
	if j.getOptimizerWeightsJob != nil {
		if err := j.getOptimizerWeightsJob.Run(); err != nil {
			j.log.Warn().Err(err).Msg("Failed to get optimizer weights, continuing without them")
		} else {
			weightsJob, ok := j.getOptimizerWeightsJob.(*GetOptimizerWeightsJob)
			if ok {
				optimizerWeights = weightsJob.GetTargetWeights()
				j.log.Debug().Int("weight_count", len(optimizerWeights)).Msg("Retrieved optimizer target weights")
			}
		}
	}
	updateStage(1, "completed", float64(time.Since(step2Start).Milliseconds()))

	// Step 3: Build opportunity context
	step3Start := time.Now()
	startStage(2)
	if j.buildOpportunityContextJob == nil {
		return fmt.Errorf("build opportunity context job not available")
	}
	// Set optimizer weights on context job before running
	contextJob, ok := j.buildOpportunityContextJob.(*BuildOpportunityContextJob)
	if !ok {
		return fmt.Errorf("build opportunity context job has wrong type")
	}
	if len(optimizerWeights) > 0 {
		contextJob.SetOptimizerTargetWeights(optimizerWeights)
	}
	if err := j.buildOpportunityContextJob.Run(); err != nil {
		updateStage(2, "failed", float64(time.Since(step3Start).Milliseconds()))
		return fmt.Errorf("failed to build opportunity context: %w", err)
	}
	updateStage(2, "completed", float64(time.Since(step3Start).Milliseconds()))

	// Get opportunity context from job (already type-asserted above)
	opportunityContext := contextJob.GetOpportunityContext()
	if opportunityContext == nil {
		return fmt.Errorf("opportunity context is nil")
	}

	// Step 4: Create trade plan with detailed progress
	step4Start := time.Now()
	startStage(3)
	if j.createTradePlanJob == nil {
		return fmt.Errorf("create trade plan job not available")
	}
	planJob, ok := j.createTradePlanJob.(*CreateTradePlanJob)
	if !ok {
		return fmt.Errorf("create trade plan job has wrong type")
	}
	planJob.SetOpportunityContext(opportunityContext)

	// Create detailed progress callback that wraps the reporter
	if reporter != nil {
		detailedCallback := func(update progress.Update) {
			// Forward detailed progress to the reporter with phase/subphase info
			reporter.ReportWithDetails(4, totalSteps, update.Message, update.Phase, update.SubPhase, update.Details)
		}
		planJob.SetDetailedProgressCallback(detailedCallback)
	}

	if err := j.createTradePlanJob.Run(); err != nil {
		updateStage(3, "failed", float64(time.Since(step4Start).Milliseconds()))
		return fmt.Errorf("failed to create trade plan: %w", err)
	}
	updateStage(3, "completed", float64(time.Since(step4Start).Milliseconds()))

	// Get plan from job (now returns typed *planningdomain.HolisticPlan)
	plan := planJob.GetPlan()
	if plan == nil {
		return fmt.Errorf("plan is nil")
	}

	// Step 5: Store recommendations
	step5Start := time.Now()
	startStage(4)
	if j.storeRecommendationsJob == nil {
		return fmt.Errorf("store recommendations job not available")
	}
	storeJob, ok := j.storeRecommendationsJob.(*StoreRecommendationsJob)
	if !ok {
		return fmt.Errorf("store recommendations job has wrong type")
	}
	storeJob.SetPlan(plan)
	storeJob.SetPortfolioHash(portfolioHash)

	// Pass rejected opportunities from plan job to store job
	rejectedOpportunities := planJob.GetRejectedOpportunities()
	storeJob.SetRejectedOpportunities(rejectedOpportunities)
	if len(rejectedOpportunities) > 0 {
		j.log.Info().
			Int("rejected_count", len(rejectedOpportunities)).
			Msg("Passing rejected opportunities to store job")
	}

	// Pass pre-filtered securities from plan job to store job
	preFilteredSecurities := planJob.GetPreFilteredSecurities()
	storeJob.SetPreFilteredSecurities(preFilteredSecurities)
	if len(preFilteredSecurities) > 0 {
		j.log.Info().
			Int("pre_filtered_count", len(preFilteredSecurities)).
			Msg("Passing pre-filtered securities to store job")
	}

	// Pass rejected sequences from plan job to store job
	rejectedSequences := planJob.GetRejectedSequences()
	storeJob.SetRejectedSequences(rejectedSequences)
	if len(rejectedSequences) > 0 {
		j.log.Info().
			Int("rejected_sequences_count", len(rejectedSequences)).
			Msg("Passing rejected sequences to store job")
	}

	if err := j.storeRecommendationsJob.Run(); err != nil {
		updateStage(4, "failed", float64(time.Since(step5Start).Milliseconds()))
		return fmt.Errorf("failed to store recommendations: %w", err)
	}
	updateStage(4, "completed", float64(time.Since(step5Start).Milliseconds()))

	// Emit events with final stage information
	if j.eventManager != nil {
		// plan is guaranteed to be non-nil here (checked above)
		j.eventManager.EmitTyped(events.PlanGenerated, "planner", &events.PlanGeneratedData{
			PortfolioHash: portfolioHash,
			Steps:         len(plan.Steps),
			EndScore:      plan.EndStateScore,
			Improvement:   plan.Improvement,
			Feasible:      plan.Feasible,
		})

		if len(plan.Steps) > 0 {
			j.eventManager.EmitTyped(events.RecommendationsReady, "planner", &events.RecommendationsReadyData{
				PortfolioHash: portfolioHash,
				Count:         len(plan.Steps),
			})
		}
	}

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Str("portfolio_hash", portfolioHash).
		Msg("Planner batch completed")

	return nil
}
