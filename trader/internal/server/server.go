package server

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/config"
	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/events"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/display"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/aristath/arduino-trader/internal/modules/evaluation"
	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning"
	planningconfig "github.com/aristath/arduino-trader/internal/modules/planning/config"
	planningevaluation "github.com/aristath/arduino-trader/internal/modules/planning/evaluation"
	planningrepo "github.com/aristath/arduino-trader/internal/modules/planning/repository"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/rebalancing"
	"github.com/aristath/arduino-trader/internal/modules/satellites"
	"github.com/aristath/arduino-trader/internal/modules/scoring/api"
	"github.com/aristath/arduino-trader/internal/modules/scoring/scorers"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/aristath/arduino-trader/internal/services"
)

// Config holds server configuration - NEW 8-database architecture
type Config struct {
	Log                zerolog.Logger
	UniverseDB         *database.DB
	ConfigDB           *database.DB
	LedgerDB           *database.DB
	PortfolioDB        *database.DB
	SatellitesDB       *database.DB
	AgentsDB           *database.DB
	HistoryDB          *database.DB
	CacheDB            *database.DB
	Config             *config.Config
	Port               int
	DevMode            bool
	Scheduler          *scheduler.Scheduler
	DisplayManager     *display.StateManager
	DeploymentHandlers *DeploymentHandlers
}

// Server represents the HTTP server - NEW 8-database architecture
type Server struct {
	router             *chi.Mux
	server             *http.Server
	log                zerolog.Logger
	universeDB         *database.DB
	configDB           *database.DB
	ledgerDB           *database.DB
	portfolioDB        *database.DB
	satellitesDB       *database.DB
	agentsDB           *database.DB
	historyDB          *database.DB
	cacheDB            *database.DB
	cfg                *config.Config
	systemHandlers     *SystemHandlers
	scheduler          *scheduler.Scheduler
	deploymentHandlers *DeploymentHandlers
}

// New creates a new HTTP server
func New(cfg Config) *Server {
	// Initialize system handlers early
	dataDir := filepath.Dir(cfg.Config.DatabasePath)

	// Create Tradernet client for system handlers
	tradernetClient := tradernet.NewClient(cfg.Config.TradernetServiceURL, cfg.Log)
	tradernetClient.SetCredentials(cfg.Config.TradernetAPIKey, cfg.Config.TradernetAPISecret)

	// Create currency exchange service for cash balance calculations
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, cfg.Log)

	systemHandlers := NewSystemHandlers(
		cfg.Log,
		dataDir,
		cfg.PortfolioDB,
		cfg.ConfigDB,
		cfg.UniverseDB,
		cfg.Scheduler,
		cfg.DisplayManager,
		tradernetClient,
		currencyExchangeService,
	)

	s := &Server{
		router:             chi.NewRouter(),
		log:                cfg.Log.With().Str("component", "server").Logger(),
		universeDB:         cfg.UniverseDB,
		configDB:           cfg.ConfigDB,
		ledgerDB:           cfg.LedgerDB,
		portfolioDB:        cfg.PortfolioDB,
		satellitesDB:       cfg.SatellitesDB,
		agentsDB:           cfg.AgentsDB,
		historyDB:          cfg.HistoryDB,
		cacheDB:            cfg.CacheDB,
		cfg:                cfg.Config,
		systemHandlers:     systemHandlers,
		scheduler:          cfg.Scheduler,
		deploymentHandlers: cfg.DeploymentHandlers,
	}

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
	satelliteMaintenance scheduler.Job,
	satelliteReconciliation scheduler.Job,
	satelliteEvaluation scheduler.Job,
	plannerBatch scheduler.Job,
	eventBasedTrading scheduler.Job,
) {
	s.systemHandlers.SetJobs(
		healthCheck,
		syncCycle,
		dividendReinvest,
		satelliteMaintenance,
		satelliteReconciliation,
		satelliteEvaluation,
		plannerBatch,
		eventBasedTrading,
	)
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
		// System monitoring and operations (MIGRATED TO GO!)
		s.setupSystemRoutes(r)

		// Allocation module (MIGRATED TO GO!)
		s.setupAllocationRoutes(r)

		// Portfolio module (MIGRATED TO GO!)
		s.setupPortfolioRoutes(r)

		// Universe module (MIGRATED TO GO!)
		s.setupUniverseRoutes(r)

		// Trading module (MIGRATED TO GO!)
		s.setupTradingRoutes(r)

		// Dividends module (MIGRATED TO GO!)
		s.setupDividendRoutes(r)

		// Display module (MIGRATED TO GO!)
		s.setupDisplayRoutes(r)

		// Scoring module (MIGRATED TO GO!)
		s.setupScoringRoutes(r)

		// Optimization module (MIGRATED TO GO!)
		s.setupOptimizationRoutes(r)

		// Cash-flows module (MIGRATED TO GO!)
		s.setupCashFlowsRoutes(r)

		// Satellites module (MIGRATED TO GO!)
		s.setupSatellitesRoutes(r)

		// Rebalancing module (MIGRATED TO GO!)
		s.setupRebalancingRoutes(r)

		// Planning module (MIGRATED TO GO!)
		s.setupPlanningRoutes(r)

		// Charts module (MIGRATED TO GO!)
		s.setupChartsRoutes(r)

		// Deployment module (MIGRATED TO GO!)
		s.setupDeploymentRoutes(r)

		// Settings module (MIGRATED TO GO!)
		s.setupSettingsRoutes(r)
	})

	// Evaluation module routes (MIGRATED TO GO!)
	// Mounted directly under /api/v1 for Python client compatibility
	s.setupEvaluationRoutes(s.router)

	// Serve built frontend files (from frontend/dist)
	// First try to serve from frontend/dist (built React app)
	// Fall back to static/ for backwards compatibility during migration
	frontendDir := "./frontend/dist"
	if _, err := os.Stat(frontendDir); err == nil {
		// Serve built frontend assets (Vite outputs to /assets/)
		fileServer := http.FileServer(http.Dir(frontendDir))
		s.router.Handle("/assets/*", http.StripPrefix("/assets/", fileServer))

		// Serve index.html for root and all non-API routes (SPA routing)
		s.router.Get("/", s.handleDashboard)
		s.router.NotFound(func(w http.ResponseWriter, r *http.Request) {
			if !strings.HasPrefix(r.URL.Path, "/api") && !strings.HasPrefix(r.URL.Path, "/health") {
				http.ServeFile(w, r, filepath.Join(frontendDir, "index.html"))
			} else {
				http.NotFound(w, r)
			}
		})
	} else {
		// Fallback to old static directory during migration
		s.router.Get("/", s.handleDashboard)
		fileServer := http.FileServer(http.Dir("./static"))
		s.router.Handle("/static/*", http.StripPrefix("/static/", fileServer))
	}
}

