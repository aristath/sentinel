// Package main is the entry point for the Sentinel autonomous portfolio management system.
// This application manages investment portfolios, executes trades, processes dividends,
// and maintains portfolio health with minimal human intervention.
//
// The application follows clean architecture principles:
// - Domain layer is pure (no infrastructure dependencies)
// - Dependency injection via DI container
// - Repository pattern for data access
// - Service layer for business logic
// - HTTP handlers for API endpoints
package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/deployment"
	"github.com/aristath/sentinel/internal/di"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/reliability"
	"github.com/aristath/sentinel/internal/server"
	"github.com/aristath/sentinel/pkg/logger"
)

// getEnv retrieves an environment variable value, returning a fallback if the variable
// is not set or is empty. This is used for configuration values that have sensible defaults.
//
// Parameters:
//   - key: The environment variable name to look up
//   - fallback: The default value to return if the variable is not set
//
// Returns:
//   - The environment variable value if set and non-empty, otherwise the fallback value
func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

// main is the application entry point. It orchestrates the entire system startup sequence:
// 1. Loads configuration from environment variables and settings database
// 2. Initializes logging system
// 3. Sets up display manager for LED status indicators
// 4. Checks for and executes pending database restores (if any)
// 5. Wires all dependencies via DI container (databases, repositories, services)
// 6. Updates configuration from settings database (credentials, etc.)
// 7. Initializes deployment manager (if enabled)
// 8. Starts HTTP server for API endpoints
// 9. Starts background monitors (state monitor, work processor, LED monitors)
// 10. Waits for shutdown signal and performs graceful shutdown
//
// The application uses a 7-database architecture:
// - universe.db: Investment universe (securities, groups)
// - config.db: Application configuration (settings, allocation targets)
// - ledger.db: Immutable financial audit trail (trades, cash flows, dividends)
// - portfolio.db: Current portfolio state (positions, scores, metrics, snapshots)
// - history.db: Historical time-series data (prices, rates, cleanup tracking)
// - cache.db: Ephemeral operational data (job history)
// - client_data.db: Cache for exchange rates and current prices
func main() {
	// Load configuration first to get log level
	// Configuration is loaded from environment variables (.env file) and can be
	// updated later from the settings database (for credentials, etc.)
	cfg, err := config.Load()
	if err != nil {
		// Use fallback logger if config fails
		// This ensures we can log the configuration error even if config loading fails
		fallbackLog := logger.New(logger.Config{
			Level:  "info",
			Pretty: true,
		})
		fallbackLog.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Initialize logger with config level
	// Logger uses structured logging (zerolog) with configurable log levels
	// Pretty mode enables human-readable output for development
	log := logger.New(logger.Config{
		Level:  cfg.LogLevel,
		Pretty: true,
	})

	log.Info().Msg("Starting Sentinel")

	// Display manager (state holder for LED display) - must be initialized before server.New()
	// The display manager maintains the state of LED indicators on the Arduino Uno Q.
	// It tracks various system states (service health, planner actions, portfolio status)
	// and must be initialized early so the HTTP server can serve display status endpoints.
	displayManager := display.NewStateManager(log)
	log.Info().Msg("Display manager initialized")

	// Check for pending restore BEFORE initializing databases
	// This ensures restores are applied before any database connections are opened.
	// Restores are staged by the backup service and executed on next startup to ensure
	// database integrity. This prevents partial restores that could corrupt running systems.
	restoreSvc := reliability.NewRestoreService(nil, cfg.DataDir, log)
	hasPendingRestore, err := restoreSvc.CheckPendingRestore()
	if err != nil {
		log.Error().Err(err).Msg("Failed to check for pending restore")
	}

	if hasPendingRestore {
		log.Warn().Msg("Pending restore detected, executing staged restore...")
		if err := restoreSvc.ExecuteStagedRestore(); err != nil {
			log.Fatal().Err(err).Msg("Failed to execute staged restore")
		}
		log.Info().Msg("Restore completed successfully, proceeding with normal startup")
	}

	// Wire all dependencies using DI container
	// This initializes databases, repositories, services, and work processor.
	// The DI container follows clean architecture principles:
	// - Databases are initialized first (7-database architecture)
	// - Repositories are created with database connections
	// - Services are created with repository dependencies
	// - Work processor is registered with all job types
	// - All dependencies are injected via constructor injection
	container, err := di.Wire(cfg, log, displayManager)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to wire dependencies")
	}

	// Market indices are now synced to database in di.InitializeServices via IndexRepository.SyncFromKnownIndices()
	// Historical price sync for indices is handled by the regular sync cycle.
	// This ensures market regime detection has access to index data for correlation analysis.

	// Cleanup databases on exit
	// All 7 databases must be properly closed to ensure WAL checkpoints are written
	// and database integrity is maintained. Using defer ensures cleanup even on panic.
	defer container.UniverseDB.Close()
	defer container.ConfigDB.Close()
	defer container.LedgerDB.Close()
	defer container.PortfolioDB.Close()
	defer container.HistoryDB.Close()
	defer container.CacheDB.Close()
	defer container.ClientDataDB.Close()
	defer container.CalculationsDB.Close()

	// Update config from settings DB (credentials, etc.) - BEFORE creating deployment manager
	// This ensures GitHub token and other credentials are loaded from settings.
	// Settings database takes precedence over environment variables for runtime configuration.
	// This allows users to update credentials via the UI without restarting the application.
	if err := cfg.UpdateFromSettings(container.SettingsRepo); err != nil {
		log.Warn().Err(err).Msg("Failed to update config from settings DB, using environment variables")
	}

	// Update broker client with credentials from settings DB
	// The broker client was created before settings were loaded, so we need to update it.
	// Broker credentials are stored in the settings database for security (not in .env file).
	// This allows credential rotation without code changes or restarts.
	if cfg.TradernetAPIKey != "" && cfg.TradernetAPISecret != "" {
		container.BrokerClient.SetCredentials(cfg.TradernetAPIKey, cfg.TradernetAPISecret)
		log.Info().Msg("Updated broker client credentials from settings database")
	} else {
		log.Warn().Msg("Tradernet credentials not configured - broker client will not be able to connect")
	}

	// NOW create deployment manager with settings-loaded config
	// Deployment manager handles automated deployment of the system:
	// - Monitors git repository for changes
	// - Downloads pre-built binaries from GitHub Actions
	// - Deploys Go services, frontend, display app, and sketch
	// - Restarts services automatically
	// Only created if deployment is enabled in configuration.
	var deploymentManager *deployment.Manager
	if cfg.Deployment != nil && cfg.Deployment.Enabled {
		deployConfig := cfg.Deployment.ToDeploymentConfig(cfg.GitHubToken)
		version := getEnv("VERSION", "dev")
		deploymentManager = deployment.NewManager(deployConfig, version, log)

		log.Info().Msg("Deployment manager initialized (deployment work type registered in work.go)")
	}

	// Create deployment handlers if deployment is enabled
	// Deployment handlers expose HTTP endpoints for triggering deployments,
	// checking deployment status, and managing deployment configuration.
	var deploymentHandlers *server.DeploymentHandlers
	if deploymentManager != nil {
		deploymentHandlers = server.NewDeploymentHandlers(deploymentManager, log)
	}

	// Initialize HTTP server
	// Pass container to server so it can use all services.
	// The HTTP server provides REST API endpoints for:
	// - Portfolio management (positions, scores, metrics)
	// - Trading operations (execute trades, sync portfolio)
	// - Planning and recommendations (generate sequences, evaluate plans)
	// - Settings management (credentials, allocation targets)
	// - System operations (health checks, logs, backups)
	// - Frontend static assets (embedded in Go binary)
	srv := server.New(server.Config{
		Port:               cfg.Port,
		Log:                log,
		UniverseDB:         container.UniverseDB,
		ConfigDB:           container.ConfigDB,
		LedgerDB:           container.LedgerDB,
		PortfolioDB:        container.PortfolioDB,
		HistoryDB:          container.HistoryDB,
		CacheDB:            container.CacheDB,
		Config:             cfg,
		DevMode:            cfg.DevMode,
		DisplayManager:     displayManager,
		DeploymentHandlers: deploymentHandlers,
		Container:          container, // Pass container for handlers to use
	})

	// NOTE: Individual job triggering is now done via Work Processor endpoints at /api/work/*
	// All job execution goes through Work Processor (see work.go).
	// The Work Processor provides:
	// - Event-driven job execution (triggered by events or time-based schedules)
	// - Dependency resolution (jobs wait for prerequisites)
	// - Market-aware scheduling (pauses during market closure)
	// - Job history tracking (completion status, execution times)

	// Start server in goroutine
	// The HTTP server runs in a separate goroutine so it doesn't block the main thread.
	// This allows other background services (monitors, work processor) to start concurrently.
	go func() {
		if err := srv.Start(); err != nil {
			log.Fatal().Err(err).Msg("Failed to start server")
		}
	}()

	log.Info().Int("port", cfg.Port).Msg("Server started successfully")

	// Start state monitor (monitors unified state hash and triggers recommendations)
	// Runs every minute, emits StateChanged event when hash changes.
	// The state hash represents the current portfolio state (positions, scores, allocation).
	// When the hash changes, it indicates the portfolio has changed and new recommendations
	// may be needed. This triggers the planning system to generate new trade sequences.
	container.StateMonitor.Start()
	log.Info().Msg("State monitor started (checking every minute)")

	// Start work processor (event-driven background job system)
	// The work processor executes background jobs such as:
	// - Price synchronization (sync current prices from broker)
	// - Trade synchronization (sync executed trades from broker)
	// - Portfolio synchronization (sync portfolio state from broker)
	// - Cash flow processing (process deposits, dividends)
	// - Market data updates (exchange rates, market hours)
	// Jobs can be triggered by events, time-based schedules, or manual API calls.
	if container.WorkComponents != nil && container.WorkComponents.Processor != nil {
		go container.WorkComponents.Processor.Run()
		log.Info().Msg("Work processor started")
	}

	// Start LED status monitors
	// LED monitors track system state and update the Arduino Uno Q display.
	// They run in separate goroutines and can be cancelled via context on shutdown.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start service heartbeat monitor (LED3)
	// Monitors the main "sentinel" service health and updates LED3 accordingly.
	// LED3 indicates whether the core service is running and healthy.
	serviceMonitor := display.NewServiceMonitor("sentinel", displayManager, log)
	go serviceMonitor.MonitorService(ctx)
	log.Info().Msg("Service heartbeat monitor started (LED3)")

	// Start planner action monitor (LED4)
	// Monitors planner activity (recommendation generation, sequence evaluation).
	// LED4 indicates when the planning system is actively generating recommendations.
	// Use recommendation repo from container to check for new recommendations.
	plannerMonitor := display.NewPlannerMonitor(container.RecommendationRepo, displayManager, log)
	go plannerMonitor.MonitorPlannerActions(ctx)
	log.Info().Msg("Planner action monitor started (LED4)")

	// Wait for interrupt signal
	// The application blocks here until it receives SIGINT (Ctrl+C) or SIGTERM (kill command).
	// This allows the application to run indefinitely until explicitly stopped.
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	// Cancel context to stop monitors
	// Cancelling the context signals all LED monitors to stop gracefully.
	// The defer cancel() at the top ensures this runs even if we return early.
	cancel()
	log.Info().Msg("Stopping LED monitors...")

	log.Info().Msg("Shutting down server...")

	// Stop state monitor
	// The state monitor checks portfolio state every minute. Stopping it prevents
	// new state change events from being emitted during shutdown.
	if container.StateMonitor != nil {
		container.StateMonitor.Stop()
		log.Info().Msg("State monitor stopped")
	}

	// Stop work processor
	// The work processor executes background jobs. Stopping it prevents new jobs
	// from starting during shutdown, but allows in-progress jobs to complete.
	if container.WorkComponents != nil && container.WorkComponents.Processor != nil {
		container.WorkComponents.Processor.Stop()
		log.Info().Msg("Work processor stopped")
	}

	// Stop WebSocket client
	// The market status WebSocket client receives real-time market status updates.
	// Stopping it closes the WebSocket connection gracefully.
	if container.MarketStatusWS != nil {
		if err := container.MarketStatusWS.Stop(); err != nil {
			log.Error().Err(err).Msg("Error stopping market status WebSocket")
		} else {
			log.Info().Msg("Market status WebSocket stopped")
		}
	}

	// Graceful shutdown
	// The HTTP server is given up to 10 seconds to finish processing in-flight requests
	// and close connections gracefully. If the timeout is exceeded, the server is forced
	// to shutdown, which may interrupt active requests.
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("Server forced to shutdown")
	}

	log.Info().Msg("Server stopped")
}

// All dependency wiring is handled by di.Wire()
// The DI container initializes:
//   - internal/di/databases.go (database initialization)
//   - internal/di/repositories.go (repository creation)
//   - internal/di/services.go (service creation)
//   - internal/di/work.go (work processor registration)
//   - internal/di/wire.go (main orchestration)
