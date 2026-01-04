package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/rs/zerolog"
)

// EventBasedTradingJob monitors for planning completion and executes approved trades
// This is the main autonomous trading loop that waits for the planner batch job
// to complete, then executes the recommended trades
type EventBasedTradingJob struct {
	log                  zerolog.Logger
	recommendationRepo   *planning.RecommendationRepository
	tradingService       *trading.TradingService
	lastExecutionTime    time.Time
	minExecutionInterval int // Minimum minutes between trade executions
}

// EventBasedTradingConfig holds configuration for event-based trading job
type EventBasedTradingConfig struct {
	Log                     zerolog.Logger
	RecommendationRepo      *planning.RecommendationRepository
	TradingService          *trading.TradingService
	MinExecutionIntervalMin int // Default: 30 minutes
}

// NewEventBasedTradingJob creates a new event-based trading job
func NewEventBasedTradingJob(cfg EventBasedTradingConfig) *EventBasedTradingJob {
	minInterval := cfg.MinExecutionIntervalMin
	if minInterval == 0 {
		minInterval = 30 // Default: 30 minutes between trade executions
	}

	return &EventBasedTradingJob{
		log:                  cfg.Log.With().Str("job", "event_based_trading").Logger(),
		recommendationRepo:   cfg.RecommendationRepo,
		tradingService:       cfg.TradingService,
		minExecutionInterval: minInterval,
	}
}

// Name returns the job name
func (j *EventBasedTradingJob) Name() string {
	return "event_based_trading"
}

// Run executes the event-based trading workflow
func (j *EventBasedTradingJob) Run() error {
	j.log.Info().Msg("Starting event-based trading cycle")
	startTime := time.Now()

	// Check if enough time has passed since last execution
	timeSinceLastExec := time.Since(j.lastExecutionTime)
	minInterval := time.Duration(j.minExecutionInterval) * time.Minute

	if timeSinceLastExec < minInterval && j.lastExecutionTime.Unix() > 0 {
		j.log.Info().
			Dur("time_since_last", timeSinceLastExec).
			Dur("min_interval", minInterval).
			Msg("Skipping execution - too soon since last trade execution")
		return nil
	}

	// Step 1: Get pending recommendations (limit to top 10 by priority)
	recommendations, err := j.recommendationRepo.GetPendingRecommendations(10)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get pending recommendations")
		return fmt.Errorf("failed to get pending recommendations: %w", err)
	}

	if len(recommendations) == 0 {
		j.log.Info().Msg("No pending recommendations to execute")
		return nil
	}

	j.log.Info().
		Int("count", len(recommendations)).
		Msg("Found pending recommendations")

	// Step 2: Execute trades
	executedCount := 0
	failedCount := 0

	for _, rec := range recommendations {
		j.log.Info().
			Str("uuid", rec.UUID).
			Str("symbol", rec.Symbol).
			Str("side", rec.Side).
			Float64("quantity", rec.Quantity).
			Float64("estimated_price", rec.EstimatedPrice).
			Msg("Executing recommendation")

		// Execute the trade via trading service
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
			failedCount++
			continue
		}

		if !result.Success {
			j.log.Warn().
				Str("uuid", rec.UUID).
				Str("symbol", rec.Symbol).
				Str("reason", result.Reason).
				Msg("Trade rejected by safety checks")
			failedCount++
			continue
		}

		// Mark recommendation as executed
		if err := j.recommendationRepo.MarkExecuted(rec.UUID); err != nil {
			j.log.Error().
				Err(err).
				Str("uuid", rec.UUID).
				Msg("Failed to mark recommendation as executed")
			// Don't increment failedCount - trade was executed successfully
		}

		j.log.Info().
			Str("uuid", rec.UUID).
			Str("symbol", rec.Symbol).
			Str("order_id", result.OrderID).
			Msg("Trade executed successfully")
		executedCount++
	}

	// Update last execution time
	j.lastExecutionTime = time.Now()

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Int("executed", executedCount).
		Int("failed", failedCount).
		Int("total", len(recommendations)).
		Msg("Event-based trading cycle completed")

	return nil
}