// setupSystemRoutes configures system monitoring and operations routes
func (s *Server) setupSystemRoutes(r chi.Router) {
	// Use server's system handlers instance
	systemHandlers := s.systemHandlers

	// Initialize log handlers
	dataDir := filepath.Dir(s.cfg.DatabasePath)
	logHandlers := NewLogHandlers(s.log, dataDir)

	// Initialize universe handlers for sync operations
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	scoreRepo := universe.NewScoreRepository(s.portfolioDB.Conn(), s.log)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	yahooClient := yahoo.NewClient(s.log)
	securityScorer := scorers.NewSecurityScorer()
	historyDB := universe.NewHistoryDB(s.cfg.HistoryPath, s.log)

	// Tradernet client for symbol resolution and data fetching
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Create SecuritySetupService for adding securities (system routes)
	symbolResolver1 := universe.NewSymbolResolver(tradernetClient, securityRepo, s.log)
	historicalSync1 := universe.NewHistoricalSyncService(yahooClient, securityRepo, historyDB, 2*time.Second, s.log)
	eventManager1 := events.NewManager(s.log)

	setupService1 := universe.NewSecuritySetupService(
		symbolResolver1,
		securityRepo,
		tradernetClient,
		yahooClient,
		historicalSync1,
		eventManager1,
		nil, // Will be set after handlers are created
		s.log,
	)

	// Create SyncService for bulk sync operations
	syncService1 := universe.NewSyncService(
		securityRepo,
		historicalSync1,
		yahooClient,
		nil,                  // scoreCalculator - Will be set after handlers are created
		tradernetClient,      // For RebuildUniverseFromPortfolio
		setupService1,        // For adding missing securities
		s.portfolioDB.Conn(), // For SyncAllPrices position updates
		s.log,
	)

	universeHandlers := universe.NewUniverseHandlers(
		securityRepo,
		scoreRepo,
		s.portfolioDB.Conn(),
		positionRepo,
		securityScorer,
		yahooClient,
		historyDB,
		setupService1,
		syncService1,
		s.cfg.PythonServiceURL,
		s.log,
	)

	// Wire score calculator
	setupService1.SetScoreCalculator(universeHandlers)
	syncService1.SetScoreCalculator(universeHandlers)

	// System routes (complete Phase 1 implementation)
	r.Route("/system", func(r chi.Router) {
		// Status and monitoring
		r.Get("/status", systemHandlers.HandleSystemStatus)
		r.Get("/led/display", systemHandlers.HandleLEDDisplay)
		r.Get("/tradernet", systemHandlers.HandleTradernetStatus)
		r.Get("/jobs", systemHandlers.HandleJobsStatus)
		r.Get("/markets", systemHandlers.HandleMarketsStatus)
		r.Get("/database/stats", systemHandlers.HandleDatabaseStats)
		r.Get("/disk", systemHandlers.HandleDiskUsage)

		// Log access
		r.Get("/logs/list", logHandlers.HandleListLogs)
		r.Get("/logs", logHandlers.HandleGetLogs)
		r.Get("/logs/errors", logHandlers.HandleGetErrors)

		// Sync operation triggers
		r.Route("/sync", func(r chi.Router) {
			r.Post("/prices", universeHandlers.HandleSyncPrices)
			r.Post("/historical", universeHandlers.HandleSyncHistorical)
			r.Post("/rebuild-universe", universeHandlers.HandleRebuildUniverse)
			r.Post("/securities-data", universeHandlers.HandleSyncSecuritiesData)
			r.Post("/portfolio", systemHandlers.HandleSyncPortfolio)
			r.Post("/daily-pipeline", systemHandlers.HandleSyncDailyPipeline)
			r.Post("/recommendations", systemHandlers.HandleSyncRecommendations)
		})

		// Job triggers (manual operation triggers)
		r.Route("/jobs", func(r chi.Router) {
			r.Post("/health-check", systemHandlers.HandleTriggerHealthCheck)
			r.Post("/sync-cycle", systemHandlers.HandleTriggerSyncCycle)
			r.Post("/dividend-reinvestment", systemHandlers.HandleTriggerDividendReinvestment)
			r.Post("/satellite-maintenance", systemHandlers.HandleTriggerSatelliteMaintenance)
			r.Post("/satellite-reconciliation", systemHandlers.HandleTriggerSatelliteReconciliation)
			r.Post("/satellite-evaluation", systemHandlers.HandleTriggerSatelliteEvaluation)
			r.Post("/planner-batch", systemHandlers.HandleTriggerPlannerBatch)
			r.Post("/event-based-trading", systemHandlers.HandleTriggerEventBasedTrading)
		})
	})
}

