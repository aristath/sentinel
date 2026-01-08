// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"github.com/aristath/sentinel/internal/modules/symbolic_regression"
	symbolicregressionhandlers "github.com/aristath/sentinel/internal/modules/symbolic_regression/handlers"
	"github.com/go-chi/chi/v5"
)

// setupSymbolicRegressionRoutes configures symbolic regression module routes
// nolint:unused // kept for documentation/reference; not used by runtime
func (s *Server) setupSymbolicRegressionRoutes(r chi.Router) {
	// Initialize formula storage
	formulaStorage := symbolic_regression.NewFormulaStorage(s.configDB.Conn(), s.log)

	// Initialize data preparation
	dataPrep := symbolic_regression.NewDataPrep(
		s.historyDB.Conn(),
		s.portfolioDB.Conn(),
		s.configDB.Conn(),
		s.universeDB.Conn(),
		s.log,
	)

	// Initialize discovery service
	discoveryService := symbolic_regression.NewDiscoveryService(
		dataPrep,
		formulaStorage,
		s.log,
	)

	// Initialize handlers
	handlers := symbolicregressionhandlers.NewHandlers(
		formulaStorage,
		discoveryService,
		dataPrep,
		s.log,
	)

	// Register routes
	handlers.RegisterRoutes(r)
}
