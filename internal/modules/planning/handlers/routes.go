package handlers

import (
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/modules/planning"
	"github.com/aristath/sentinel/internal/modules/planning/config"
	"github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

// Handler provides HTTP handlers for planning endpoints
type Handler struct {
	recommendationsHandler *RecommendationsHandler
	configHandler          *ConfigHandler
	executeHandler         *ExecuteHandler
	streamHandler          *StreamHandler
	dismissedFilterHandler *DismissedFilterHandler
}

// NewHandler creates a new planning handler with all sub-handlers
func NewHandler(
	planningService *planning.Service,
	configRepo *repository.ConfigRepository,
	plannerRepo *repository.PlannerRepository,
	dismissedFilterRepo *repository.DismissedFilterRepository,
	validator *config.Validator,
	eventBroadcaster *EventBroadcaster,
	eventManager *events.Manager,
	tradeExecutor TradeExecutor,
	log zerolog.Logger,
) *Handler {
	return &Handler{
		recommendationsHandler: NewRecommendationsHandler(planningService, log),
		configHandler:          NewConfigHandler(configRepo, validator, eventManager, log),
		executeHandler:         NewExecuteHandler(plannerRepo, tradeExecutor, log),
		streamHandler:          NewStreamHandler(eventBroadcaster, log),
		dismissedFilterHandler: NewDismissedFilterHandler(dismissedFilterRepo, log),
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

		// Plan execution
		r.Post("/execute", h.executeHandler.ServeHTTP)

		// SSE streaming
		r.Get("/stream", h.streamHandler.ServeHTTP)

		// Dismissed filters management
		r.Post("/dismiss-filter", h.dismissedFilterHandler.Dismiss)
		r.Delete("/dismiss-filter", h.dismissedFilterHandler.Undismiss)
		r.Get("/dismissed-filters", h.dismissedFilterHandler.GetAll)
	})
}