// setupAllocationRoutes configures allocation module routes
func (s *Server) setupAllocationRoutes(r chi.Router) {
	// Initialize allocation module components
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	groupingRepo := allocation.NewGroupingRepository(s.universeDB.Conn(), s.log)
	alertService := allocation.NewConcentrationAlertService(s.portfolioDB.Conn(), s.log)

	// Portfolio service (needed for allocation calculations)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	portfolioRepo := portfolio.NewPortfolioRepository(s.portfolioDB.Conn(), s.log)
	turnoverTracker := portfolio.NewTurnoverTracker(s.ledgerDB.Conn(), s.portfolioDB.Conn(), s.log)
	tradeRepo := portfolio.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	attributionCalc := portfolio.NewAttributionCalculator(tradeRepo, s.configDB.Conn(), s.cfg.HistoryPath, s.log)
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Cash manager (needed for portfolio service)
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	bucketRepo := satellites.NewBucketRepository(s.satellitesDB.Conn(), s.log)
	cashManager := cash_flows.NewCashSecurityManager(securityRepo, positionRepo, bucketRepo, s.universeDB.Conn(), s.portfolioDB.Conn(), s.log)

	portfolioService := portfolio.NewPortfolioService(
		portfolioRepo,
		positionRepo,
		allocRepo,
		turnoverTracker,
		attributionCalc,
		cashManager,
		s.universeDB.Conn(),
		tradernetClient,
		currencyExchangeService,
		s.log,
	)

	// Create adapter to break circular dependency: allocation → portfolio
	portfolioSummaryAdapter := portfolio.NewPortfolioSummaryAdapter(portfolioService)

	handler := allocation.NewHandler(allocRepo, groupingRepo, alertService, portfolioSummaryAdapter, s.log, s.cfg.PythonServiceURL)

	// Allocation routes (faithful translation of Python routes)
	r.Route("/allocation", func(r chi.Router) {
		r.Get("/targets", handler.HandleGetTargets)
		r.Get("/current", handler.HandleGetCurrentAllocation)
		r.Get("/deviations", handler.HandleGetDeviations)

		// Group management
		r.Get("/groups/country", handler.HandleGetCountryGroups)
		r.Get("/groups/industry", handler.HandleGetIndustryGroups)
		r.Put("/groups/country", handler.HandleUpdateCountryGroup)
		r.Put("/groups/industry", handler.HandleUpdateIndustryGroup)
		r.Delete("/groups/country/{group_name}", handler.HandleDeleteCountryGroup)
		r.Delete("/groups/industry/{group_name}", handler.HandleDeleteIndustryGroup)

		// Available options
		r.Get("/groups/available/countries", handler.HandleGetAvailableCountries)
		r.Get("/groups/available/industries", handler.HandleGetAvailableIndustries)

		// Group allocation and targets
		r.Get("/groups/allocation", handler.HandleGetGroupAllocation)
		r.Put("/groups/targets/country", handler.HandleUpdateCountryGroupTargets)
		r.Put("/groups/targets/industry", handler.HandleUpdateIndustryGroupTargets)
	})
}

