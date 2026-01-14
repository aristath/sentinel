// Package server provides the HTTP server and routing for Sentinel.
package server

import (
	"context"
	"fmt"
	"io"
	"io/fs"
	"mime"
	"net/http"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/rs/zerolog"

	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/di"
	adaptationhandlers "github.com/aristath/sentinel/internal/modules/adaptation/handlers"
	allocationhandlers "github.com/aristath/sentinel/internal/modules/allocation/handlers"
	analyticshandlers "github.com/aristath/sentinel/internal/modules/analytics/handlers"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	cashflowshandlers "github.com/aristath/sentinel/internal/modules/cash_flows/handlers"
	"github.com/aristath/sentinel/internal/modules/charts"
	chartshandlers "github.com/aristath/sentinel/internal/modules/charts/handlers"
	currencyhandlers "github.com/aristath/sentinel/internal/modules/currency/handlers"
	"github.com/aristath/sentinel/internal/modules/display"
	displayhandlers "github.com/aristath/sentinel/internal/modules/display/handlers"
	dividendhandlers "github.com/aristath/sentinel/internal/modules/dividends/handlers"
	evaluation "github.com/aristath/sentinel/internal/modules/evaluation"
	evaluationhandlers "github.com/aristath/sentinel/internal/modules/evaluation/handlers"
	historicalhandlers "github.com/aristath/sentinel/internal/modules/historical/handlers"
	ledgerhandlers "github.com/aristath/sentinel/internal/modules/ledger/handlers"
	markethourshandlers "github.com/aristath/sentinel/internal/modules/market_hours/handlers"
	opportunitieshandlers "github.com/aristath/sentinel/internal/modules/opportunities/handlers"
	optimizationhandlers "github.com/aristath/sentinel/internal/modules/optimization/handlers"
	planningconfig "github.com/aristath/sentinel/internal/modules/planning/config"
	planninghandlers "github.com/aristath/sentinel/internal/modules/planning/handlers"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	portfoliohandlers "github.com/aristath/sentinel/internal/modules/portfolio/handlers"
	quantumhandlers "github.com/aristath/sentinel/internal/modules/quantum/handlers"
	rebalancinghandlers "github.com/aristath/sentinel/internal/modules/rebalancing/handlers"
	riskhandlers "github.com/aristath/sentinel/internal/modules/risk/handlers"
	scoringhandlers "github.com/aristath/sentinel/internal/modules/scoring/api/handlers"
	sequenceshandlers "github.com/aristath/sentinel/internal/modules/sequences/handlers"
	settingshandlers "github.com/aristath/sentinel/internal/modules/settings/handlers"
	snapshotshandlers "github.com/aristath/sentinel/internal/modules/snapshots/handlers"
	tradinghandlers "github.com/aristath/sentinel/internal/modules/trading/handlers"
	"github.com/aristath/sentinel/internal/modules/universe"
	universehandlers "github.com/aristath/sentinel/internal/modules/universe/handlers"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/pkg/embedded"
)

// Config holds server configuration
type Config struct {
	Log                zerolog.Logger
	UniverseDB         *database.DB
	ConfigDB           *database.DB
	LedgerDB           *database.DB
	PortfolioDB        *database.DB
	HistoryDB          *database.DB
	CacheDB            *database.DB
	Config             *config.Config
	Port               int
	DevMode            bool
	DisplayManager     *display.StateManager
	DeploymentHandlers *DeploymentHandlers
	Container          *di.Container // DI container with all services
}

// Server represents the HTTP server - 7-database architecture
type Server struct {
	router             *chi.Mux
	server             *http.Server
	log                zerolog.Logger
	universeDB         *database.DB
	configDB           *database.DB
	ledgerDB           *database.DB
	portfolioDB        *database.DB
	historyDB          *database.DB
	cacheDB            *database.DB
	cfg                *config.Config
	container          *di.Container // DI container with all services
	displayManager     *display.StateManager
	systemHandlers     *SystemHandlers
	deploymentHandlers *DeploymentHandlers
	r2BackupHandlers   *R2BackupHandlers
	statusMonitor      *StatusMonitor
}

