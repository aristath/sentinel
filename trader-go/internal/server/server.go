package server

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/config"
	"github.com/aristath/arduino-trader/internal/database"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
)

// Config holds server configuration
type Config struct {
	Port        int
	Log         zerolog.Logger
	ConfigDB    *database.DB // config.db - securities, allocation data
	StateDB     *database.DB // state.db - positions, scores
	SnapshotsDB *database.DB // snapshots.db - portfolio snapshots
	LedgerDB    *database.DB // ledger.db - trades (append-only ledger)
	DividendsDB *database.DB // dividends.db - dividend records with DRIP tracking
	Config      *config.Config
	DevMode     bool
}

// Server represents the HTTP server
type Server struct {
	router      *chi.Mux
	server      *http.Server
	log         zerolog.Logger
	configDB    *database.DB
	stateDB     *database.DB
	snapshotsDB *database.DB
	ledgerDB    *database.DB
	dividendsDB *database.DB
	cfg         *config.Config
}

// New creates a new HTTP server
func New(cfg Config) *Server {
	s := &Server{
		router:      chi.NewRouter(),
		log:         cfg.Log.With().Str("component", "server").Logger(),
		configDB:    cfg.ConfigDB,
		stateDB:     cfg.StateDB,
		snapshotsDB: cfg.SnapshotsDB,
		ledgerDB:    cfg.LedgerDB,
		dividendsDB: cfg.DividendsDB,
		cfg:         cfg.Config,
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
	// Dashboard root route - serve index.html
	s.router.Get("/", s.handleDashboard)

	// Health check
	s.router.Get("/health", s.handleHealth)

	// API routes
	s.router.Route("/api", func(r chi.Router) {
		// System
		r.Route("/system", func(r chi.Router) {
			r.Get("/status", s.handleSystemStatus)
		})

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

		// TODO: Add more routes as modules are migrated
		// r.Route("/planning", func(r chi.Router) { ... })
	})

	// Serve static files (for dashboard)
	fileServer := http.FileServer(http.Dir("./static"))
	s.router.Handle("/static/*", http.StripPrefix("/static/", fileServer))
}

// setupAllocationRoutes configures allocation module routes
func (s *Server) setupAllocationRoutes(r chi.Router) {
	// Initialize allocation module components
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	groupingRepo := allocation.NewGroupingRepository(s.configDB.Conn(), s.log)
	alertService := allocation.NewConcentrationAlertService(s.stateDB.Conn(), s.log)
	handler := allocation.NewHandler(allocRepo, groupingRepo, alertService, s.log, s.cfg.PythonServiceURL)

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
	positionRepo := portfolio.NewPositionRepository(s.stateDB.Conn(), s.configDB.Conn(), s.log)
	portfolioRepo := portfolio.NewPortfolioRepository(s.snapshotsDB.Conn(), s.log)
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)
	portfolioService := portfolio.NewPortfolioService(
		portfolioRepo,
		positionRepo,
		allocRepo,
		s.configDB.Conn(),
		s.log,
	)
	handler := portfolio.NewHandler(
		positionRepo,
		portfolioRepo,
		portfolioService,
		s.log,
		s.cfg.PythonServiceURL,
	)

	// Portfolio routes (faithful translation of Python routes)
	r.Route("/portfolio", func(r chi.Router) {
		r.Get("/", handler.HandleGetPortfolio)                  // List positions (same as GET /portfolio)
		r.Get("/summary", handler.HandleGetSummary)             // Portfolio summary
		r.Get("/history", handler.HandleGetHistory)             // Historical snapshots
		r.Get("/transactions", handler.HandleGetTransactions)   // Proxy to Python (Tradernet)
		r.Get("/cash-breakdown", handler.HandleGetCashBreakdown) // Proxy to Python (Tradernet)
		r.Get("/analytics", handler.HandleGetAnalytics)         // Proxy to Python (analytics)
	})
}