// setupPortfolioRoutes configures portfolio module routes
func (s *Server) setupPortfolioRoutes(r chi.Router) {
	// Initialize portfolio module components
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	portfolioRepo := portfolio.NewPortfolioRepository(s.portfolioDB.Conn(), s.log)
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	turnoverTracker := portfolio.NewTurnoverTracker(s.ledgerDB.Conn(), s.portfolioDB.Conn(), s.log)
	tradeRepo := portfolio.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	attributionCalc := portfolio.NewAttributionCalculator(tradeRepo, s.configDB.Conn(), s.cfg.HistoryPath, s.log)

	// Tradernet microservice client
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Cash manager (needed for portfolio service)
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	bucketRepo := satellites.NewBucketRepository(s.satellitesDB.Conn(), s.log)
	cashManager := cash_flows.NewCashSecurityManager(securityRepo, positionRepo, bucketRepo, s.universeDB.Conn(), s.portfolioDB.Conn(), s.log)

	portfolioService := portfolio.NewPortfolioService(
		portfolioRepo,
		positionRepo,
		allocRepo,
		turnoverTracker,
		attributionCalc,
		cashManager,
		s.universeDB.Conn(),
		tradernetClient,
		currencyExchangeService,
		s.log,
	)

	handler := portfolio.NewHandler(
		positionRepo,
		portfolioRepo,
		portfolioService,
		tradernetClient,
		currencyExchangeService,
		s.log,
		s.cfg.PythonServiceURL,
	)

	// Portfolio routes (faithful translation of Python routes)
	r.Route("/portfolio", func(r chi.Router) {
		r.Get("/", handler.HandleGetPortfolio)                   // List positions (same as GET /portfolio)
		r.Get("/summary", handler.HandleGetSummary)              // Portfolio summary
		r.Get("/history", handler.HandleGetHistory)              // Historical snapshots
		r.Get("/transactions", handler.HandleGetTransactions)    // Transaction history (via Tradernet microservice)
		r.Get("/cash-breakdown", handler.HandleGetCashBreakdown) // Cash breakdown (via Tradernet microservice)
		r.Get("/analytics", handler.HandleGetAnalytics)          // Proxy to Python (analytics - requires PyFolio)
	})
}

