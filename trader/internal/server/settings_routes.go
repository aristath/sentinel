package server

import (
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/events"
	"github.com/aristath/arduino-trader/internal/modules/allocation"
	"github.com/aristath/arduino-trader/internal/modules/cash_flows"
	"github.com/aristath/arduino-trader/internal/modules/market_hours"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/scoring/scorers"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/go-chi/chi/v5"
)

// setupSettingsRoutes configures settings module routes
func (s *Server) setupSettingsRoutes(r chi.Router) {
	// Initialize settings repository
	settingsRepo := settings.NewRepository(s.configDB.Conn(), s.log)

	// Initialize settings service
	settingsService := settings.NewService(settingsRepo, s.log)

	// Initialize Tradernet SDK client for onboarding
	tradernetClient := tradernet.NewClient(s.cfg.TradernetAPIKey, s.cfg.TradernetAPISecret, s.log)

	// Initialize currency exchange service for multi-currency cash handling
	currencyExchangeService := services.NewCurrencyExchangeService(tradernetClient, s.log)

	// Initialize portfolio service for onboarding
	positionRepo := portfolio.NewPositionRepository(s.portfolioDB.Conn(), s.universeDB.Conn(), s.log)
	allocRepo := allocation.NewRepository(s.configDB.Conn(), s.log)

	// Security repository (needed for universe services)
	securityRepo := universe.NewSecurityRepository(s.universeDB.Conn(), s.log)

	// Cash manager (needed for portfolio service)
	cashRepo := cash_flows.NewCashRepository(s.portfolioDB.Conn(), s.log)
	cashManager := cash_flows.NewCashManagerWithDualWrite(cashRepo, positionRepo, s.log)

	portfolioService := portfolio.NewPortfolioService(
		positionRepo,
		allocRepo,
		cashManager,
		s.universeDB.Conn(),
		tradernetClient,
		currencyExchangeService,
		s.log,
	)

	// Initialize universe sync service for onboarding
	scoreRepo := universe.NewScoreRepository(s.portfolioDB.Conn(), s.log)
	yahooClient := yahoo.NewNativeClient(s.log)
	historyDB := universe.NewHistoryDB(s.historyDB.Conn(), s.log)
	symbolResolver := universe.NewSymbolResolver(tradernetClient, securityRepo, s.log)
	historicalSync := universe.NewHistoricalSyncService(yahooClient, securityRepo, historyDB, 2*time.Second, s.log)
	eventManager := events.NewManager(s.log)
	securityScorer := scorers.NewSecurityScorer()

	// Create score calculator adapter (we'll use a simple adapter)
	var scoreCalculator universe.ScoreCalculator

	setupService := universe.NewSecuritySetupService(
		symbolResolver,
		securityRepo,
		tradernetClient,
		yahooClient,
		historicalSync,
		eventManager,
		scoreCalculator, // Will be set after sync service is created
		s.log,
	)

	syncService := universe.NewSyncService(
		securityRepo,
		historicalSync,
		yahooClient,
		scoreCalculator,      // Will be set after handler is created
		tradernetClient,      // For RebuildUniverseFromPortfolio
		setupService,         // For adding missing securities
		s.portfolioDB.Conn(), // For SyncAllPrices position updates
		s.log,
	)

	// Create a simple score calculator that uses UniverseHandlers pattern
	// For onboarding, we'll create a minimal handler just for score calculation
	universeHandler := universe.NewUniverseHandlers(
		securityRepo,
		scoreRepo,
		s.portfolioDB.Conn(),
		positionRepo,
		securityScorer,
		yahooClient,
		historyDB,
		setupService,
		syncService,
		currencyExchangeService,
		s.log,
	)

	// Wire score calculator
	setupService.SetScoreCalculator(universeHandler)
	syncService.SetScoreCalculator(universeHandler)

	// Initialize trading service for onboarding
	tradingRepo := trading.NewTradeRepository(s.ledgerDB.Conn(), s.log)
	settingsServiceForTrading := settings.NewService(settingsRepo, s.log)

	// Create market hours service for trade safety
	marketHoursService := market_hours.NewMarketHoursService()

	tradeSafetyService := trading.NewTradeSafetyService(
		tradingRepo,
		positionRepo,
		securityRepo,
		settingsServiceForTrading,
		marketHoursService,
		s.log,
	)

	tradingService := trading.NewTradingService(
		tradingRepo,
		tradernetClient,
		tradeSafetyService,
		s.log,
	)

	// Create onboarding service
	onboardingService := settings.NewOnboardingService(
		portfolioService,
		syncService,
		tradingService,
		tradernetClient,
		s.log,
	)

	// Initialize settings handler
	settingsHandler := settings.NewHandler(settingsService, s.log)
	settingsHandler.SetOnboardingService(onboardingService)

	// Set credential refresher to refresh system handlers' tradernet client
	if s.systemHandlers != nil {
		settingsHandler.SetCredentialRefresher(s.systemHandlers)
	}

	// Register routes
	// Note: r is already under /api route group, so use /settings not /api/settings
	r.Route("/settings", func(r chi.Router) {
		// GET /api/settings - Get all settings
		r.Get("/", settingsHandler.HandleGetAll)

		// PUT /api/settings/{key} - Update a setting value
		r.Put("/{key}", settingsHandler.HandleUpdate)

		// POST /api/settings/restart-service - Restart the systemd service
		r.Post("/restart-service", settingsHandler.HandleRestartService)

		// POST /api/settings/restart - Trigger system reboot
		r.Post("/restart", settingsHandler.HandleRestart)

		// POST /api/settings/reset-cache - Clear all cached data
		r.Post("/reset-cache", settingsHandler.HandleResetCache)

		// GET /api/settings/cache-stats - Get cache statistics
		r.Get("/cache-stats", settingsHandler.HandleGetCacheStats)

		// POST /api/settings/reschedule-jobs - Reschedule all jobs
		r.Post("/reschedule-jobs", settingsHandler.HandleRescheduleJobs)

		// GET /api/settings/trading-mode - Get current trading mode
		r.Get("/trading-mode", settingsHandler.HandleGetTradingMode)

		// POST /api/settings/trading-mode - Toggle trading mode
		r.Post("/trading-mode", settingsHandler.HandleToggleTradingMode)
	})
}
