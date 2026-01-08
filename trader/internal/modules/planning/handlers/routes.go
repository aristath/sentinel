package handlers

import (
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/planning"
	"github.com/aristath/sentinel/internal/modules/planning/config"
	"github.com/aristath/sentinel/internal/modules/planning/planner"
	"github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler provides HTTP handlers for planning endpoints
type Handler struct {
	recommendationsHandler *RecommendationsHandler
	configHandler          *ConfigHandler
	batchHandler           *BatchHandler
	executeHandler         *ExecuteHandler
	statusHandler          *StatusHandler
	streamHandler          *StreamHandler
}

// NewHandler creates a new planning handler with all sub-handlers
func NewHandler(
	planningService *planning.Service,
	configRepo *repository.ConfigRepository,
	corePlanner *planner.Planner,
	plannerRepo *repository.PlannerRepository,
	validator *config.Validator,
	incrementalPlanner *planner.IncrementalPlanner,
	eventBroadcaster *EventBroadcaster,
	eventManager *events.Manager,
	tradeExecutor TradeExecutor,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		recommendationsHandler: NewRecommendationsHandler(planningService, log),
		configHandler:          NewConfigHandler(configRepo, validator, eventManager, log),
		batchHandler:           NewBatchHandler(incrementalPlanner, configRepo, log),
		executeHandler:         NewExecuteHandler(plannerRepo, tradeExecutor, log),
		statusHandler:          NewStatusHandler(plannerRepo, log),
		streamHandler:          NewStreamHandler(eventBroadcaster, log),
	}
}

// RegisterRoutes registers all planning routes
func (h *Handler) RegisterRoutes(r chi.Router) {
	r.Route("/planning", func(r chi.Router) {
		// Recommendations (main planning endpoint)
		r.Get("/recommendations", h.recommendationsHandler.ServeHTTP)
		r.Post("/recommendations", h.recommendationsHandler.ServeHTTP)

		// Configuration management (single config - no ID needed)
		r.Get("/config", h.configHandler.ServeHTTP)
		r.Put("/config", h.configHandler.ServeHTTP)
		r.Delete("/config", h.configHandler.ServeHTTP)
		r.Post("/config/validate", h.configHandler.ServeHTTP)

		// Batch generation
		r.Post("/batch", h.batchHandler.ServeHTTP)

		// Plan execution
		r.Post("/execute", h.executeHandler.ServeHTTP)

		// Status monitoring
		r.Get("/status", h.statusHandler.ServeHTTP)

		// SSE streaming
		r.Get("/stream", h.streamHandler.ServeHTTP)
	})
}