// setupUniverseRoutes configures universe/securities module routes
func (s *Server) setupUniverseRoutes(r chi.Router) {
	// Initialize universe module components
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	scoreRepo := universe.NewScoreRepository(s.portfolioDB.Conn(), s.log)
	// Position repo for joining position data (optional for now)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)

	// Yahoo Finance client for fundamental data
	yahooClient := yahoo.NewClient(s.log)

	// Security scorer for score calculation
	securityScorer := scorers.NewSecurityScorer()

	// History database for historical price data
	historyDB := universe.NewHistoryDB(s.cfg.HistoryPath, s.log)

	// Tradernet client for symbol resolution and data fetching
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Create SecuritySetupService for adding securities
	symbolResolver := universe.NewSymbolResolver(tradernetClient, securityRepo, s.log)
	historicalSync := universe.NewHistoricalSyncService(yahooClient, securityRepo, historyDB, 2*time.Second, s.log)
	eventManager := events.NewManager(s.log)

	// Create score calculator adapter (UniverseHandlers implements ScoreCalculator)
	var scoreCalculator universe.ScoreCalculator

	setupService := universe.NewSecuritySetupService(
		symbolResolver,
		securityRepo,
		tradernetClient,
		yahooClient,
		historicalSync,
		eventManager,
		scoreCalculator, // Will be set after handlers are created
		s.log,
	)

	// Create SyncService for bulk sync operations
	syncService := universe.NewSyncService(
		securityRepo,
		historicalSync,
		yahooClient,
		scoreCalculator,      // Will be set after handlers are created
		tradernetClient,      // For RebuildUniverseFromPortfolio
		setupService,         // For adding missing securities
		s.portfolioDB.Conn(), // For SyncAllPrices position updates
		s.log,
	)

	handler := universe.NewUniverseHandlers(
		securityRepo,
		scoreRepo,
		s.portfolioDB.Conn(), // Pass portfolioDB for GetWithScores
		positionRepo,
		securityScorer,
		yahooClient,
		historyDB,
		setupService,
		syncService,
		s.cfg.PythonServiceURL,
		s.log,
	)

	// Now wire the score calculator (handler implements the interface)
	setupService.SetScoreCalculator(handler)
	syncService.SetScoreCalculator(handler)

	// Universe/Securities routes (faithful translation of Python routes)
	r.Route("/securities", func(r chi.Router) {
		// GET endpoints (implemented in Go)
		r.Get("/", handler.HandleGetStocks)      // List all securities with scores
		r.Get("/{isin}", handler.HandleGetStock) // Get security detail by ISIN

		// POST endpoints (proxied to Python for complex operations)
		r.Post("/", handler.HandleCreateStock)                           // Create security (requires Yahoo Finance)
		r.Post("/add-by-identifier", handler.HandleAddStockByIdentifier) // Auto-setup by symbol/ISIN
		r.Post("/refresh-all", handler.HandleRefreshAllScores)           // Recalculate all scores

		// Security-specific POST endpoints
		r.Post("/{isin}/refresh-data", handler.HandleRefreshSecurityData) // Full data refresh
		r.Post("/{isin}/refresh", handler.HandleRefreshStockScore)        // Quick score refresh

		// PUT/DELETE endpoints
		r.Put("/{isin}", handler.HandleUpdateStock)    // Update security (requires score recalc)
		r.Delete("/{isin}", handler.HandleDeleteStock) // Soft delete (implemented in Go)
	})
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

// setupTradingRoutes configures trading module routes
func (s *Server) setupTradingRoutes(r chi.Router) {
	// Initialize trading module components
	tradeRepo := trading.NewTradeRepository(s.ledgerDB.Conn(), s.log)

	// Security repo for enriching trade data with security names
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	securityFetcher := &securityFetcherAdapter{repo: securityRepo}

	// Portfolio service (needed for allocation endpoint)
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	portfolioRepo := portfolio.NewPortfolioRepository(s.portfolioDB.Conn(), s.log)
	turnoverTracker := portfolio.NewTurnoverTracker(s.ledgerDB.Conn(), s.portfolioDB.Conn(), s.log)
	portfolioTradeRepo := portfolio.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	attributionCalc := portfolio.NewAttributionCalculator(portfolioTradeRepo, s.configDB.Conn(), s.cfg.HistoryPath, s.log)

	// Tradernet microservice client
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Cash manager (needed for portfolio service)
	securityRepoForCash := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	bucketRepoForCash := satellites.NewBucketRepository(s.satellitesDB.Conn(), s.log)
	cashManager := cash_flows.NewCashSecurityManager(securityRepoForCash, positionRepo, bucketRepoForCash, s.universeDB.Conn(), s.portfolioDB.Conn(), s.log)

	portfolioService := portfolio.NewPortfolioService(
		portfolioRepo,
		positionRepo,
		allocRepo,
		turnoverTracker,
		attributionCalc,
		cashManager,
		s.universeDB.Conn(),
		tradernetClient,
		currencyExchangeService,
		s.log,
	)

	// Concentration alert service (needed for allocation endpoint)
	alertService := allocation.NewConcentrationAlertService(s.portfolioDB.Conn(), s.log)

	// Settings service (needed for trade safety validation)
	settingsRepo := settings.NewRepository(s.configDB.Conn(), s.log)
	settingsService := settings.NewService(settingsRepo, s.log)

	// Market hours service (needed for trade safety validation)
	marketHoursService := scheduler.NewMarketHoursService(s.log)

	// Trade safety service (validates all manual trades)
	safetyService := trading.NewTradeSafetyService(
		tradeRepo,
		positionRepo,
		securityRepo,
		settingsService,
		marketHoursService,
		s.log,
	)

	// alertService implements allocation.ConcentrationAlertProvider interface
	handler := trading.NewTradingHandlers(
		tradeRepo,
		securityFetcher,
		portfolioService,
		alertService, // ConcentrationAlertService implements ConcentrationAlertProvider
		tradernetClient,
		safetyService,
		settingsService,
		s.log,
	)

	// Trading routes (faithful translation of Python routes)
	r.Route("/trades", func(r chi.Router) {
		r.Get("/", handler.HandleGetTrades)               // Trade history
		r.Post("/execute", handler.HandleExecuteTrade)    // Execute trade (via Tradernet microservice)
		r.Get("/allocation", handler.HandleGetAllocation) // Portfolio allocation

		// TODO: Recommendations subroute will be added after planning module is properly configured
		// r.Route("/recommendations", func(r chi.Router) {
		// 	r.Post("/", recommendationsHandler.ServeHTTP)
		// 	r.Get("/", ...)  // Fetch existing recommendations
		// 	r.Post("/execute", ...) // Execute recommendation
		// 	r.Get("/stream", ...) // SSE streaming
		// })
	})
}

// setupDividendRoutes configures dividend module routes
func (s *Server) setupDividendRoutes(r chi.Router) {
	// Initialize dividend module components
	dividendRepo := dividends.NewDividendRepository(s.ledgerDB.Conn(), s.log)
	handler := dividends.NewDividendHandlers(dividendRepo, s.log)

	// Dividend routes (faithful translation of Python repository to HTTP API)
	r.Route("/dividends", func(r chi.Router) {
		// List endpoints
		r.Get("/", handler.HandleGetDividends)                        // List all dividends
		r.Get("/{id}", handler.HandleGetDividendByID)                 // Get dividend by ID
		r.Get("/symbol/{symbol}", handler.HandleGetDividendsBySymbol) // Get dividends by symbol

		// CRITICAL: Endpoints used by dividend_reinvestment.py job
		r.Get("/unreinvested", handler.HandleGetUnreinvestedDividends) // Get unreinvested dividends
		r.Post("/{id}/pending-bonus", handler.HandleSetPendingBonus)   // Set pending bonus
		r.Post("/{id}/mark-reinvested", handler.HandleMarkReinvested)  // Mark as reinvested

		// Management endpoints
		r.Post("/", handler.HandleCreateDividend)                  // Create dividend
		r.Post("/clear-bonus/{symbol}", handler.HandleClearBonus)  // Clear bonus by symbol
		r.Get("/pending-bonuses", handler.HandleGetPendingBonuses) // Get all pending bonuses

		// Analytics endpoints
		r.Get("/analytics/total", handler.HandleGetTotalDividendsBySymbol)       // Total dividends by symbol
		r.Get("/analytics/reinvestment-rate", handler.HandleGetReinvestmentRate) // Overall reinvestment rate
	})
}

// setupDisplayRoutes configures display module routes
func (s *Server) setupDisplayRoutes(r chi.Router) {
	// Initialize display module components
	stateManager := display.NewStateManager(s.log)
	handler := display.NewHandlers(stateManager, s.log)

	// Display routes (faithful translation of Python display service)
	r.Route("/display", func(r chi.Router) {
		r.Get("/state", handler.HandleGetState) // Get current display state
		r.Post("/text", handler.HandleSetText)  // Set display text
		r.Post("/led3", handler.HandleSetLED3)  // Set LED3 color
		r.Post("/led4", handler.HandleSetLED4)  // Set LED4 color
	})
}

// setupScoringRoutes configures scoring module routes
func (s *Server) setupScoringRoutes(r chi.Router) {
	// Initialize scoring module components
	handler := api.NewHandlers(s.log)

	// Scoring routes
	r.Route("/scoring", func(r chi.Router) {
		r.Post("/score", handler.HandleScoreSecurity) // Calculate security score
	})
}

// setupOptimizationRoutes configures optimization module routes
func (s *Server) setupOptimizationRoutes(r chi.Router) {
	// Initialize shared clients
	yahooClient := yahoo.NewClient(s.log)
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)
	dividendRepo := dividends.NewDividendRepository(s.ledgerDB.Conn(), s.log)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Initialize PyPFOpt client
	pypfoptClient := optimization.NewPyPFOptClient(s.cfg.PyPFOptServiceURL, s.log)

	// Initialize constraints manager
	constraintsMgr := optimization.NewConstraintsManager(s.log)

	// Initialize returns calculator with Yahoo client for market indicators
	returnsCalc := optimization.NewReturnsCalculator(s.configDB.Conn(), yahooClient, s.log)

	// Initialize risk model builder
	riskBuilder := optimization.NewRiskModelBuilder(s.configDB.Conn(), pypfoptClient, s.log)

	// Initialize optimization service
	optimizerService := optimization.NewOptimizerService(
		pypfoptClient,
		constraintsMgr,
		returnsCalc,
		riskBuilder,
		s.log,
	)

	// Initialize handler with currency exchange service
	handler := optimization.NewHandler(
		optimizerService,
		s.configDB.Conn(),
		yahooClient,
		tradernetClient,
		currencyExchangeService,
		dividendRepo,
		s.log,
	)

	// Optimization routes (faithful translation of Python routes)
	r.Route("/optimizer", func(r chi.Router) {
		r.Get("/", handler.HandleGetStatus) // Get optimizer status and last run
		r.Post("/run", handler.HandleRun)   // Run optimization
	})
}

