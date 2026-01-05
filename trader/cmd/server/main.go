package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/config"
	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/deployment"
	"github.com/aristath/arduino-trader/internal/events"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/cleanup"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning"
	planningevaluation "github.com/aristath/arduino-trader/internal/modules/planning/evaluation"
	planningplanner "github.com/aristath/arduino-trader/internal/modules/planning/planner"
	planningrepo "github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/rebalancing"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/internal/reliability"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/aristath/arduino-trader/internal/server"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/aristath/arduino-trader/internal/ticker"
	"github.com/aristath/arduino-trader/pkg/logger"
	"github.com/rs/zerolog"
)

// getEnv gets environment variable with fallback
func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func main() {
	// Initialize logger
	log := logger.New(logger.Config{
		Level:  "info",
		Pretty: true,
	})

	log.Info().Msg("Starting Arduino Trader")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to load configuration")
	}

	// Initialize databases - NEW 7-database architecture
	// Architecture: universe, config, ledger, portfolio, agents, history, cache
	// All databases use cfg.DataDir which automatically detects ../data or ./data

	// 1. universe.db - Investment universe (securities, groups)
	universeDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/universe.db",
		Profile: database.ProfileStandard,
		Name:    "universe",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize universe database")
	}
	defer universeDB.Close()

	// 2. config.db - Application configuration (REDUCED: settings, allocation targets)
	configDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/config.db",
		Profile: database.ProfileStandard,
		Name:    "config",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize config database")
	}
	defer configDB.Close()

	// Update config from settings DB (credentials, etc.)
	settingsRepo := settings.NewRepository(configDB.Conn(), log)
	if err := cfg.UpdateFromSettings(settingsRepo); err != nil {
		log.Warn().Err(err).Msg("Failed to update config from settings DB, using environment variables")
	}

	// Warn if credentials are loaded from .env (deprecated)
	if cfg.TradernetAPIKey != "" || cfg.TradernetAPISecret != "" {
		// Check if credentials came from env vars (not settings DB)
		apiKeyFromDB, _ := settingsRepo.Get("tradernet_api_key")
		apiSecretFromDB, _ := settingsRepo.Get("tradernet_api_secret")
		usingEnvVars := (apiKeyFromDB == nil || *apiKeyFromDB == "") && cfg.TradernetAPIKey != "" ||
			(apiSecretFromDB == nil || *apiSecretFromDB == "") && cfg.TradernetAPISecret != ""
		if usingEnvVars {
			log.Warn().Msg("Tradernet credentials loaded from .env file - this is deprecated. Please configure credentials via Settings UI (Credentials tab) or API. The .env file will no longer be required in future versions.")
		}
	}

	// 3. ledger.db - Immutable financial audit trail (EXPANDED: trades, cash flows, dividends)
	ledgerDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/ledger.db",
		Profile: database.ProfileLedger, // Maximum safety for immutable audit trail
		Name:    "ledger",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize ledger database")
	}
	defer ledgerDB.Close()

	// 4. portfolio.db - Current portfolio state (positions, scores, metrics, snapshots)
	portfolioDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/portfolio.db",
		Profile: database.ProfileStandard,
		Name:    "portfolio",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize portfolio database")
	}
	defer portfolioDB.Close()

	// 5. agents.db - Strategy management (sequences, evaluations)
	agentsDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/agents.db",
		Profile: database.ProfileStandard,
		Name:    "agents",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize agents database")
	}
	defer agentsDB.Close()

	// 6. history.db - Historical time-series data (prices, rates, cleanup tracking)
	historyDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/history.db",
		Profile: database.ProfileStandard,
		Name:    "history",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize history database")
	}
	defer historyDB.Close()

	// 7. cache.db - Ephemeral operational data (recommendations, cache)
	cacheDB, err := database.New(database.Config{
		Path:    cfg.DataDir + "/cache.db",
		Profile: database.ProfileCache, // Maximum speed for ephemeral data
		Name:    "cache",
	})
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to initialize cache database")
	}
	defer cacheDB.Close()

	// Apply schemas to all databases (single source of truth)
	for _, db := range []*database.DB{universeDB, configDB, ledgerDB, portfolioDB, agentsDB, historyDB, cacheDB} {
		if err := db.Migrate(); err != nil {
			log.Fatal().Err(err).Str("database", db.Name()).Msg("Failed to apply schema")
		}
	}

	// Initialize scheduler
	sched := scheduler.New(log)
	sched.Start()
	defer sched.Stop()

	// Display manager (state holder for LED display) - must be initialized before server.New()
	displayManager := display.NewStateManager(log)
	log.Info().Msg("Display manager initialized")

	// Register background jobs
	jobs, err := registerJobs(sched, universeDB, configDB, ledgerDB, portfolioDB, agentsDB, historyDB, cacheDB, cfg, log, displayManager)
	if err != nil {
		log.Fatal().Err(err).Msg("Failed to register jobs")
	}

	// Initialize deployment manager and handlers if enabled
	var deploymentHandlers *server.DeploymentHandlers
	if cfg.Deployment != nil && cfg.Deployment.Enabled {
		deployConfig := cfg.Deployment.ToDeploymentConfig()
		version := getEnv("VERSION", "dev")
		deploymentManager := deployment.NewManager(deployConfig, version, log)
		deploymentHandlers = server.NewDeploymentHandlers(deploymentManager, log)

		// Register deployment job (runs every 5 minutes)
		deploymentJob := scheduler.NewDeploymentJob(deploymentManager, 5*time.Minute, true, log)
		if err := sched.AddJob("0 */5 * * * *", deploymentJob); err != nil {
			log.Warn().Err(err).Msg("Failed to register deployment job")
		} else {
			log.Info().Msg("Deployment job registered (every 5 minutes)")
		}
	}

	// Initialize HTTP server
	srv := server.New(server.Config{
		Port:               cfg.Port,
		Log:                log,
		UniverseDB:         universeDB,
		ConfigDB:           configDB,
		LedgerDB:           ledgerDB,
		PortfolioDB:        portfolioDB,
		AgentsDB:           agentsDB,
		HistoryDB:          historyDB,
		CacheDB:            cacheDB,
		Config:             cfg,
		DevMode:            cfg.DevMode,
		Scheduler:          sched,
		DisplayManager:     displayManager,
		DeploymentHandlers: deploymentHandlers,
	})

	// Wire up jobs for manual triggering via API
	srv.SetJobs(
		jobs.HealthCheck,
		jobs.SyncCycle,
		jobs.DividendReinvest,
		jobs.PlannerBatch,
		jobs.EventBasedTrading,
	)

	// Start server in goroutine
	go func() {
		if err := srv.Start(); err != nil {
			log.Fatal().Err(err).Msg("Failed to start server")
		}
	}()

	log.Info().Int("port", cfg.Port).Msg("Server started successfully")

	// Start LED status monitors
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start service heartbeat monitor (LED3)
	serviceMonitor := display.NewServiceMonitor("trader", displayManager, log)
	go serviceMonitor.MonitorService(ctx)
	log.Info().Msg("Service heartbeat monitor started (LED3)")

	// Start planner action monitor (LED4)
	recommendationRepo := planning.NewRecommendationRepository(cacheDB.Conn(), log)
	plannerMonitor := display.NewPlannerMonitor(recommendationRepo, displayManager, log)
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

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error().Err(err).Msg("Server forced to shutdown")
	}

	log.Info().Msg("Server stopped")
}