// New creates a new HTTP server
func New(cfg Config) *Server {
	// Register common MIME types to ensure correct Content-Type headers
	_ = mime.AddExtensionType(".js", "application/javascript")
	_ = mime.AddExtensionType(".mjs", "application/javascript")
	_ = mime.AddExtensionType(".css", "text/css")
	_ = mime.AddExtensionType(".woff2", "font/woff2")
	_ = mime.AddExtensionType(".woff", "font/woff")

	// Initialize system handlers early
	// Use services from container instead of creating new ones
	dataDir := cfg.Config.DataDir

	// Use services from container (single source of truth)
	tradernetClient := cfg.Container.BrokerClient
	currencyExchangeService := cfg.Container.CurrencyExchangeService
	cashManagerForSystem := cfg.Container.CashManager
	marketHoursService := cfg.Container.MarketHoursService

	systemHandlers := NewSystemHandlers(
		cfg.Log,
		dataDir,
		cfg.PortfolioDB,
		cfg.ConfigDB,
		cfg.UniverseDB,
		cfg.HistoryDB,
		cfg.Container.QueueManager,
		cfg.DisplayManager,
		tradernetClient,
		currencyExchangeService,
		cashManagerForSystem,
		marketHoursService,
		cfg.Container.MarketStatusWS,
	)

	// Initialize R2 backup handlers if R2 is configured
	var r2BackupHandlers *R2BackupHandlers
	if cfg.Container.R2BackupService != nil && cfg.Container.RestoreService != nil {
		r2BackupHandlers = NewR2BackupHandlers(
			cfg.Container.R2BackupService,
			cfg.Container.RestoreService,
			cfg.Container.QueueManager,
			cfg.Log,
		)
	}

	s := &Server{
		router:             chi.NewRouter(),
		log:                cfg.Log.With().Str("component", "server").Logger(),
		universeDB:         cfg.UniverseDB,
		configDB:           cfg.ConfigDB,
		ledgerDB:           cfg.LedgerDB,
		portfolioDB:        cfg.PortfolioDB,
		historyDB:          cfg.HistoryDB,
		cacheDB:            cfg.CacheDB,
		cfg:                cfg.Config,
		container:          cfg.Container,
		displayManager:     cfg.DisplayManager,
		systemHandlers:     systemHandlers,
		deploymentHandlers: cfg.DeploymentHandlers,
		r2BackupHandlers:   r2BackupHandlers,
		statusMonitor:      nil, // Will be initialized after setupRoutes
	}

	// Initialize status monitor
	s.statusMonitor = NewStatusMonitor(
		cfg.Container.EventManager,
		systemHandlers,
		cfg.Log,
	)

	s.setupMiddleware(cfg.DevMode)
	s.setupRoutes()

	s.server = &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      s.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return s
}

// SetJobs registers job instances for manual triggering via API
func (s *Server) SetJobs(
	healthCheck scheduler.Job,
	syncCycle scheduler.Job,
	dividendReinvest scheduler.Job,
	plannerBatch scheduler.Job,
	eventBasedTrading scheduler.Job,
	tagUpdate scheduler.Job,
	// Individual sync jobs
	syncTrades scheduler.Job,
	syncCashFlows scheduler.Job,
	syncPortfolio scheduler.Job,
	syncPrices scheduler.Job,
	checkNegativeBalances scheduler.Job,
	updateDisplayTicker scheduler.Job,
	// Individual planning jobs
	generatePortfolioHash scheduler.Job,
	getOptimizerWeights scheduler.Job,
	buildOpportunityContext scheduler.Job,
	createTradePlan scheduler.Job,
	storeRecommendations scheduler.Job,
	// Individual dividend jobs
	getUnreinvestedDividends scheduler.Job,
	groupDividendsBySymbol scheduler.Job,
	checkDividendYields scheduler.Job,
	createDividendRecommendations scheduler.Job,
	setPendingBonuses scheduler.Job,
	executeDividendTrades scheduler.Job,
	// Individual health check jobs
	checkCoreDatabases scheduler.Job,
	checkHistoryDatabases scheduler.Job,
	checkWALCheckpoints scheduler.Job,
) {
	s.systemHandlers.SetJobs(
		healthCheck,
		syncCycle,
		dividendReinvest,
		plannerBatch,
		eventBasedTrading,
		tagUpdate,
		syncTrades,
		syncCashFlows,
		syncPortfolio,
		syncPrices,
		checkNegativeBalances,
		updateDisplayTicker,
		generatePortfolioHash,
		getOptimizerWeights,
		buildOpportunityContext,
		createTradePlan,
		storeRecommendations,
		getUnreinvestedDividends,
		groupDividendsBySymbol,
		checkDividendYields,
		createDividendRecommendations,
		setPendingBonuses,
		executeDividendTrades,
		checkCoreDatabases,
		checkHistoryDatabases,
		checkWALCheckpoints,
	)
}