// setupCashFlowsRoutes configures cash-flows module routes
func (s *Server) setupCashFlowsRoutes(r chi.Router) {
	// Initialize cash flows repository
	repo := cash_flows.NewRepository(s.ledgerDB.Conn(), s.log)

	// Initialize schema
	if err := cash_flows.InitSchema(s.ledgerDB.Conn()); err != nil {
		s.log.Error().Err(err).Msg("Failed to initialize cash_flows schema")
	}

	// Initialize Tradernet client and adapter
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)
	tradernetAdapter := cash_flows.NewTradernetAdapter(tradernetClient)

	// Initialize deposit processor (BalanceService integration will be added when satellites module is migrated)
	// For now, using nil BalanceService - deposits won't be allocated but won't fail either
	depositProcessor := cash_flows.NewDepositProcessor(nil, s.log)

	// Note: DividendCreator and sync job will be set up separately when scheduling background jobs
	// For now, the API endpoints are fully functional

	// Initialize handler
	handler := cash_flows.NewHandler(repo, depositProcessor, tradernetAdapter, s.log)

	// Cash-flows routes (faithful translation of Python routes)
	r.Route("/cash-flows", func(r chi.Router) {
		r.Get("/", handler.HandleGetCashFlows)      // GET / - list cash flows with filters
		r.Get("/sync", handler.HandleSyncCashFlows) // GET /sync - sync from Tradernet
		r.Get("/summary", handler.HandleGetSummary) // GET /summary - aggregate statistics
	})
}