// JobInstances holds references to all registered jobs for manual triggering
type JobInstances struct {
	// Original jobs
	HealthCheck       scheduler.Job
	SyncCycle         scheduler.Job
	DividendReinvest  scheduler.Job
	PlannerBatch      scheduler.Job
	EventBasedTrading scheduler.Job

	// Reliability jobs (Phase 11-15)
	HistoryCleanup     scheduler.Job
	HourlyBackup       scheduler.Job
	DailyBackup        scheduler.Job
	DailyMaintenance   scheduler.Job
	WeeklyBackup       scheduler.Job
	WeeklyMaintenance  scheduler.Job
	MonthlyBackup      scheduler.Job
	MonthlyMaintenance scheduler.Job
}

func registerJobs(sched *scheduler.Scheduler, universeDB, configDB, ledgerDB, portfolioDB, agentsDB, historyDB, cacheDB *database.DB, cfg *config.Config, log zerolog.Logger, displayManager *display.StateManager) (*JobInstances, error) {
	// Initialize required repositories and services for jobs

	// Repositories - NEW 7-database architecture
	positionRepo := portfolio.NewPositionRepository(portfolioDB.Conn(), universeDB.Conn(), log)
	securityRepo := universe.NewSecurityRepository(universeDB.Conn(), log)
	scoreRepo := universe.NewScoreRepository(portfolioDB.Conn(), log)
	dividendRepo := dividends.NewDividendRepository(ledgerDB.Conn(), log)

	// Clients
	tradernetClient := tradernet.NewClient(cfg.TradernetServiceURL, log)
	tradernetClient.SetCredentials(cfg.TradernetAPIKey, cfg.TradernetAPISecret)
	// Use Yahoo Finance microservice client by default (falls back to direct client if microservice unavailable)
	// The microservice uses yfinance which has better browser impersonation and avoids 401 errors
	yahooClient := yahoo.NewMicroserviceClient(cfg.YahooFinanceServiceURL, log)
	log.Info().Str("url", cfg.YahooFinanceServiceURL).Msg("Using Yahoo Finance microservice")

	// Currency exchange service
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, log)

	// Market hours service
	marketHours := scheduler.NewMarketHoursService(log)

	// Cash security manager (cash-as-positions architecture)
	cashManager := cash_flows.NewCashSecurityManager(securityRepo, positionRepo, universeDB.Conn(), portfolioDB.Conn(), log)

	// Trade repository
	tradeRepo := trading.NewTradeRepository(ledgerDB.Conn(), log)

	// Trading and portfolio services
	// Trade safety service with all validation layers
	tradeSafetyService := trading.NewTradeSafetyService(
		tradeRepo,
		positionRepo,
		securityRepo,
		nil, // settingsService - will use defaults
		marketHours,
		log,
	)

	tradingService := trading.NewTradingService(
		trading.NewTradeRepository(ledgerDB.Conn(), log),
		tradernetClient,
		tradeSafetyService,
		log,
	)

	allocRepo := allocation.NewRepository(configDB.Conn(), log)
	portfolioService := portfolio.NewPortfolioService(positionRepo, allocRepo, cashManager, universeDB.Conn(), tradernetClient, currencyExchangeService, log)

	// Event manager (for system events)
	eventManager := events.NewManager(log)

	// === Cash Flows Module ===

	// 1. Create cash flows repository
	cashFlowsRepo := cash_flows.NewRepository(ledgerDB.Conn(), log)

	// 2. Create dividend service implementation (adapter - uses existing dividendRepo)
	dividendService := cash_flows.NewDividendServiceImpl(dividendRepo, log)

	// 3. Create dividend creator
	dividendCreator := cash_flows.NewDividendCreator(dividendService, log)

	// 4. Create deposit processor (simplified - uses CashSecurityManager directly)
	depositProcessor := cash_flows.NewDepositProcessor(cashManager, log)

	// 6. Create Tradernet adapter (adapts tradernet.Client to cash_flows.TradernetClient)
	tradernetAdapter := cash_flows.NewTradernetAdapter(tradernetClient)

	// 7. Create sync job
	syncJob := cash_flows.NewSyncJob(
		cashFlowsRepo,
		depositProcessor,
		dividendCreator,
		tradernetAdapter,
		displayManager,
		eventManager,
		log,
	)

	// 8. Create cash flows service
	cashFlowsService := cash_flows.NewCashFlowsService(syncJob, log)

	// Universe sync services
	historyDBClient := universe.NewHistoryDB(historyDB.Conn(), log)
	historicalSyncService := universe.NewHistoricalSyncService(
		yahooClient,
		securityRepo,
		historyDBClient,
		time.Second*2, // Rate limit delay
		log,
	)
	syncService := universe.NewSyncService(
		securityRepo,
		historicalSyncService,
		yahooClient,
		nil, // scoreCalculator - will be set later if needed
		tradernetClient,
		nil, // setupService - will be set later if needed
		portfolioDB.Conn(),
		log,
	)

	// Universe service with cleanup coordination
	universeService := universe.NewUniverseService(securityRepo, historyDB, portfolioDB, syncService, log)

	// Tag assigner for auto-tagging securities
	tagAssigner := universe.NewTagAssigner(log)

	// === Rebalancing Services ===

	// Settings repository
	settingsRepo := settings.NewRepository(configDB.Conn(), log)

	// Planning recommendation repository
	recommendationRepo := planning.NewRecommendationRepository(cacheDB.Conn(), log)

	// Ticker content service (generates ticker text) - must be initialized before updateDisplayTicker closure
	tickerContentService := ticker.NewTickerContentService(
		portfolioDB.Conn(),
		configDB.Conn(),
		cacheDB.Conn(),
		log,
	)
	log.Info().Msg("Ticker content service initialized")

	// Trade execution service for emergency rebalancing
	tradeExecutionService := services.NewTradeExecutionService(
		tradernetClient,
		tradeRepo,
		positionRepo,
		cashManager, // Use CashSecurityManager directly
		currencyExchangeService,
		log,
	)

	// Negative balance rebalancer
	negativeBalanceRebalancer := rebalancing.NewNegativeBalanceRebalancer(
		log,
		tradernetClient,
		securityRepo,
		positionRepo,
		settingsRepo,
		currencyExchangeService,
		tradeExecutionService,
		recommendationRepo,
		marketHours,
	)

	// Register Job 1: Health Check (daily at 4:00 AM)
	healthCheck := scheduler.NewHealthCheckJob(scheduler.HealthCheckConfig{
		Log:         log,
		DataDir:     cfg.DataDir,
		UniverseDB:  universeDB,
		ConfigDB:    configDB,
		LedgerDB:    ledgerDB,
		PortfolioDB: portfolioDB,
		AgentsDB:    agentsDB,
		HistoryDB:   historyDB,
		CacheDB:     cacheDB,
	})
	if err := sched.AddJob("0 0 4 * * *", healthCheck); err != nil {
		return nil, fmt.Errorf("failed to register health_check job: %w", err)
	}

	// Display ticker update callback (called by sync cycle)
	updateDisplayTicker := func() error {
		text, err := tickerContentService.GenerateTickerText()
		if err != nil {
			log.Error().Err(err).Msg("Failed to generate ticker text")
			return err
		}

		displayManager.SetText(text)

		log.Debug().
			Str("ticker_text", text).
			Msg("Updated display ticker")

		return nil
	}

	// Emergency rebalance callback (called when negative balance detected)
	emergencyRebalance := func() error {
		log.Warn().Msg("EMERGENCY: Executing negative balance rebalancing")

		success, err := negativeBalanceRebalancer.RebalanceNegativeBalances()
		if err != nil {
			return fmt.Errorf("emergency rebalancing failed: %w", err)
		}

		if !success {
			log.Warn().Msg("Emergency rebalancing completed but some issues may remain")
		} else {
			log.Info().Msg("Emergency rebalancing completed successfully")
		}

		return nil
	}

	// Register Job 2: Sync Cycle (every 5 minutes)
	syncCycle := scheduler.NewSyncCycleJob(scheduler.SyncCycleConfig{
		Log:                 log,
		PortfolioService:    portfolioService,
		CashFlowsService:    cashFlowsService,
		TradingService:      tradingService,
		UniverseService:     universeService,
		BalanceService:      nil, // TODO: implement adapter for scheduler.BalanceServiceInterface
		DisplayManager:      displayManager,
		MarketHours:         marketHours,
		EmergencyRebalance:  emergencyRebalance,
		UpdateDisplayTicker: updateDisplayTicker,
	})
	if err := sched.AddJob("0 */5 * * * *", syncCycle); err != nil {
		return nil, fmt.Errorf("failed to register sync_cycle job: %w", err)
	}

	// Register Job 3: Dividend Reinvestment (daily at 10:00 AM)
	dividendReinvest := scheduler.NewDividendReinvestmentJob(scheduler.DividendReinvestmentConfig{
		Log:                   log,
		DividendRepo:          dividendRepo,
		SecurityRepo:          securityRepo,
		ScoreRepo:             scoreRepo,
		PortfolioService:      portfolioService,
		TradingService:        tradingService,
		TradeExecutionService: tradeExecutionService,
		TradernetClient:       tradernetClient,
		YahooClient:           yahooClient,
	})
	if err := sched.AddJob("0 0 10 * * *", dividendReinvest); err != nil {
		return nil, fmt.Errorf("failed to register dividend_reinvestment job: %w", err)
	}

	// Planning module repositories and services
	plannerConfigRepo := planningrepo.NewConfigRepository(configDB, log)
	opportunitiesService := opportunities.NewService(log)

	// Optimization services for correlation filtering and optimizer target weights
	pypfoptClient := optimization.NewPyPFOptClient(cfg.PyPFOptServiceURL, log)
	riskBuilder := optimization.NewRiskModelBuilder(historyDB.Conn(), pypfoptClient, log)

	// Initialize optimizer service for target weights
	constraintsMgr := optimization.NewConstraintsManager(log)
	returnsCalc := optimization.NewReturnsCalculator(configDB.Conn(), yahooClient, log)
	optimizerService := optimization.NewOptimizerService(
		pypfoptClient,
		constraintsMgr,
		returnsCalc,
		riskBuilder,
		log,
	)

	sequencesService := sequences.NewService(log, riskBuilder)
	evaluationService := planningevaluation.NewService(4, log) // 4 workers
	plannerService := planningplanner.NewPlanner(opportunitiesService, sequencesService, evaluationService, log)

	// Register Job 7: Planner Batch (every 15 minutes)
	plannerBatch := scheduler.NewPlannerBatchJob(scheduler.PlannerBatchConfig{
		Log:                    log,
		PositionRepo:           positionRepo,
		SecurityRepo:           securityRepo,
		AllocRepo:              allocRepo,
		TradernetClient:        tradernetClient,
		YahooClient:            yahooClient,
		OptimizerService:       optimizerService, // Added for optimizer target weights
		OpportunitiesService:   opportunitiesService,
		SequencesService:       sequencesService,
		EvaluationService:      evaluationService,
		PlannerService:         plannerService,
		ConfigRepo:             plannerConfigRepo,
		RecommendationRepo:     recommendationRepo,
		PortfolioDB:            portfolioDB.Conn(), // For querying scores and calculations
		ConfigDB:               configDB.Conn(),    // For querying settings
		ScoreRepo:              scoreRepo,          // For querying quality scores
		MinPlanningIntervalMin: 15,                 // Minimum 15 minutes between planning cycles
	})
	if err := sched.AddJob("0 */15 * * * *", plannerBatch); err != nil {
		return nil, fmt.Errorf("failed to register planner_batch job: %w", err)
	}

	// Register Job 8: Event-Based Trading (every 5 minutes)
	eventBasedTrading := scheduler.NewEventBasedTradingJob(scheduler.EventBasedTradingConfig{
		Log:                     log,
		RecommendationRepo:      recommendationRepo,
		TradingService:          tradingService,
		MinExecutionIntervalMin: 30, // Minimum 30 minutes between trade executions
	})
	if err := sched.AddJob("0 */5 * * * *", eventBasedTrading); err != nil {
		return nil, fmt.Errorf("failed to register event_based_trading job: %w", err)
	}

	// ==========================================
	// RELIABILITY JOBS (Phase 11-15)
	// ==========================================

	// Initialize reliability services
	dataDir := cfg.DataDir
	backupDir := cfg.DataDir + "/backups"

	// Create all database references map for reliability services
	databases := map[string]*database.DB{
		"universe":  universeDB,
		"config":    configDB,
		"ledger":    ledgerDB,
		"portfolio": portfolioDB,
		"agents":    agentsDB,
		"history":   historyDB,
		"cache":     cacheDB,
	}

	// Initialize health services for each database
	healthServices := make(map[string]*reliability.DatabaseHealthService)
	healthServices["universe"] = reliability.NewDatabaseHealthService(universeDB, "universe", dataDir+"/universe.db", log)
	healthServices["config"] = reliability.NewDatabaseHealthService(configDB, "config", dataDir+"/config.db", log)
	healthServices["ledger"] = reliability.NewDatabaseHealthService(ledgerDB, "ledger", dataDir+"/ledger.db", log)
	healthServices["portfolio"] = reliability.NewDatabaseHealthService(portfolioDB, "portfolio", dataDir+"/portfolio.db", log)
	healthServices["agents"] = reliability.NewDatabaseHealthService(agentsDB, "agents", dataDir+"/agents.db", log)
	healthServices["history"] = reliability.NewDatabaseHealthService(historyDB, "history", dataDir+"/history.db", log)
	healthServices["cache"] = reliability.NewDatabaseHealthService(cacheDB, "cache", dataDir+"/cache.db", log)

	// Initialize backup service
	backupService := reliability.NewBackupService(databases, dataDir, backupDir, log)

	// Register Job 9: History Cleanup (daily at midnight)
	historyCleanup := cleanup.NewHistoryCleanupJob(historyDB, portfolioDB, universeDB, log)
	if err := sched.AddJob("0 0 0 * * *", historyCleanup); err != nil {
		return nil, fmt.Errorf("failed to register history_cleanup job: %w", err)
	}

	// Register Job 10: Hourly Backup (every hour at :00)
	hourlyBackup := reliability.NewHourlyBackupJob(backupService)
	if err := sched.AddJob("0 0 * * * *", hourlyBackup); err != nil {
		return nil, fmt.Errorf("failed to register hourly_backup job: %w", err)
	}

	// Register Job 11: Daily Backup (daily at 1:00 AM, before maintenance)
	dailyBackup := reliability.NewDailyBackupJob(backupService)
	if err := sched.AddJob("0 0 1 * * *", dailyBackup); err != nil {
		return nil, fmt.Errorf("failed to register daily_backup job: %w", err)
	}

	// Register Job 12: Daily Maintenance (daily at 2:00 AM)
	dailyMaintenance := reliability.NewDailyMaintenanceJob(databases, healthServices, backupDir, log)
	if err := sched.AddJob("0 0 2 * * *", dailyMaintenance); err != nil {
		return nil, fmt.Errorf("failed to register daily_maintenance job: %w", err)
	}

	// Register Tag Update Jobs with per-tag update frequencies
	// The job intelligently updates only tags that need updating based on their frequency
	tagUpdateJob := scheduler.NewTagUpdateJob(scheduler.TagUpdateConfig{
		Log:          log,
		SecurityRepo: securityRepo,
		ScoreRepo:    scoreRepo,
		TagAssigner:  tagAssigner,
		YahooClient:  yahooClient,
		HistoryDB:    historyDBClient,
		PortfolioDB:  portfolioDB.Conn(),
		PositionRepo: positionRepo,
	})

	// Register multiple tag update jobs for different frequency tiers
	// Very Dynamic: Every 10 minutes (price/technical tags)
	if err := sched.AddJob("0 */10 * * * *", tagUpdateJob); err != nil {
		return nil, fmt.Errorf("failed to register tag_update (10min) job: %w", err)
	}

	// Dynamic: Every hour (opportunity/risk tags)
	if err := sched.AddJob("0 0 * * * *", tagUpdateJob); err != nil {
		return nil, fmt.Errorf("failed to register tag_update (hourly) job: %w", err)
	}

	// Stable: Daily at 3:00 AM (quality/characteristic tags)
	if err := sched.AddJob("0 0 3 * * *", tagUpdateJob); err != nil {
		return nil, fmt.Errorf("failed to register tag_update (daily) job: %w", err)
	}

	// Very Stable: Weekly on Sunday at 3:00 AM (long-term tags)
	if err := sched.AddJob("0 0 3 * * 0", tagUpdateJob); err != nil {
		return nil, fmt.Errorf("failed to register tag_update (weekly) job: %w", err)
	}

	// Register Job 13: Weekly Backup (Sunday at 1:00 AM)
	weeklyBackup := reliability.NewWeeklyBackupJob(backupService)
	if err := sched.AddJob("0 0 1 * * 0", weeklyBackup); err != nil {
		return nil, fmt.Errorf("failed to register weekly_backup job: %w", err)
	}

	// Register Job 14: Weekly Maintenance (Sunday at 3:30 AM)
	weeklyMaintenance := reliability.NewWeeklyMaintenanceJob(databases, historyDB, log)
	if err := sched.AddJob("0 30 3 * * 0", weeklyMaintenance); err != nil {
		return nil, fmt.Errorf("failed to register weekly_maintenance job: %w", err)
	}

	// Register Job 15: Monthly Backup (1st day at 1:00 AM)
	// Cron: "0 0 1 1 * *" means: sec=0, min=0, hour=1, day=1, month=*, weekday=*
	monthlyBackup := reliability.NewMonthlyBackupJob(backupService)
	if err := sched.AddJob("0 0 1 1 * *", monthlyBackup); err != nil {
		return nil, fmt.Errorf("failed to register monthly_backup job: %w", err)
	}

	// Register Job 16: Monthly Maintenance (1st day at 4:00 AM)
	monthlyMaintenance := reliability.NewMonthlyMaintenanceJob(databases, healthServices, agentsDB, backupDir, log)
	if err := sched.AddJob("0 0 4 1 * *", monthlyMaintenance); err != nil {
		return nil, fmt.Errorf("failed to register monthly_maintenance job: %w", err)
	}

	log.Info().Int("jobs", 14).Msg("Background jobs registered successfully")

	return &JobInstances{
		// Original jobs
		HealthCheck:       healthCheck,
		SyncCycle:         syncCycle,
		DividendReinvest:  dividendReinvest,
		PlannerBatch:      plannerBatch,
		EventBasedTrading: eventBasedTrading,

		// Reliability jobs
		HistoryCleanup:     historyCleanup,
		HourlyBackup:       hourlyBackup,
		DailyBackup:        dailyBackup,
		DailyMaintenance:   dailyMaintenance,
		WeeklyBackup:       weeklyBackup,
		WeeklyMaintenance:  weeklyMaintenance,
		MonthlyBackup:      monthlyBackup,
		MonthlyMaintenance: monthlyMaintenance,
	}, nil
}
