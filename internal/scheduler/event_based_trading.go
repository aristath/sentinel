package scheduler

import (
	"fmt"
	"sync"
	"time"

	"github.com/aristath/sentinel/internal/modules/planning"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/rs/zerolog"
)

// EventBasedTradingJob monitors for planning completion and executes approved trades
// This is the main autonomous trading loop that waits for the planner batch job
// to complete, then executes the recommended trades (one at a time with 15-min throttle)
type EventBasedTradingJob struct {
	log                zerolog.Logger
	recommendationRepo *planning.RecommendationRepository
	tradingService     *trading.TradingService
	eventManager       EventManagerInterface

	// In-memory throttle lock
	mu                sync.Mutex
	lastExecutionTime time.Time
	throttleDuration  time.Duration
}

// EventBasedTradingConfig holds configuration for event-based trading job
type EventBasedTradingConfig struct {
	Log                zerolog.Logger
	RecommendationRepo *planning.RecommendationRepository
	TradingService     *trading.TradingService
	EventManager       EventManagerInterface
}

// NewEventBasedTradingJob creates a new event-based trading job
func NewEventBasedTradingJob(cfg EventBasedTradingConfig) *EventBasedTradingJob {
	return &EventBasedTradingJob{
		log:                cfg.Log.With().Str("job", "event_based_trading").Logger(),
		recommendationRepo: cfg.RecommendationRepo,
		tradingService:     cfg.TradingService,
		eventManager:       cfg.EventManager,
		throttleDuration:   15 * time.Minute, // Max 1 trade per 15 minutes
	}
}

// Name returns the job name
func (j *EventBasedTradingJob) Name() string {
	return "event_based_trading"
}

// Run executes the event-based trading workflow
// Modified to execute ONE trade per run with 15-minute throttling via in-memory lock
func (j *EventBasedTradingJob) Run() error {
	j.log.Info().Msg("Starting event-based trading cycle")
	startTime := time.Now()

	// Check throttle lock (15-minute cooldown)
	j.mu.Lock()
	timeSinceLastExecution := time.Since(j.lastExecutionTime)
	if !j.lastExecutionTime.IsZero() && timeSinceLastExecution < j.throttleDuration {
		j.mu.Unlock()
		remaining := j.throttleDuration - timeSinceLastExecution
		j.log.Info().
			Dur("remaining", remaining).
			Msg("Trade throttle active - skipping execution")
		return nil
	}
	j.lastExecutionTime = startTime
	j.mu.Unlock()

	// Step 1: Get next pending recommendation (limit to 1 for throttling)
	recommendations, err := j.recommendationRepo.GetPendingRecommendations(1)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get pending recommendations")
		return fmt.Errorf("failed to get pending recommendations: %w", err)
	}

	if len(recommendations) == 0 {
		j.log.Info().Msg("No pending recommendations to execute")
		return nil
	}

	rec := recommendations[0]

	// Check if max retries exceeded (default: 3)
	const maxRetries = 3
	if rec.RetryCount >= maxRetries {
		j.log.Warn().
			Str("uuid", rec.UUID).
			Str("symbol", rec.Symbol).
			Int("retry_count", rec.RetryCount).
			Msg("Max retries exceeded - marking as failed")

		failureReason := fmt.Sprintf("Exceeded max retries (%d)", maxRetries)
		if rec.FailureReason != "" {
			failureReason = fmt.Sprintf("%s. Last failure: %s", failureReason, rec.FailureReason)
		}

		if err := j.recommendationRepo.MarkFailed(rec.UUID, failureReason); err != nil {
			j.log.Error().Err(err).Msg("Failed to mark recommendation as failed")
		}

		return nil // Continue to next recommendation
	}

	j.log.Info().
		Str("uuid", rec.UUID).
		Str("symbol", rec.Symbol).
		Str("side", rec.Side).
		Float64("quantity", rec.Quantity).
		Float64("estimated_price", rec.EstimatedPrice).
		Int("retry_count", rec.RetryCount).
		Msg("Executing recommendation")

	// Step 2: Execute the trade via trading service
	// Note: The trading service handles all safety validations internally
	tradeRequest := trading.TradeRequest{
		Symbol:   rec.Symbol,
		Side:     rec.Side,
		Quantity: int(rec.Quantity),
		Reason:   rec.Reason,
	}

	result, err := j.tradingService.ExecuteTrade(tradeRequest)
	if err != nil {
		j.log.Error().
			Err(err).
			Str("uuid", rec.UUID).
			Str("symbol", rec.Symbol).
			Msg("Failed to execute trade")

		// Record failed attempt
		failureReason := fmt.Sprintf("Execution error: %v", err)
		if err := j.recommendationRepo.RecordFailedAttempt(rec.UUID, failureReason); err != nil {
			j.log.Error().Err(err).Msg("Failed to record failed attempt")
		}

		return fmt.Errorf("trade execution failed: %w", err)
	}

	if !result.Success {
		j.log.Warn().
			Str("uuid", rec.UUID).
			Str("symbol", rec.Symbol).
			Str("reason", result.Reason).
			Msg("Trade rejected by safety checks")

		// Record failed attempt
		failureReason := fmt.Sprintf("Rejected: %s", result.Reason)
		if err := j.recommendationRepo.RecordFailedAttempt(rec.UUID, failureReason); err != nil {
			j.log.Error().Err(err).Msg("Failed to record failed attempt")
		}

		return fmt.Errorf("trade rejected: %s", result.Reason)
	}

	// Step 3: Mark recommendation as executed
	if err := j.recommendationRepo.MarkExecuted(rec.UUID); err != nil {
		j.log.Error().
			Err(err).
			Str("uuid", rec.UUID).
			Msg("Failed to mark recommendation as executed")
		// Trade was executed successfully, but marking failed - log and continue
	}

	j.log.Info().
		Str("uuid", rec.UUID).
		Str("symbol", rec.Symbol).
		Str("order_id", result.OrderID).
		Msg("Trade executed successfully")

	// Step 4: Check if more recommendations exist
	// Note: The event system will trigger this job again (with 15-min throttle)
	// when the next sync/planner cycle completes, or the job can be manually triggered
	moreRecommendations, err := j.recommendationRepo.GetPendingRecommendations(1)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to check for more recommendations")
	} else if len(moreRecommendations) > 0 {
		j.log.Info().
			Int("remaining_count", len(moreRecommendations)).
			Msg("More recommendations pending - will be processed when job is triggered again")
		// The job is throttled to run at most once per 15 minutes via queue manager
	}

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Msg("Event-based trading cycle completed")

	return nil
}