// setupEvaluationRoutes configures evaluation module routes
func (s *Server) setupEvaluationRoutes(r chi.Router) {
	// Initialize evaluation service
	numWorkers := runtime.NumCPU()
	if numWorkers < 2 {
		numWorkers = 2
	}

	evalService := evaluation.NewService(numWorkers, s.log)
	handler := evaluation.NewHandler(evalService, s.log)

	// Mount routes under /api/v1 for Python client compatibility
	r.Route("/api/v1", func(r chi.Router) {
		// Increase timeout for heavy evaluation operations
		r.Use(middleware.Timeout(120 * time.Second))

		r.Route("/evaluate", func(r chi.Router) {
			r.Post("/batch", handler.HandleEvaluateBatch)
			r.Post("/monte-carlo", handler.HandleMonteCarlo)
			r.Post("/stochastic", handler.HandleStochastic)
		})

		r.Route("/simulate", func(r chi.Router) {
			r.Post("/batch", handler.HandleSimulateBatch)
		})
	})
}

// setupSatellitesRoutes configures satellites module routes
func (s *Server) setupSatellitesRoutes(r chi.Router) {
	// Initialize satellites database schema
	if err := satellites.InitSchema(s.satellitesDB.Conn()); err != nil {
		s.log.Fatal().Err(err).Msg("Failed to initialize satellites schema")
	}

	// Initialize Tradernet client for exchange rates
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Initialize currency exchange service for multi-currency cash conversion
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Initialize repositories
	bucketRepo := satellites.NewBucketRepository(s.satellitesDB.Conn(), s.log)
	balanceRepo := satellites.NewBalanceRepository(s.satellitesDB.Conn(), s.log)

	// Cash manager (needed for balance service)
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	cashManager := cash_flows.NewCashSecurityManager(securityRepo, positionRepo, bucketRepo, s.universeDB.Conn(), s.portfolioDB.Conn(), s.log)

	// Initialize services
	bucketService := satellites.NewBucketService(bucketRepo, balanceRepo, currencyExchangeService, s.log)
	balanceService := satellites.NewBalanceService(cashManager, balanceRepo, bucketRepo, s.log)
	reconciliationService := satellites.NewReconciliationService(balanceRepo, bucketRepo, s.log)

	// Initialize handlers
	handlers := satellites.NewHandlers(
		bucketService,
		balanceService,
		reconciliationService,
		s.log,
	)

	// Register routes
	handlers.RegisterRoutes(r)
}