// SetTagUpdateJob sets the tag update job (called after job registration)
func (s *Server) SetTagUpdateJob(tagUpdate scheduler.Job) {
	s.systemHandlers.SetTagUpdateJob(tagUpdate)
}

// setupMiddleware configures middleware
func (s *Server) setupMiddleware(devMode bool) {
	// Recovery from panics
	s.router.Use(middleware.Recoverer)

	// Request ID
	s.router.Use(middleware.RequestID)

	// Real IP
	s.router.Use(middleware.RealIP)

	// Logging
	s.router.Use(s.loggingMiddleware)

	// Timeout
	s.router.Use(middleware.Timeout(60 * time.Second))

	// CORS
	s.router.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		ExposedHeaders:   []string{"Link"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Compress responses
	if !devMode {
		s.router.Use(middleware.Compress(5))
	}
}

// setupRoutes configures all routes
func (s *Server) setupRoutes() {
	// Health check (before SPA routing)
	s.router.Get("/health", s.handleHealth)

	// API routes
	s.router.Route("/api", func(r chi.Router) {
		// Version endpoint
		r.Get("/version", s.handleVersion)

		// Unified events stream (SSE) - must be before other routes for proper handling
		eventsStreamHandler := NewEventsStreamHandler(s.container.EventBus, s.cfg.DataDir, s.log)
		r.Get("/events/stream", eventsStreamHandler.ServeHTTP)

		// System monitoring and operations
		// Use server's system handlers instance
		systemHandlers := s.systemHandlers

		// Initialize log handlers
		logHandlers := NewLogHandlers(s.log)

		// Use services from container (single source of truth)
		securityRepo := s.container.SecurityRepo
		scoreRepo := s.container.ScoreRepo
		positionRepo := s.container.PositionRepo
		securityScorer := s.container.SecurityScorer
		historyDB := s.container.HistoryDBClient
		setupService1 := s.container.SetupService
		syncService1 := s.container.SyncService
		currencyExchangeService1 := s.container.CurrencyExchangeService

		systemUniverseHandlers := universehandlers.NewUniverseHandlers(
			securityRepo,
			scoreRepo,
			s.portfolioDB.Conn(),
			positionRepo,
			securityScorer,
			historyDB,
			setupService1,
			s.container.SecurityDeletionService,
			syncService1,
			currencyExchangeService1,
			s.container.EventManager,
			s.log,
		)

		// Wire score calculator
		setupService1.SetScoreCalculator(systemUniverseHandlers)
		syncService1.SetScoreCalculator(systemUniverseHandlers)

		// System routes (complete Phase 1 implementation)
		r.Route("/system", func(r chi.Router) {
			// Status and monitoring
			r.Get("/status", systemHandlers.HandleSystemStatus)
			r.Get("/led/display", systemHandlers.HandleLEDDisplay)
			r.Get("/tradernet", systemHandlers.HandleTradernetStatus)
			r.Get("/pending-orders", systemHandlers.HandlePendingOrders)
			r.Get("/jobs", systemHandlers.HandleJobsStatus)
			r.Get("/markets", systemHandlers.HandleMarketsStatus)
			r.Get("/database/stats", systemHandlers.HandleDatabaseStats)
			r.Get("/disk", systemHandlers.HandleDiskUsage)

			// MCU/Display hardware operations
			r.Route("/mcu", func(r chi.Router) {
				r.Post("/upload-sketch", systemHandlers.HandleUploadSketch)
			})

			// Log access
			r.Get("/logs/list", logHandlers.HandleListLogs)
			r.Get("/logs", logHandlers.HandleGetLogs)
			r.Get("/logs/errors", logHandlers.HandleGetErrors)

			// Sync operation triggers
			r.Route("/sync", func(r chi.Router) {
				r.Post("/prices", systemUniverseHandlers.HandleSyncPrices)
				r.Post("/historical", systemUniverseHandlers.HandleSyncHistorical)
				r.Post("/rebuild-universe", systemUniverseHandlers.HandleRebuildUniverse)
				r.Post("/securities-data", systemUniverseHandlers.HandleSyncSecuritiesData)
				r.Post("/portfolio", systemHandlers.HandleSyncPortfolio)
				r.Post("/daily-pipeline", systemHandlers.HandleSyncDailyPipeline)
				r.Post("/recommendations", systemHandlers.HandleSyncRecommendations)
			})

			// Job triggers (manual operation triggers)
			r.Route("/jobs", func(r chi.Router) {
				// Original composite jobs
				r.Post("/health-check", systemHandlers.HandleTriggerHealthCheck)
				r.Post("/sync-cycle", systemHandlers.HandleTriggerSyncCycle)
				r.Post("/dividend-reinvestment", systemHandlers.HandleTriggerDividendReinvestment)
				r.Post("/planner-batch", systemHandlers.HandleTriggerPlannerBatch)
				r.Post("/event-based-trading", systemHandlers.HandleTriggerEventBasedTrading)
				r.Post("/tag-update", systemHandlers.HandleTriggerTagUpdate)

				// Individual sync jobs
				r.Post("/sync-trades", systemHandlers.HandleTriggerSyncTrades)
				r.Post("/sync-cash-flows", systemHandlers.HandleTriggerSyncCashFlows)
				r.Post("/sync-portfolio", systemHandlers.HandleTriggerSyncPortfolio)
				r.Post("/sync-prices", systemHandlers.HandleTriggerSyncPrices)
				r.Post("/check-negative-balances", systemHandlers.HandleTriggerCheckNegativeBalances)
				r.Post("/update-display-ticker", systemHandlers.HandleTriggerUpdateDisplayTicker)

				// Individual planning jobs
				r.Post("/generate-portfolio-hash", systemHandlers.HandleTriggerGeneratePortfolioHash)
				r.Post("/get-optimizer-weights", systemHandlers.HandleTriggerGetOptimizerWeights)
				r.Post("/build-opportunity-context", systemHandlers.HandleTriggerBuildOpportunityContext)
				r.Post("/create-trade-plan", systemHandlers.HandleTriggerCreateTradePlan)
				r.Post("/store-recommendations", systemHandlers.HandleTriggerStoreRecommendations)

				// Individual dividend jobs
				r.Post("/get-unreinvested-dividends", systemHandlers.HandleTriggerGetUnreinvestedDividends)
				r.Post("/group-dividends-by-symbol", systemHandlers.HandleTriggerGroupDividendsBySymbol)
				r.Post("/check-dividend-yields", systemHandlers.HandleTriggerCheckDividendYields)
				r.Post("/create-dividend-recommendations", systemHandlers.HandleTriggerCreateDividendRecommendations)
				r.Post("/set-pending-bonuses", systemHandlers.HandleTriggerSetPendingBonuses)
				r.Post("/execute-dividend-trades", systemHandlers.HandleTriggerExecuteDividendTrades)

				// Individual health check jobs
				r.Post("/check-core-databases", systemHandlers.HandleTriggerCheckCoreDatabases)
				r.Post("/check-history-databases", systemHandlers.HandleTriggerCheckHistoryDatabases)
				r.Post("/check-wal-checkpoints", systemHandlers.HandleTriggerCheckWALCheckpoints)
			})
		})

		// Allocation module
		allocRepo := s.container.AllocRepo
		allocRepo.SetUniverseDB(s.universeDB.Conn())
		alertService := s.container.ConcentrationAlertService
		portfolioService := s.container.PortfolioService
		portfolioSummaryAdapter := portfolio.NewPortfolioSummaryAdapter(portfolioService)
		allocationHandler := allocationhandlers.NewHandler(allocRepo, alertService, portfolioSummaryAdapter, s.container.EventManager, s.log)
		allocationHandler.RegisterRoutes(r)

		// Portfolio module
		portfolioPositionRepo := s.container.PositionRepo
		portfolioTradernetClient := s.container.BrokerClient
		portfolioCurrencyExchangeService := s.container.CurrencyExchangeService
		portfolioCashManager := s.container.CashManager
		// portfolioService already declared above for allocation module
		portfolioHandler := portfoliohandlers.NewHandler(portfolioPositionRepo, portfolioService, portfolioTradernetClient, portfolioCurrencyExchangeService, portfolioCashManager, s.configDB.Conn(), s.log)
		portfolioHandler.RegisterRoutes(r)

		// Universe module
		universeSecurityRepo := s.container.SecurityRepo
		universeScoreRepo := s.container.ScoreRepo
		universePositionRepo := s.container.PositionRepo
		universeSecurityScorer := s.container.SecurityScorer
		universeHistoryDB := s.container.HistoryDBClient
		universeSetupService := s.container.SetupService
		universeSyncService := s.container.SyncService
		universeCurrencyExchangeService := s.container.CurrencyExchangeService
		universeHandler := universehandlers.NewUniverseHandlers(
			universeSecurityRepo,
			universeScoreRepo,
			s.portfolioDB.Conn(), // Pass portfolioDB for GetWithScores
			universePositionRepo,
			universeSecurityScorer,
			universeHistoryDB,
			universeSetupService,
			s.container.SecurityDeletionService,
			universeSyncService,
			universeCurrencyExchangeService,
			s.container.EventManager,
			s.log,
		)
		// Wire the score calculator (handler implements the interface)
		// Note: This wiring is already done in services.go, but we do it here too
		// to ensure handlers created in other routes also have it wired
		universeSetupService.SetScoreCalculator(universeHandler)
		universeSyncService.SetScoreCalculator(universeHandler)
		universeHandler.RegisterRoutes(r)

		// Trading module
		tradingTradeRepo := s.container.TradeRepo
		tradingSecurityRepo := s.container.SecurityRepo
		tradingSecurityFetcher := &securityFetcherAdapter{repo: tradingSecurityRepo}
		tradingTradernetClient := s.container.BrokerClient
		tradingPortfolioService := s.container.PortfolioService
		tradingAlertService := s.container.ConcentrationAlertService
		tradingSettingsService := s.container.SettingsService
		tradingSafetyService := s.container.TradeSafetyService
		tradingRecommendationRepo := s.container.RecommendationRepo
		// Use in-memory planner repository from DI container
		tradingPlannerRepo := s.container.PlannerRepo
		tradingHandler := tradinghandlers.NewTradingHandlers(
			tradingTradeRepo,
			tradingSecurityFetcher,
			tradingPortfolioService,
			tradingAlertService, // ConcentrationAlertService implements ConcentrationAlertProvider
			tradingTradernetClient,
			tradingSafetyService,
			tradingSettingsService,
			tradingRecommendationRepo,
			tradingPlannerRepo,
			s.container.EventManager,
			s.log,
		)
		tradingHandler.RegisterRoutes(r)

		// Dividends module
		dividendRepo := s.container.DividendRepo
		dividendHandler := dividendhandlers.NewDividendHandlers(dividendRepo, s.log)
		dividendHandler.RegisterRoutes(r)

		// Display module
		// Display manager is passed in via server config, not container
		// (it's initialized before container in main.go)
		displayHandler := displayhandlers.NewHandlers(
			s.displayManager,
			s.container.ModeManager,
			s.container.HealthCalculator,
			s.container.HealthUpdater,
			s.log,
		)
		displayHandler.RegisterRoutes(r)

		// Scoring module
		scoringHandler := scoringhandlers.NewHandlers(s.log)
		scoringHandler.RegisterRoutes(r)

		// Optimization module
		optimizationTradernetClient := s.container.BrokerClient
		optimizationDividendRepo := s.container.DividendRepo
		optimizationCurrencyExchangeService := s.container.CurrencyExchangeService
		optimizationCashManager := s.container.CashManager
		optimizationService := s.container.OptimizerService
		optimizationPlannerConfigRepo := s.container.PlannerConfigRepo
		optimizationHandler := optimizationhandlers.NewHandler(
			optimizationService,
			s.configDB.Conn(),
			optimizationTradernetClient,
			optimizationCurrencyExchangeService,
			optimizationDividendRepo,
			optimizationCashManager,
			optimizationPlannerConfigRepo,
			s.log,
		)
		optimizationHandler.RegisterRoutes(r)

		// Cash-flows module
		cashFlowsRepo := s.container.CashFlowsRepo
		cashFlowsDepositProcessor := s.container.DepositProcessor
		cashFlowsTradernetClient := s.container.BrokerClient
		// Initialize schema
		if err := cash_flows.InitSchema(s.ledgerDB.Conn()); err != nil {
			s.log.Fatal().Err(err).Msg("Failed to initialize cash_flows schema")
		}
		// Initialize Tradernet adapter
		cashFlowsTradernetAdapter := cash_flows.NewTradernetAdapter(cashFlowsTradernetClient)
		// Initialize handler
		cashFlowsHandler := cashflowshandlers.NewHandler(
			cashFlowsRepo,
			cashFlowsDepositProcessor,
			cashFlowsTradernetAdapter,
			s.log,
		)
		cashFlowsHandler.RegisterRoutes(r)

		// Planning module
		planningService := s.container.PlanningService
		planningConfigRepo := s.container.PlannerConfigRepo
		planningPlannerRepo := s.container.PlannerRepo // Use in-memory planner repo from container
		planningDismissedFilterRepo := s.container.DismissedFilterRepo
		planningValidator := planningconfig.NewValidator()
		planningEventBroadcaster := planninghandlers.NewEventBroadcaster(s.log)
		planningHandler := planninghandlers.NewHandler(
			planningService,
			planningConfigRepo,
			planningPlannerRepo,
			planningDismissedFilterRepo,
			planningValidator,
			planningEventBroadcaster,
			s.container.EventManager,
			s.container.TradeExecutionService, // Trade executor for plan execution
			s.log,
		)
		planningHandler.RegisterRoutes(r)

		// Charts module
		chartsSecurityRepo := s.container.SecurityRepo
		chartsService := charts.NewService(
			s.historyDB.Conn(),
			chartsSecurityRepo,
			s.universeDB.Conn(),
			s.log,
		)
		chartsHandler := chartshandlers.NewHandler(chartsService, s.log)
		chartsHandler.RegisterRoutes(r)

		// Deployment module
		if s.deploymentHandlers != nil {
			s.deploymentHandlers.RegisterRoutes(r)
		}

		// Settings module
		settingsService := s.container.SettingsService
		settingsHandler := settingshandlers.NewHandler(settingsService, s.container.EventManager, s.log)
		settingsHandler.SetDisplayModeSwitcher(s.container.ModeManager)
		settingsHandler.RegisterRoutes(r)

		// R2 Cloud Backup routes (optional - only if R2 configured)
		if s.r2BackupHandlers != nil {
			r.Route("/backups/r2", func(r chi.Router) {
				r.Get("/", s.r2BackupHandlers.HandleListBackups)
				r.Post("/", s.r2BackupHandlers.HandleCreateBackup)
				r.Post("/test", s.r2BackupHandlers.HandleTestConnection)
				r.Delete("/{filename}", s.r2BackupHandlers.HandleDeleteBackup)
				r.Get("/{filename}/download", s.r2BackupHandlers.HandleDownloadBackup)
				r.Post("/restore", s.r2BackupHandlers.HandleStageRestore)
				r.Delete("/restore/staged", s.r2BackupHandlers.HandleCancelRestore)
			})
		}

		// Symbolic Regression module
		// Analytics module (Factor Exposure, etc.)
		analyticsHandler := analyticshandlers.NewHandler(
			s.container.FactorExposureTracker,
			s.portfolioDB.Conn(),
			s.log,
		)
		analyticsHandler.RegisterRoutes(r)

		// Market Hours module (API extension)
		marketHoursHandler := s.createMarketHoursHandler()
		marketHoursHandler.RegisterRoutes(r)

		// Historical Data module (API extension)
		historicalHandler := s.createHistoricalHandler()
		historicalHandler.RegisterRoutes(r)

		// Risk Metrics module (API extension)
		riskHandler := s.createRiskHandler()
		riskHandler.RegisterRoutes(r)

		// Adaptation (Market Regime) module (API extension)
		adaptationHandler := s.createAdaptationHandler()
		adaptationHandler.RegisterRoutes(r)

		// Opportunities module (API extension)
		opportunitiesHandler := s.createOpportunitiesHandler()
		opportunitiesHandler.RegisterRoutes(r)

		// Ledger module (API extension)
		ledgerHandler := s.createLedgerHandler()
		ledgerHandler.RegisterRoutes(r)

		// Snapshots module (API extension)
		snapshotsHandler := s.createSnapshotsHandler()
		snapshotsHandler.RegisterRoutes(r)

		// Sequences module (API extension)
		sequencesHandler := s.createSequencesHandler()
		sequencesHandler.RegisterRoutes(r)

		// Rebalancing module (API extension)
		rebalancingHandler := s.createRebalancingHandler()
		rebalancingHandler.RegisterRoutes(r)

		// Currency module (API extension)
		currencyHandler := s.createCurrencyHandler()
		currencyHandler.RegisterRoutes(r)

		// Quantum module (API extension)
		quantumHandler := s.createQuantumHandler()
		quantumHandler.RegisterRoutes(r)
	})

	// Evaluation module routes
	// Mounted directly under /api/v1
	numWorkers := runtime.NumCPU()
	if numWorkers < 2 {
		numWorkers = 2
	}
	evalService := evaluation.NewService(numWorkers, s.log)
	evalHandler := evaluationhandlers.NewHandler(evalService, s.log)
	evalHandler.RegisterRoutes(s.router)

	// Serve built frontend files from embedded filesystem
	// Frontend files are embedded in the binary at frontend/dist
	// Create a sub-FS for the frontend directory
	frontendFS, err := fs.Sub(embedded.Files, "frontend/dist")
	if err != nil {
		s.log.Error().Err(err).Msg("Failed to create frontend filesystem from embedded files")
	} else {
		// Serve built frontend assets (Vite outputs to /assets/)
		// Files are at frontend/dist/assets/, so serve from assets subdirectory
		assetsFS, err := fs.Sub(frontendFS, "assets")
		if err != nil {
			s.log.Warn().Err(err).Msg("Frontend assets directory not found in embedded files")
		} else {
			fileServer := http.FileServer(http.FS(assetsFS))
			// Wrap file server with MIME type handler to ensure correct Content-Type headers
			assetsHandler := s.assetsHandler(fileServer)
			s.router.Handle("/assets/*", http.StripPrefix("/assets/", assetsHandler))
		}

		// Serve index.html for root and all non-API routes (SPA routing)
		s.router.Get("/", s.handleDashboard)
		s.router.NotFound(func(w http.ResponseWriter, r *http.Request) {
			if !strings.HasPrefix(r.URL.Path, "/api") && !strings.HasPrefix(r.URL.Path, "/health") {
				// Serve index.html from embedded filesystem
				indexFile, err := frontendFS.Open("index.html")
				if err != nil {
					s.log.Error().Err(err).Msg("Failed to open embedded index.html")
					http.NotFound(w, r)
					return
				}
				defer indexFile.Close()
				// Read file content and serve it
				data, err := io.ReadAll(indexFile)
				if err != nil {
					s.log.Error().Err(err).Msg("Failed to read embedded index.html")
					http.NotFound(w, r)
					return
				}
				w.Header().Set("Content-Type", "text/html; charset=utf-8")
				if _, err := w.Write(data); err != nil {
					s.log.Error().Err(err).Msg("Failed to write index.html response")
				}
			} else {
				http.NotFound(w, r)
			}
		})
	}
}

// securityFetcherAdapter adapts universe.SecurityRepository to trading.SecurityFetcher interface
type securityFetcherAdapter struct {
	repo *universe.SecurityRepository
}

func (a *securityFetcherAdapter) GetSecurityName(symbol string) (string, error) {
	security, err := a.repo.GetBySymbol(symbol)
	if err != nil {
		return "", err
	}
	if security == nil {
		return symbol, nil // Return symbol if not found
	}
	return security.Name, nil
}

// Start starts the HTTP server and background monitors
func (s *Server) Start() error {
	// Start status monitor (check every 60 seconds)
	if s.statusMonitor != nil {
		s.statusMonitor.Start(60 * time.Second)
		s.log.Info().Msg("Status monitor started")
	}

	s.log.Info().Int("port", s.cfg.Port).Msg("Starting HTTP server")
	return s.server.ListenAndServe()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown(ctx context.Context) error {
	s.log.Info().Msg("Shutting down HTTP server")
	return s.server.Shutdown(ctx)
}

// assetsHandler wraps the file server to set correct MIME types
func (s *Server) assetsHandler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Get the file path from the request
		filePath := r.URL.Path

		// Get file extension
		ext := filepath.Ext(filePath)

		// Set MIME type based on extension
		contentType := mime.TypeByExtension(ext)
		if contentType == "" {
			// Fallback for common extensions
			switch ext {
			case ".js":
				contentType = "application/javascript"
			case ".mjs":
				contentType = "application/javascript"
			case ".css":
				contentType = "text/css"
			case ".json":
				contentType = "application/json"
			case ".woff", ".woff2":
				contentType = "font/woff2"
			case ".ttf":
				contentType = "font/ttf"
			case ".svg":
				contentType = "image/svg+xml"
			default:
				contentType = "application/octet-stream"
			}
		}

		// Set Content-Type header
		if contentType != "" {
			w.Header().Set("Content-Type", contentType)
		}

		// Serve the file
		next.ServeHTTP(w, r)
	})
}

