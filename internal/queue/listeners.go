package queue

import (
	"fmt"

	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// RegisterListeners registers event listeners that enqueue jobs
func RegisterListeners(bus *events.Bus, manager *Manager, registry *Registry, log zerolog.Logger) {
	log = log.With().Str("component", "event_listeners").Logger()

	// StateChanged -> planner_batch (CRITICAL priority - unified state monitoring)
	// This is the new primary trigger for recommendation regeneration
	// Replaces separate PortfolioChanged, ScoreUpdated, and other triggers
	_ = bus.Subscribe(events.StateChanged, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypePlannerBatch, event.Timestamp.UnixNano()),
			Type:        JobTypePlannerBatch,
			Priority:    PriorityCritical,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.StateChanged)).
				Str("job_type", string(JobTypePlannerBatch)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue planner_batch from StateChanged event")
		} else {
			// Extract hashes for logging
			oldHash, _ := event.Data["old_hash"].(string)
			newHash, _ := event.Data["new_hash"].(string)
			log.Info().
				Str("old_hash", oldHash).
				Str("new_hash", newHash).
				Msg("Enqueued planner_batch due to state change")
		}
	})

	// RecommendationsReady -> event_based_trading (CRITICAL priority)
	// Note: Job has in-memory 15-minute throttle and processes ONE trade at a time
	_ = bus.Subscribe(events.RecommendationsReady, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypeEventBasedTrading, event.Timestamp.UnixNano()),
			Type:        JobTypeEventBasedTrading,
			Priority:    PriorityCritical,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.RecommendationsReady)).
				Str("job_type", string(JobTypeEventBasedTrading)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})

	// NOTE: Tag updates are now handled by the Work Processor.
	// Per-security tag updates are staggered to avoid paralyzing the system.
	// Batch TagUpdateJob is still available via API for manual force-refresh.
	// Removed event listeners: PlanGenerated, PriceUpdated, ScoreUpdated -> tag_update

	// DividendDetected -> dividend_reinvestment (HIGH priority)
	_ = bus.Subscribe(events.DividendDetected, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypeDividendReinvest, event.Timestamp.UnixNano()),
			Type:        JobTypeDividendReinvest,
			Priority:    PriorityHigh,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.DividendDetected)).
				Str("job_type", string(JobTypeDividendReinvest)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})
}
