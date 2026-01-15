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
	"github.com/aristath/sentinel/internal/queue"
	"github.com/aristath/sentinel/internal/reliability"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/internal/server"
	"github.com/aristath/sentinel/pkg/logger"
)

// getEnv gets environment variable with fallback
func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func main() {
	// Load configuration first to get log level
	cfg, err := config.Load()
	if err != nil {
		// Use fallback logger if config fails
		fallbackLog := logger.New(logger.Config{
			Level:  "info",
			Pretty: true,
		})
		fallbackLog.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Initialize logger with config level
	log := logger.New(logger.Config{
		Level:  cfg.LogLevel,
		Pretty: true,
	})

	log.Info().Msg("Starting Sentinel")

	// Display manager (state holder for LED display) - must be initialized before server.New()
	displayManager := display.NewStateManager(log)
	log.Info().Msg("Display manager initialized")

	// Check for pending restore BEFORE initializing databases
	// This ensures restores are applied before any database connections are opened
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

	// Wire all dependencies using DI container (WITHOUT deployment manager first)
	// This initializes databases and settings repository
	// Pass nil for deployment manager - we'll create it after loading settings
	container, jobs, err := di.Wire(cfg, log, displayManager, nil)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to wire dependencies")
	}

	// Market indices are now synced to database in di.InitializeServices via IndexRepository.SyncFromKnownIndices()
	// Historical price sync for indices is handled by the regular sync cycle

	// Cleanup databases on exit
	defer container.UniverseDB.Close()
	defer container.ConfigDB.Close()
	defer container.LedgerDB.Close()
	defer container.PortfolioDB.Close()
	defer container.HistoryDB.Close()
	defer container.CacheDB.Close()
	defer container.ClientDataDB.Close()
	defer container.CalculationsDB.Close()

	// Update config from settings DB (credentials, etc.) - BEFORE creating deployment manager
	// This ensures GitHub token and other credentials are loaded from settings
	if err := cfg.UpdateFromSettings(container.SettingsRepo); err != nil {
		log.Warn().Err(err).Msg("Failed to update config from settings DB, using environment variables")
	}

	// Update broker client with credentials from settings DB
	// The broker client was created before settings were loaded, so we need to update it
	if cfg.TradernetAPIKey != "" && cfg.TradernetAPISecret != "" {
		container.BrokerClient.SetCredentials(cfg.TradernetAPIKey, cfg.TradernetAPISecret)
		log.Info().Msg("Updated broker client credentials from settings database")
	} else {
		log.Warn().Msg("Tradernet credentials not configured - broker client will not be able to connect")
	}

	// NOW create deployment manager with settings-loaded config
	var deploymentManager *deployment.Manager
	if cfg.Deployment != nil && cfg.Deployment.Enabled {
		deployConfig := cfg.Deployment.ToDeploymentConfig(cfg.GitHubToken)
		version := getEnv("VERSION", "dev")
		deploymentManager = deployment.NewManager(deployConfig, version, log)

		// Register deployment job now that we have the manager
		deploymentIntervalMinutes, err := container.SettingsRepo.GetFloat("job_auto_deploy_minutes", 5.0)
		if err != nil {
			log.Warn().Err(err).Msg("Failed to get deployment interval from settings, using default 5 minutes")
			deploymentIntervalMinutes = 5.0
		}
		deploymentInterval := time.Duration(deploymentIntervalMinutes) * time.Minute
		deploymentJob := scheduler.NewDeploymentJob(deploymentManager, deploymentInterval, true, log)
		container.JobRegistry.Register(queue.JobTypeDeployment, queue.JobToHandler(deploymentJob))
		jobs.Deployment = deploymentJob

		log.Info().
			Float64("interval_minutes", deploymentIntervalMinutes).
			Msg("Deployment manager initialized and job registered")
	}

	// Create deployment handlers if deployment is enabled
	var deploymentHandlers *server.DeploymentHandlers
	if deploymentManager != nil {
		deploymentHandlers = server.NewDeploymentHandlers(deploymentManager, log)
	}

	// Initialize HTTP server
	// Pass container to server so it can use all services
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

	// Wire up jobs for manual triggering via API
	// NOTE: All composite jobs removed - use Work Processor endpoints instead
	srv.SetJobs(
		jobs.EventBasedTrading,
		jobs.TagUpdate,
		// Individual sync jobs
		jobs.SyncTrades,
		jobs.SyncCashFlows,
		jobs.SyncPortfolio,
		jobs.SyncPrices,
		jobs.CheckNegativeBalances,
		jobs.UpdateDisplayTicker,
		// Individual planning jobs
		jobs.GeneratePortfolioHash,
		jobs.GetOptimizerWeights,
		jobs.BuildOpportunityContext,
		jobs.CreateTradePlan,
		jobs.StoreRecommendations,
		// Individual dividend jobs
		jobs.GetUnreinvestedDividends,
		jobs.GroupDividendsBySymbol,
		jobs.CheckDividendYields,
		jobs.CreateDividendRecommendations,
		jobs.SetPendingBonuses,
		jobs.ExecuteDividendTrades,
		// Individual health check jobs
		jobs.CheckCoreDatabases,
		jobs.CheckHistoryDatabases,
		jobs.CheckWALCheckpoints,
	)

	// Set Tradernet metadata sync job (for manual triggering)
	srv.SetTradernetMetadataSyncJob(jobs.TradernetMetadataSync)

	// Start server in goroutine
	go func() {
		if err := srv.Start(); err != nil {
			log.Fatal().Err(err).Msg("Failed to start server")
		}
	}()

	log.Info().Int("port", cfg.Port).Msg("Server started successfully")

	// Start state monitor (monitors unified state hash and triggers recommendations)
	// Runs every minute, emits StateChanged event when hash changes
	container.StateMonitor.Start()
	log.Info().Msg("State monitor started (checking every minute)")

	// Start work processor (event-driven background job system)
	if container.WorkComponents != nil && container.WorkComponents.Processor != nil {
		go container.WorkComponents.Processor.Run()
		log.Info().Msg("Work processor started")
	}

	// Start worker pool for manual job execution via /api/jobs/* endpoints
	// NOTE: Only manually-triggered jobs run through WorkerPool now
	// (RegisterListeners disabled, TimeScheduler deleted)
	if container.WorkerPool != nil {
		container.WorkerPool.Start()
		log.Info().Msg("Worker pool started (for manual job execution)")
	}

	// Start LED status monitors
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start service heartbeat monitor (LED3)
	serviceMonitor := display.NewServiceMonitor("sentinel", displayManager, log)
	go serviceMonitor.MonitorService(ctx)
	log.Info().Msg("Service heartbeat monitor started (LED3)")

	// Start planner action monitor (LED4)
	// Use recommendation repo from container
	plannerMonitor := display.NewPlannerMonitor(container.RecommendationRepo, displayManager, log)
	go plannerMonitor.MonitorPlannerActions(ctx)
	log.Info().Msg("Planner action monitor started (LED4)")

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	// Cancel context to stop monitors
	cancel()
	log.Info().Msg("Stopping LED monitors...")

	log.Info().Msg("Shutting down server...")

	// Stop state monitor
	if container.StateMonitor != nil {
		container.StateMonitor.Stop()
		log.Info().Msg("State monitor stopped")
	}

	// Stop work processor
	if container.WorkComponents != nil && container.WorkComponents.Processor != nil {
		container.WorkComponents.Processor.Stop()
		log.Info().Msg("Work processor stopped")
	}

	// Stop worker pool (for manual job execution)
	if container.WorkerPool != nil {
		container.WorkerPool.Stop()
		log.Info().Msg("Worker pool stopped")
	}

	// Stop WebSocket client
	if container.MarketStatusWS != nil {
		if err := container.MarketStatusWS.Stop(); err != nil {
			log.Error().Err(err).Msg("Error stopping market status WebSocket")
		} else {
			log.Info().Msg("Market status WebSocket stopped")
		}
	}

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("Server forced to shutdown")
	}

	log.Info().Msg("Server stopped")
}

// Note: registerJobs function has been moved to internal/di/jobs.go
// JobInstances type has been moved to internal/di/types.go
// All dependency wiring is now handled by di.Wire()
// The entire registerJobs function (842 lines) has been extracted to:
//   - internal/di/databases.go (database initialization)
//   - internal/di/repositories.go (repository creation)
//   - internal/di/services.go (service creation - single source of truth)
//   - internal/di/jobs.go (job registration)
//   - internal/di/wire.go (main orchestration)