// handleDashboard serves the main dashboard HTML from embedded filesystem
func (s *Server) handleDashboard(w http.ResponseWriter, r *http.Request) {
	// Get frontend filesystem from embedded files
	// The embed path is frontend/dist relative to the embedded package
	frontendFS, err := fs.Sub(embedded.Files, "frontend/dist")
	if err != nil {
		s.log.Error().Err(err).Msg("Failed to create frontend filesystem from embedded files")
		http.Error(w, "Frontend not available", http.StatusInternalServerError)
		return
	}

	// Open and serve index.html from embedded filesystem
	indexFile, err := frontendFS.Open("index.html")
	if err != nil {
		s.log.Error().Err(err).Msg("Failed to open embedded index.html")
		http.Error(w, "Frontend not available", http.StatusInternalServerError)
		return
	}
	defer indexFile.Close()

	// Read file content and serve it
	data, err := io.ReadAll(indexFile)
	if err != nil {
		s.log.Error().Err(err).Msg("Failed to read embedded index.html")
		http.Error(w, "Frontend not available", http.StatusInternalServerError)
		return
	}

	// Set content type
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if _, err := w.Write(data); err != nil {
		s.log.Error().Err(err).Msg("Failed to write index.html response")
	}
}

// loggingMiddleware logs HTTP requests
func (s *Server) loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)

		s.log.Info().
			Str("method", r.Method).
			Str("path", r.URL.Path).
			Int("status", ww.Status()).
			Int("bytes", ww.BytesWritten()).
			Dur("duration_ms", time.Since(start)).
			Str("request_id", middleware.GetReqID(r.Context())).
			Msg("HTTP request")
	})
}

