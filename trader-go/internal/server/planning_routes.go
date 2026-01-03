package server

import (
	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/aristath/arduino-trader/internal/modules/planning/config"
	"github.com/aristath/arduino-trader/internal/modules/planning/evaluation"
	"github.com/aristath/arduino-trader/internal/modules/planning/handlers"
	"github.com/aristath/arduino-trader/internal/modules/planning/planner"
	"github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/go-chi/chi/v5"
)

// setupPlanningRoutes configures planning module routes.
func (s *Server) setupPlanningRoutes(r chi.Router) {
	// Initialize opportunities service
	opportunitiesService := opportunities.NewService(s.log)

	// Initialize sequences service
	sequencesService := sequences.NewService(s.log)

	// Initialize evaluation client (microservice)
	evaluationClient := evaluation.NewClient(s.cfg.EvaluatorServiceURL, s.log)

	// Initialize planning service
	planningService := planning.NewService(
		opportunitiesService,
		sequencesService,
		evaluationClient,
		s.log,
	)

	// Initialize planner repository (uses configDB for planner state)
	plannerRepo := repository.NewPlannerRepository(s.configDB, s.log)

	// Initialize config loader
	configLoader := config.NewLoader(s.log)

	// Initialize config repository
	configRepo := repository.NewConfigRepository(s.configDB, configLoader, s.log)

	// Initialize config validator
	validator := config.NewValidator()

	// Initialize core planner (planning engine)
	corePlanner := planner.NewPlanner(
		opportunitiesService,
		sequencesService,
		evaluationClient,
		s.log,
	)

	// Initialize incremental planner (batch generation)
	incrementalPlanner := planner.NewIncrementalPlanner(
		corePlanner,
		plannerRepo,
		s.log,
	)

	// Initialize event broadcaster for SSE streaming
	eventBroadcaster := handlers.NewEventBroadcaster(s.log)

	// Initialize handlers
	recommendationsHandler := handlers.NewRecommendationsHandler(planningService, s.log)
	configHandler := handlers.NewConfigHandler(configRepo, validator, s.log)
	batchHandler := handlers.NewBatchHandler(incrementalPlanner, configRepo, s.log)
	executeHandler := handlers.NewExecuteHandler(plannerRepo, nil, s.log) // TODO: Pass trade executor
	statusHandler := handlers.NewStatusHandler(plannerRepo, s.log)
	streamHandler := handlers.NewStreamHandler(eventBroadcaster, s.log)

	// Register routes
	r.Route("/api/planning", func(r chi.Router) {
		// Recommendations (main planning endpoint)
		r.Post("/recommendations", recommendationsHandler.ServeHTTP)

		// Configuration management
		r.Get("/configs", configHandler.ServeHTTP)
		r.Post("/configs", configHandler.ServeHTTP)
		r.Get("/configs/{id}", configHandler.ServeHTTP)
		r.Put("/configs/{id}", configHandler.ServeHTTP)
		r.Delete("/configs/{id}", configHandler.ServeHTTP)
		r.Post("/configs/validate", configHandler.ServeHTTP)
		r.Get("/configs/{id}/history", configHandler.ServeHTTP)

		// Batch generation
		r.Post("/batch", batchHandler.ServeHTTP)

		// Plan execution
		r.Post("/execute", executeHandler.ServeHTTP)

		// Status monitoring
		r.Get("/status", statusHandler.ServeHTTP)

		// SSE streaming
		r.Get("/stream", streamHandler.ServeHTTP)
	})

	// Trade recommendations endpoints (aliases for compatibility)
	r.Route("/api/trades", func(r chi.Router) {
		r.Get("/recommendations", recommendationsHandler.ServeHTTP)
		r.Post("/recommendations", recommendationsHandler.ServeHTTP)
		r.Post("/recommendations/execute", executeHandler.ServeHTTP)
	})
}