// setupRebalancingRoutes configures rebalancing module routes
func (s *Server) setupRebalancingRoutes(r chi.Router) {
	// Initialize Tradernet client
	tradernetClient := tradernet.NewClient(s.cfg.TradernetServiceURL, s.log)
	tradernetClient.SetCredentials(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret)

	// Initialize portfolio service (needed for rebalancing)
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	portfolioRepo := portfolio.NewPortfolioRepository(s.portfolioDB.Conn(), s.log)
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	turnoverTracker := portfolio.NewTurnoverTracker(s.ledgerDB.Conn(), s.portfolioDB.Conn(), s.log)
	tradeRepo := portfolio.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	attributionCalc := portfolio.NewAttributionCalculator(tradeRepo, s.configDB.Conn(), s.cfg.HistoryPath, s.log)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Cash manager (needed for portfolio service)
	securityRepoForRebalancing := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	bucketRepoForRebalancing := satellites.NewBucketRepository(s.satellitesDB.Conn(), s.log)
	cashManagerForRebalancing := cash_flows.NewCashSecurityManager(securityRepoForRebalancing, positionRepo, bucketRepoForRebalancing, s.universeDB.Conn(), s.portfolioDB.Conn(), s.log)

	portfolioService := portfolio.NewPortfolioService(
		portfolioRepo,
		positionRepo,
		allocRepo,
		turnoverTracker,
		attributionCalc,
		cashManagerForRebalancing,
		s.universeDB.Conn(),
		tradernetClient,
		currencyExchangeService,
		s.log,
	)

	// Initialize rebalancing components
	triggerChecker := rebalancing.NewTriggerChecker(s.log)

	// Initialize repositories for negative balance rebalancer
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)
	settingsRepo := settings.NewRepository(s.configDB.Conn(), s.log)

	// Initialize balance service for cash validation (reuse cashManagerForRebalancing created above)
	balanceRepo := satellites.NewBalanceRepository(s.satellitesDB.Conn(), s.log)
	balanceService := satellites.NewBalanceService(cashManagerForRebalancing, balanceRepo, bucketRepoForRebalancing, s.log)

	tradingRepo := trading.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	tradeExecutionService := services.NewTradeExecutionService(
		tradernetClient,
		tradingRepo,
		positionRepo,
		balanceService,
		currencyExchangeService,
		s.log,
	)
	recommendationRepo := planning.NewRecommendationRepository(s.cacheDB.Conn(), s.log)

	// Initialize market hours service for market open/close checking
	marketHoursService := scheduler.NewMarketHoursService(s.log)

	negativeRebalancer := rebalancing.NewNegativeBalanceRebalancer(
		s.log,
		tradernetClient,
		securityRepo,
		positionRepo,
		settingsRepo,
		currencyExchangeService,
		tradeExecutionService,
		recommendationRepo,
		marketHoursService,
	)

	// Initialize planning service dependencies for rebalancing
	planningOpportunitiesService := opportunities.NewService(s.log)

	// Initialize risk builder for sequences service
	pypfoptClient := optimization.NewPyPFOptClient(s.cfg.PyPFOptServiceURL, s.log)
	riskBuilder := optimization.NewRiskModelBuilder(s.historyDB.Conn(), pypfoptClient, s.log)

	planningSequencesService := sequences.NewService(s.log, riskBuilder)
	planningEvaluationService := planningevaluation.NewService(4, s.log) // 4 workers

	planningService := planning.NewService(
		planningOpportunitiesService,
		planningSequencesService,
		planningEvaluationService,
		s.log,
	)

	// Initialize planner config loader and repository
	planningConfigLoader := planningconfig.NewLoader(s.log)
	plannerConfigRepo := planningrepo.NewConfigRepository(s.agentsDB, planningConfigLoader, s.log)

	// Initialize rebalancing service with full planning integration
	rebalancingService := rebalancing.NewService(
		triggerChecker,
		negativeRebalancer,
		planningService,
		positionRepo,
		securityRepo,
		allocRepo,
		tradernetClient,
		plannerConfigRepo,
		recommendationRepo,
		s.log,
	)

	// Initialize handlers with currency exchange service and allocation repository
	handlers := rebalancing.NewHandlers(
		rebalancingService,
		portfolioService,
		tradernetClient,
		currencyExchangeService,
		allocRepo,
		s.log,
	)

	// Register routes
	handlers.RegisterRoutes(r)
}

// setupDeploymentRoutes configures deployment module routes
func (s *Server) setupDeploymentRoutes(r chi.Router) {
	if s.deploymentHandlers != nil {
		s.deploymentHandlers.RegisterRoutes(r)
	}
}

// Start starts the HTTP server
func (s *Server) Start() error {
	s.log.Info().Int("port", s.cfg.Port).Msg("Starting HTTP server")
	return s.server.ListenAndServe()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown(ctx context.Context) error {
	s.log.Info().Msg("Shutting down HTTP server")
	return s.server.Shutdown(ctx)
}

// handleDashboard serves the main dashboard HTML
func (s *Server) handleDashboard(w http.ResponseWriter, r *http.Request) {
	// Try to serve from frontend/dist first (built React app)
	frontendIndex := "./frontend/dist/index.html"
	if _, err := os.Stat(frontendIndex); err == nil {
		http.ServeFile(w, r, frontendIndex)
		return
	}
	// Fallback to old static directory during migration
	http.ServeFile(w, r, "./static/index.html")
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