// setupUniverseRoutes configures universe/securities module routes
func (s *Server) setupUniverseRoutes(r chi.Router) {
	// Initialize universe module components
	securityRepo := universe.NewSecurityRepository(s.configDB.Conn(), s.log)
	scoreRepo := universe.NewScoreRepository(s.stateDB.Conn(), s.log)
	// Position repo for joining position data (optional for now)
	positionRepo := portfolio.NewPositionRepository(s.stateDB.Conn(), s.configDB.Conn(), s.log)

	handler := universe.NewUniverseHandlers(
		securityRepo,
		scoreRepo,
		s.stateDB.Conn(), // Pass stateDB for GetWithScores
		positionRepo,
		s.cfg.PythonServiceURL,
		s.log,
	)

	// Universe/Securities routes (faithful translation of Python routes)
	r.Route("/securities", func(r chi.Router) {
		// GET endpoints (implemented in Go)
		r.Get("/", handler.HandleGetStocks)         // List all securities with scores
		r.Get("/{isin}", handler.HandleGetStock)    // Get security detail by ISIN

		// POST endpoints (proxied to Python for complex operations)
		r.Post("/", handler.HandleCreateStock)                       // Create security (requires Yahoo Finance)
		r.Post("/add-by-identifier", handler.HandleAddStockByIdentifier) // Auto-setup by symbol/ISIN
		r.Post("/refresh-all", handler.HandleRefreshAllScores)       // Recalculate all scores

		// Security-specific POST endpoints
		r.Post("/{isin}/refresh-data", handler.HandleRefreshSecurityData) // Full data refresh
		r.Post("/{isin}/refresh", handler.HandleRefreshStockScore)         // Quick score refresh

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
	securityRepo := universe.NewSecurityRepository(s.configDB.Conn(), s.log)
	securityFetcher := &securityFetcherAdapter{repo: securityRepo}

	handler := trading.NewTradingHandlers(
		tradeRepo,
		securityFetcher,
		s.cfg.PythonServiceURL,
		s.log,
	)

	// Trading routes (faithful translation of Python routes)
	r.Route("/trades", func(r chi.Router) {
		r.Get("/", handler.HandleGetTrades)                // Trade history
		r.Post("/execute", handler.HandleExecuteTrade)     // Execute trade (proxy to Python)
		r.Get("/allocation", handler.HandleGetAllocation)  // Portfolio allocation (proxy to Python)
	})
}

// setupDividendRoutes configures dividend module routes
func (s *Server) setupDividendRoutes(r chi.Router) {
	// Initialize dividend module components
	dividendRepo := dividends.NewDividendRepository(s.dividendsDB.Conn(), s.log)
	handler := dividends.NewDividendHandlers(dividendRepo, s.log)

	// Dividend routes (faithful translation of Python repository to HTTP API)
	r.Route("/dividends", func(r chi.Router) {
		// List endpoints
		r.Get("/", handler.HandleGetDividends)                            // List all dividends
		r.Get("/{id}", handler.HandleGetDividendByID)                     // Get dividend by ID
		r.Get("/symbol/{symbol}", handler.HandleGetDividendsBySymbol)     // Get dividends by symbol

		// CRITICAL: Endpoints used by dividend_reinvestment.py job
		r.Get("/unreinvested", handler.HandleGetUnreinvestedDividends)    // Get unreinvested dividends
		r.Post("/{id}/pending-bonus", handler.HandleSetPendingBonus)      // Set pending bonus
		r.Post("/{id}/mark-reinvested", handler.HandleMarkReinvested)     // Mark as reinvested

		// Management endpoints
		r.Post("/", handler.HandleCreateDividend)                         // Create dividend
		r.Post("/clear-bonus/{symbol}", handler.HandleClearBonus)         // Clear bonus by symbol
		r.Get("/pending-bonuses", handler.HandleGetPendingBonuses)        // Get all pending bonuses

		// Analytics endpoints
		r.Get("/analytics/total", handler.HandleGetTotalDividendsBySymbol)       // Total dividends by symbol
		r.Get("/analytics/reinvestment-rate", handler.HandleGetReinvestmentRate) // Overall reinvestment rate
	})
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
