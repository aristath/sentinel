// Package di provides dependency injection wiring and initialization.
package di

import (
	"fmt"

	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/rs/zerolog"
)

// Wire initializes all dependencies and returns a fully configured container
// This is the main entry point for dependency injection
// Order of operations:
// 1. Initialize databases
// 2. Initialize repositories
// 3. Initialize services
// 4. Register jobs
// deploymentManager is optional (can be nil if deployment is disabled)
func Wire(cfg *config.Config, log zerolog.Logger, displayManager *display.StateManager, deploymentManager interface{}) (*Container, *JobInstances, error) {
	// Step 1: Initialize databases
	container, err := InitializeDatabases(cfg, log)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to initialize databases: %w", err)
	}

	// Step 2: Initialize repositories
	if err := InitializeRepositories(container, log); err != nil {
		// Cleanup databases on error
		container.UniverseDB.Close()
		container.ConfigDB.Close()
		container.LedgerDB.Close()
		container.PortfolioDB.Close()
		container.HistoryDB.Close()
		container.CacheDB.Close()
		container.ClientDataDB.Close()
		return nil, nil, fmt.Errorf("failed to initialize repositories: %w", err)
	}

	// Step 3: Initialize services
	if err := InitializeServices(container, cfg, displayManager, log); err != nil {
		// Cleanup on error
		container.UniverseDB.Close()
		container.ConfigDB.Close()
		container.LedgerDB.Close()
		container.PortfolioDB.Close()
		container.HistoryDB.Close()
		container.CacheDB.Close()
		container.ClientDataDB.Close()
		return nil, nil, fmt.Errorf("failed to initialize services: %w", err)
	}

	// Step 4: Register jobs (pass deployment manager if available)
	jobs, err := RegisterJobs(container, cfg, displayManager, deploymentManager, log)
	if err != nil {
		// Cleanup on error
		container.UniverseDB.Close()
		container.ConfigDB.Close()
		container.LedgerDB.Close()
		container.PortfolioDB.Close()
		container.HistoryDB.Close()
		container.CacheDB.Close()
		container.ClientDataDB.Close()
		return nil, nil, fmt.Errorf("failed to register jobs: %w", err)
	}

	log.Info().Msg("Dependency injection wiring completed successfully")

	return container, jobs, nil
}