// createMarketHoursHandler creates a handler for market hours endpoints
func (s *Server) createMarketHoursHandler() *markethourshandlers.Handler {
	return markethourshandlers.NewHandler(
		s.container.MarketHoursService,
		s.log,
	)
}

// createHistoricalHandler creates a handler for historical data endpoints
func (s *Server) createHistoricalHandler() *historicalhandlers.Handler {
	return historicalhandlers.NewHandler(
		s.container.HistoryDBClient,
		s.log,
	)
}

// createRiskHandler creates a handler for risk metrics endpoints
func (s *Server) createRiskHandler() *riskhandlers.Handler {
	return riskhandlers.NewHandler(
		s.container.HistoryDBClient,
		s.container.PositionRepo,
		s.log,
	)
}

// createAdaptationHandler creates a handler for adaptation/regime endpoints
func (s *Server) createAdaptationHandler() *adaptationhandlers.Handler {
	return adaptationhandlers.NewHandler(
		s.configDB.Conn(),
		s.container.AdaptiveMarketService,
		s.log,
	)
}

// createOpportunitiesHandler creates a handler for opportunities endpoints
func (s *Server) createOpportunitiesHandler() *opportunitieshandlers.Handler {
	return opportunitieshandlers.NewHandler(
		s.container.OpportunitiesService,
		s.container.PlannerConfigRepo,
		s.container.OpportunityContextBuilder,
		s.log,
	)
}

