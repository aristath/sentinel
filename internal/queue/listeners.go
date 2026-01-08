package queue

import (
	"fmt"

	"github.com/aristath/sentinel/internal/events"
	"github.com/rs/zerolog"
)

// RegisterListeners registers event listeners that enqueue jobs
func RegisterListeners(bus *events.Bus, manager *Manager, registry *Registry, log zerolog.Logger) {
	log = log.With().Str("component", "event_listeners").Logger()
	// PortfolioChanged -> planner_batch (HIGH priority)
	bus.Subscribe(events.PortfolioChanged, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypePlannerBatch, event.Timestamp.UnixNano()),
			Type:        JobTypePlannerBatch,
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
				Str("event_type", string(events.PortfolioChanged)).
				Str("job_type", string(JobTypePlannerBatch)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})

	// RecommendationsReady -> event_based_trading (CRITICAL priority)
	// Note: Job has in-memory 15-minute throttle and processes ONE trade at a time
	bus.Subscribe(events.RecommendationsReady, func(event *events.Event) {
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

	// PlanGenerated -> tag_update (MEDIUM priority)
	bus.Subscribe(events.PlanGenerated, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypeTagUpdate, event.Timestamp.UnixNano()),
			Type:        JobTypeTagUpdate,
			Priority:    PriorityMedium,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.PlanGenerated)).
				Str("job_type", string(JobTypeTagUpdate)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})

	// PriceUpdated -> tag_update (LOW priority, will be debounced by manager)
	bus.Subscribe(events.PriceUpdated, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypeTagUpdate, event.Timestamp.UnixNano()),
			Type:        JobTypeTagUpdate,
			Priority:    PriorityLow,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.PriceUpdated)).
				Str("job_type", string(JobTypeTagUpdate)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})

	// ScoreUpdated -> tag_update (LOW priority)
	bus.Subscribe(events.ScoreUpdated, func(event *events.Event) {
		job := &Job{
			ID:          fmt.Sprintf("%s-%d", JobTypeTagUpdate, event.Timestamp.UnixNano()),
			Type:        JobTypeTagUpdate,
			Priority:    PriorityLow,
			Payload:     event.Data,
			CreatedAt:   event.Timestamp,
			AvailableAt: event.Timestamp,
			Retries:     0,
			MaxRetries:  3,
		}
		if err := manager.Enqueue(job); err != nil {
			log.Error().
				Err(err).
				Str("event_type", string(events.ScoreUpdated)).
				Str("job_type", string(JobTypeTagUpdate)).
				Str("job_id", job.ID).
				Msg("Failed to enqueue job from event")
		}
	})

	// DividendDetected -> dividend_reinvestment (HIGH priority)
	bus.Subscribe(events.DividendDetected, func(event *events.Event) {
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
