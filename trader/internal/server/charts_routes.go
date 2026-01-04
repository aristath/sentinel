package server

import (
	"github.com/aristath/arduino-trader/internal/modules/charts"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/go-chi/chi/v5"
)

// setupChartsRoutes configures charts module routes
func (s *Server) setupChartsRoutes(r chi.Router) {
	// Initialize security repository
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)

	// Initialize charts service
	chartsService := charts.NewService(
		s.cfg.HistoryPath,
		securityRepo,
		s.universeDB.Conn(),
		s.log,
	)

	// Initialize charts handler
	chartsHandler := charts.NewHandler(chartsService, s.log)

	// Register routes
	r.Route("/charts", func(r chi.Router) {
		// GET /api/charts/sparklines - Get 1-year sparkline data for all active securities
		r.Get("/sparklines", chartsHandler.HandleGetSparklines)

		// GET /api/charts/securities/{isin} - Get historical price data for a specific security
		r.Get("/securities/{isin}", chartsHandler.HandleGetSecurityChart)
	})
}