// createLedgerHandler creates a handler for ledger endpoints
func (s *Server) createLedgerHandler() *ledgerhandlers.Handler {
	return ledgerhandlers.NewHandler(
		s.ledgerDB.Conn(),
		s.log,
	)
}

// createSnapshotsHandler creates a handler for snapshot endpoints
func (s *Server) createSnapshotsHandler() *snapshotshandlers.Handler {
	return snapshotshandlers.NewHandler(
		s.container.PositionRepo,
		s.container.HistoryDBClient,
		s.ledgerDB.Conn(),
		s.configDB.Conn(),
		s.container.CashManager,
		s.container.AdaptiveMarketService,
		s.container.MarketHoursService,
		s.log,
	)
}

// createSequencesHandler creates a handler for sequences endpoints
func (s *Server) createSequencesHandler() *sequenceshandlers.Handler {
	return sequenceshandlers.NewHandler(
		s.container.SequencesService,
		s.log,
	)
}

// createRebalancingHandler creates a handler for rebalancing endpoints
func (s *Server) createRebalancingHandler() *rebalancinghandlers.Handler {
	return rebalancinghandlers.NewHandler(
		s.container.RebalancingService,
		s.log,
	)
}

// createCurrencyHandler creates a handler for currency endpoints
func (s *Server) createCurrencyHandler() *currencyhandlers.Handler {
	return currencyhandlers.NewHandler(
		s.container.CurrencyExchangeService,
		s.container.ExchangeRateCacheService,
		s.container.CashManager,
		s.log,
	)
}

// createQuantumHandler creates a handler for quantum endpoints
func (s *Server) createQuantumHandler() *quantumhandlers.Handler {
	return quantumhandlers.NewHandler(
		s.container.QuantumCalculator,
		s.log,
	)
}
