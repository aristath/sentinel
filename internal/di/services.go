// Package di provides dependency injection for service implementations.
package di

import (
	"database/sql"
	"fmt"
	"math"
	"os"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/clients/alphavantage"
	"github.com/aristath/sentinel/internal/clients/exchangerate"
	"github.com/aristath/sentinel/internal/clients/openfigi"
	"github.com/aristath/sentinel/internal/clients/symbols"
	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/analytics"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/order_book"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningconstraints "github.com/aristath/sentinel/internal/modules/planning/constraints"
	planningevaluation "github.com/aristath/sentinel/internal/modules/planning/evaluation"
	planninghash "github.com/aristath/sentinel/internal/modules/planning/hash"
	planningplanner "github.com/aristath/sentinel/internal/modules/planning/planner"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	planningstatemonitor "github.com/aristath/sentinel/internal/modules/planning/state_monitor"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/quantum"
	"github.com/aristath/sentinel/internal/modules/rebalancing"
	"github.com/aristath/sentinel/internal/modules/scoring/scorers"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/trading"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/queue"
	"github.com/aristath/sentinel/internal/reliability"
	"github.com/aristath/sentinel/internal/services"
	"github.com/aristath/sentinel/internal/ticker"
	"github.com/rs/zerolog"
)

// securitySetupServiceAdapter adapts universe.SecuritySetupService to portfolio.SecuritySetupServiceInterface
// This is needed because Go doesn't support return type covariance in interfaces
type securitySetupServiceAdapter struct {
	service *universe.SecuritySetupService
}

// AddSecurityByIdentifier implements portfolio.SecuritySetupServiceInterface
func (a *securitySetupServiceAdapter) AddSecurityByIdentifier(identifier string, minLot int, allowBuy bool, allowSell bool) (interface{}, error) {
	return a.service.AddSecurityByIdentifier(identifier, minLot, allowBuy, allowSell)
}

// InitializeServices creates all services and stores them in the container
// This is the SINGLE SOURCE OF TRUTH for all service creation
// Services are created in dependency order to ensure all dependencies exist
func InitializeServices(container *Container, cfg *config.Config, displayManager *display.StateManager, log zerolog.Logger) error {
	if container == nil {
		return fmt.Errorf("container cannot be nil")
	}

	// ==========================================
	// STEP 1: Initialize Clients
	// ==========================================

	// Broker client (Tradernet adapter)
	container.BrokerClient = tradernet.NewTradernetBrokerAdapter(cfg.TradernetAPIKey, cfg.TradernetAPISecret, log)
	log.Info().Msg("Broker client initialized (Tradernet adapter)")

	// Yahoo Finance client (native Go implementation)
	container.YahooClient = yahoo.NewNativeClient(log)
	log.Info().Msg("Using native Go Yahoo Finance client")

	// ExchangeRate API client (exchangerate-api.com)
	container.ExchangeRateAPIClient = exchangerate.NewClient(container.ClientDataRepo, log)
	log.Info().Msg("ExchangeRateAPI client initialized with persistent cache")

	// OpenFIGI client (ISIN to ticker mapping)
	// Get API key from settings (optional - increases rate limits)
	// Must be initialized before Alpha Vantage client (which depends on it)
	openFIGIKey := ""
	if container.SettingsRepo != nil {
		if key, err := container.SettingsRepo.Get("openfigi_api_key"); err == nil && key != nil {
			openFIGIKey = *key
		}
	}
	container.OpenFIGIClient = openfigi.NewClient(openFIGIKey, container.ClientDataRepo, log)
	if openFIGIKey != "" {
		log.Info().Msg("OpenFIGI client initialized with API key and persistent cache (25k requests/min)")
	} else {
		log.Info().Msg("OpenFIGI client initialized with persistent cache (25 requests/min without key)")
	}

	// Alpha Vantage client (fundamentals, technical indicators, etc.)
	// Get API key from settings or config
	// Depends on OpenFIGIClient and SecurityRepo for symbol-to-ISIN resolution
	avAPIKey := ""
	if container.SettingsRepo != nil {
		if key, err := container.SettingsRepo.Get("alphavantage_api_key"); err == nil && key != nil {
			avAPIKey = *key
		}
	}
	container.AlphaVantageClient = alphavantage.NewClient(
		avAPIKey,
		container.ClientDataRepo,
		container.OpenFIGIClient,
		container.SecurityRepo,
		log,
	)
	if avAPIKey != "" {
		log.Info().Msg("Alpha Vantage client initialized with API key and persistent cache")
	} else {
		log.Info().Msg("Alpha Vantage client initialized with persistent cache (no API key configured)")
	}

	// Symbol mapper for converting symbols between providers
	container.SymbolMapper = symbols.NewMapper()
	log.Info().Msg("Symbol mapper initialized")

	// Client symbol mapper for converting ISINs to client-specific symbols
	// Used for brokers (tradernet, ibkr, schwab) and data providers (yahoo, alphavantage, etc.)
	// Note: ClientSymbolRepo must be initialized in InitializeRepositories first
	if container.ClientSymbolRepo != nil {
		container.ClientSymbolMapper = services.NewClientSymbolMapper(container.ClientSymbolRepo)
		log.Info().Msg("Client symbol mapper initialized")
	}

	// Configure display service (App Lab HTTP API on localhost:7000)
	// displayManager can be nil in tests - skip display configuration if nil
	if displayManager != nil {
		// Get display URL from settings or use default
		displayURL := display.DefaultDisplayURL
		if container.SettingsRepo != nil {
			if url, err := container.SettingsRepo.Get("display_url"); err == nil && url != nil && *url != "" {
				displayURL = *url
			}
		}
		displayManager.SetDisplayURL(displayURL)

		// Check if display should be enabled (default: true on Arduino hardware)
		// Display is enabled if running on Arduino Uno Q (check for arduino-router socket)
		displayEnabled := false
		if _, err := os.Stat("/var/run/arduino-router.sock"); err == nil {
			// Arduino router socket exists - we're on Arduino hardware
			displayEnabled = true
			log.Info().Str("url", displayURL).Msg("Arduino hardware detected, enabling display service")
		} else {
			// Allow manual override via settings
			if container.SettingsRepo != nil {
				if enabled, err := container.SettingsRepo.Get("display_enabled"); err == nil && enabled != nil && *enabled == "true" {
					displayEnabled = true
					log.Info().Str("url", displayURL).Msg("Display service manually enabled via settings")
				}
			}
		}

		if displayEnabled {
			displayManager.Enable()
		} else {
			log.Info().Msg("Display service disabled (not on Arduino hardware)")
		}
	} else {
		log.Debug().Msg("Display manager not provided - skipping display configuration")
	}

	// Data source router for configurable provider priorities
	// Create settings adapter for DataSourceRouter
	settingsAdapter := &dataSourceSettingsAdapter{repo: container.SettingsRepo}
	clientsConfig := &services.DataSourceClients{
		AlphaVantageAPIKey: avAPIKey,
		OpenFIGIAPIKey:     openFIGIKey,
	}
	container.DataSourceRouter = services.NewDataSourceRouter(settingsAdapter, clientsConfig)
	container.DataSourceRouter.SetLogger(log)
	log.Info().Msg("Data source router initialized")

	// Subscribe to SETTINGS_CHANGED events to refresh data source priorities dynamically
	// Note: EventBus is initialized later, so we defer the subscription
	dataSourceRouter := container.DataSourceRouter // Capture for closure

	// Data fetcher service - provides unified data fetching with configurable priorities
	container.DataFetcherService = services.NewDataFetcherService(
		container.DataSourceRouter,
		container.SymbolMapper,
		&brokerClientAdapter{client: container.BrokerClient},
		&yahooClientAdapter{client: container.YahooClient},
		container.AlphaVantageClient,
		log,
	)
	log.Info().Msg("Data fetcher service initialized")

	// ==========================================
	// STEP 2: Initialize Basic Services
	// ==========================================

	// Currency exchange service
	container.CurrencyExchangeService = services.NewCurrencyExchangeService(container.BrokerClient, log)

	// Market hours service
	container.MarketHoursService = market_hours.NewMarketHoursService()

	// Market state detector (for market-aware scheduling)
	container.MarketStateDetector = market_regime.NewMarketStateDetector(
		container.SecurityRepo,
		container.MarketHoursService,
		log,
	)

	// Event system (new bus-based architecture)
	container.EventBus = events.NewBus(log)
	container.EventManager = events.NewManager(container.EventBus, log)

	// Subscribe DataSourceRouter to settings changes for dynamic priority refresh
	container.EventBus.Subscribe(events.SettingsChanged, func(e *events.Event) {
		// Check if this is a data source priority change
		if key, ok := e.Data["key"].(string); ok {
			if strings.HasPrefix(key, "datasource_") {
				log.Debug().Str("key", key).Msg("Refreshing data source priorities due to settings change")
				dataSourceRouter.RefreshPriorities()
			}
		}
	})

	// Market status WebSocket client
	container.MarketStatusWS = tradernet.NewMarketStatusWebSocket(
		"wss://wss.tradernet.com/",
		"", // Empty string for demo mode (SID not required)
		container.EventBus,
		log,
	)

	// Start WebSocket connection (non-blocking, will auto-retry)
	if err := container.MarketStatusWS.Start(); err != nil {
		log.Warn().Err(err).Msg("Market status WebSocket connection failed, will auto-retry")
		// Don't fail startup - reconnect loop will handle it
	}

	// Queue system
	memoryQueue := queue.NewMemoryQueue()
	jobHistory := queue.NewHistory(container.CacheDB.Conn())
	container.QueueManager = queue.NewManager(memoryQueue, jobHistory)
	container.JobHistory = jobHistory
	container.JobRegistry = queue.NewRegistry()
	container.WorkerPool = queue.NewWorkerPool(container.QueueManager, container.JobRegistry, 2)
	container.WorkerPool.SetLogger(log)
	container.TimeScheduler = queue.NewScheduler(container.QueueManager)
	container.TimeScheduler.SetLogger(log)
	// Set market state detector on scheduler for market-aware sync scheduling
	container.TimeScheduler.SetMarketStateDetector(container.MarketStateDetector)

	// Settings service (needed for trade safety and other services)
	container.SettingsService = settings.NewService(container.SettingsRepo, log)

	// Order Book service (validates liquidity and calculates optimal limit prices)
	// Uses bid-ask midpoint pricing strategy for optimal execution
	// PriceValidator abstracts the validation source (Yahoo Finance in this case)
	priceValidator := order_book.NewYahooPriceValidator(
		container.YahooClient,
		log.With().Str("component", "yahoo_price_validator").Logger(),
	)
	container.OrderBookService = order_book.NewService(
		container.BrokerClient,
		priceValidator,
		container.SettingsService,
		log.With().Str("service", "order_book").Logger(),
	)

	// Exchange rate cache service (wraps ExchangeRateAPI + CurrencyExchangeService + Alpha Vantage + Yahoo fallback)
	container.ExchangeRateCacheService = services.NewExchangeRateCacheService(
		container.ExchangeRateAPIClient,   // Primary source (exchangerate-api.com)
		container.CurrencyExchangeService, // Tradernet (secondary)
		container.YahooClient,
		container.HistoryDBClient,
		container.SettingsService,
		log,
	)
	// Wire Alpha Vantage as additional exchange rate fallback
	container.ExchangeRateCacheService.SetAlphaVantageClient(container.AlphaVantageClient)

	// Price conversion service (converts native currency prices to EUR)
	container.PriceConversionService = services.NewPriceConversionService(
		container.CurrencyExchangeService,
		log,
	)

	// ==========================================
	// STEP 3: Initialize Cash Manager
	// ==========================================

	// Cash manager (cash-as-balances architecture)
	// This implements domain.CashManager interface
	cashManager := cash_flows.NewCashManagerWithDualWrite(container.CashRepo, container.PositionRepo, log)
	container.CashManager = cashManager // Store as interface

	// ==========================================
	// STEP 4: Initialize Trading Services
	// ==========================================

	// Trade safety service with all validation layers
	container.TradeSafetyService = trading.NewTradeSafetyService(
		container.TradeRepo,
		container.PositionRepo,
		container.SecurityRepo,
		container.SettingsService,
		container.MarketHoursService,
		log,
	)

	// Trading service
	container.TradingService = trading.NewTradingService(
		container.TradeRepo,
		container.BrokerClient,
		container.TradeSafetyService,
		container.EventManager,
		log,
	)

	// Trade execution service for emergency rebalancing
	container.TradeExecutionService = services.NewTradeExecutionService(
		container.BrokerClient,
		container.TradeRepo,
		container.PositionRepo,
		cashManager, // Use concrete type for now, will be interface later
		container.CurrencyExchangeService,
		container.EventManager,
		container.SettingsService,
		container.PlannerConfigRepo,
		container.OrderBookService,
		container.YahooClient,
		container.HistoryDB.Conn(),
		container.SecurityRepo,
		container.MarketHoursService,  // Market hours validation
		container.DismissedFilterRepo, // Clear dismissed filters after trades
		log,
	)

	// ==========================================
	// STEP 5: Initialize Universe Services
	// ==========================================

	// Historical price validator for validating and interpolating abnormal prices
	historicalPriceValidator := universe.NewPriceValidator(log)

	// Historical sync service (uses Tradernet as primary source for historical data)
	container.HistoricalSyncService = universe.NewHistoricalSyncService(
		container.BrokerClient, // Changed from YahooClient - Tradernet is now single source of truth
		container.SecurityRepo,
		container.HistoryDBClient,
		historicalPriceValidator,
		time.Second*2, // Rate limit delay
		log,
	)

	// Wire DataFetcherService for multi-source historical price fetching
	container.HistoricalSyncService.SetDataFetcher(&historicalDataFetcherAdapter{
		fetcher: container.DataFetcherService,
	})

	// Symbol resolver
	container.SymbolResolver = universe.NewSymbolResolver(
		container.BrokerClient,
		container.SecurityRepo,
		log,
	)

	// Security setup service (scoreCalculator will be set later)
	container.SetupService = universe.NewSecuritySetupService(
		container.SymbolResolver,
		container.SecurityRepo,
		container.BrokerClient,
		container.YahooClient,
		container.HistoricalSyncService,
		container.EventManager,
		nil, // scoreCalculator - will be set later
		log,
	)

	// Wire OpenFIGI client for ISIN lookup fallback
	container.SetupService.SetOpenFIGIClient(container.OpenFIGIClient)

	// Wire DataFetcherService for multi-source metadata fetching
	container.SetupService.SetMetadataFetcher(&metadataFetcherAdapter{
		fetcher: container.DataFetcherService,
	})

	// Create adapter for SecuritySetupService to match portfolio.SecuritySetupServiceInterface
	setupServiceAdapter := &securitySetupServiceAdapter{service: container.SetupService}

	// ==========================================
	// STEP 6: Initialize Portfolio Service
	// ==========================================

	// Portfolio service (with SecuritySetupService adapter for auto-adding missing securities)
	container.PortfolioService = portfolio.NewPortfolioService(
		container.PositionRepo,
		container.AllocRepo,
		cashManager, // Use concrete type
		container.UniverseDB.Conn(),
		container.BrokerClient,
		container.CurrencyExchangeService,
		container.ExchangeRateCacheService,
		container.SettingsService,
		setupServiceAdapter, // Use adapter to match interface
		log,
	)

	// ==========================================
	// STEP 7: Initialize Cash Flows Services
	// ==========================================

	// Dividend service implementation (adapter - uses existing dividendRepo)
	container.DividendService = cash_flows.NewDividendServiceImpl(container.DividendRepo, log)

	// Dividend creator
	container.DividendCreator = cash_flows.NewDividendCreator(container.DividendService, log)

	// Deposit processor (uses CashManager)
	container.DepositProcessor = cash_flows.NewDepositProcessor(cashManager, log)

	// Tradernet adapter (adapts tradernet.Client to cash_flows.TradernetClient)
	tradernetAdapter := cash_flows.NewTradernetAdapter(container.BrokerClient)

	// Cash flows sync job (created but not stored - used by service)
	syncJob := cash_flows.NewSyncJob(
		container.CashFlowsRepo,
		container.DepositProcessor,
		container.DividendCreator,
		tradernetAdapter,
		displayManager,
		container.EventManager,
		log,
	)

	// Cash flows service
	container.CashFlowsService = cash_flows.NewCashFlowsService(syncJob, log)

	// ==========================================
	// STEP 8: Initialize Remaining Universe Services
	// ==========================================

	// Price validator (Tradernet primary, Yahoo sanity check)
	// Create Yahoo price adapter to satisfy PriceValidator's interface
	yahooPriceAdapter := services.NewYahooPriceAdapter(container.YahooClient)
	priceValidatorService := services.NewPriceValidator(yahooPriceAdapter, log)

	// Sync service (scoreCalculator will be set later)
	container.SyncService = universe.NewSyncService(
		container.SecurityRepo,
		container.HistoricalSyncService,
		container.YahooClient,
		priceValidatorService, // PriceValidator for Tradernet-primary price sync
		nil,                   // scoreCalculator - will be set later
		container.BrokerClient,
		container.SetupService,
		container.PortfolioDB.Conn(),
		log,
	)

	// Universe service with cleanup coordination
	container.UniverseService = universe.NewUniverseService(
		container.SecurityRepo,
		container.HistoryDB,
		container.PortfolioDB,
		container.SyncService,
		log,
	)

	// Tag assigner for auto-tagging securities
	container.TagAssigner = universe.NewTagAssigner(log)
	// Wire settings service for temperament-aware tag thresholds
	tagSettingsAdapterInstance := &tagSettingsAdapter{service: container.SettingsService}
	container.TagAssigner.SetSettingsService(tagSettingsAdapterInstance)

	// Security scorer (used by handlers)
	container.SecurityScorer = scorers.NewSecurityScorer()

	// ==========================================
	// STEP 8: Initialize Planning Services
	// ==========================================

	// Opportunities service (with unified calculators - tag-based optimization controlled by config)
	// Create adapter to bridge between universe.SecurityRepository and opportunities.SecurityRepository interface
	securityRepoAdapter := opportunities.NewSecurityRepositoryAdapter(container.SecurityRepo)
	tagFilter := opportunities.NewTagBasedFilter(securityRepoAdapter, log)
	container.OpportunitiesService = opportunities.NewService(tagFilter, securityRepoAdapter, log)

	// Risk builder (needed for sequences service)
	container.RiskBuilder = optimization.NewRiskModelBuilder(container.HistoryDB.Conn(), container.UniverseDB.Conn(), log)

	// Constraint enforcer for sequences service
	// Uses security lookup to check per-security allow_buy/allow_sell constraints
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		if isin != "" {
			sec, err := container.SecurityRepo.GetByISIN(isin)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		if symbol != "" {
			sec, err := container.SecurityRepo.GetBySymbol(symbol)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		return nil, false
	}
	sequencesEnforcer := planningconstraints.NewEnforcer(log, securityLookup)

	// Sequences service
	container.SequencesService = sequences.NewService(log, container.RiskBuilder, sequencesEnforcer)

	// Evaluation service (4 workers)
	container.EvaluationService = planningevaluation.NewService(4, log)
	// Wire settings service for temperament-aware scoring
	container.EvaluationService.SetSettingsService(container.SettingsService)

	// Planner service (core planner)
	container.PlannerService = planningplanner.NewPlanner(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		container.CurrencyExchangeService,
		container.BrokerClient,
		log,
	)

	// Planning service
	container.PlanningService = planning.NewService(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		container.CurrencyExchangeService,
		container.BrokerClient,
		log,
	)

	// State hash service (calculates unified state hash for change detection)
	container.StateHashService = planninghash.NewStateHashService(
		container.PositionRepo,
		container.SecurityRepo,
		container.ScoreRepo,
		container.CashManager,
		container.SettingsRepo,
		container.SettingsService,
		container.AllocRepo,
		container.CurrencyExchangeService,
		container.BrokerClient,
		log,
	)
	log.Info().Msg("State hash service initialized")

	// State monitor (monitors unified state hash and emits events on changes)
	// NOTE: Not started here - will be started in main.go after all services initialized
	container.StateMonitor = planningstatemonitor.NewStateMonitor(
		container.StateHashService,
		container.EventManager,
		log,
	)
	log.Info().Msg("State monitor initialized (not started yet)")

	// Opportunity Context Builder - unified context building for opportunities, planning, and rebalancing
	container.OpportunityContextBuilder = services.NewOpportunityContextBuilder(
		&ocbPositionRepoAdapter{repo: container.PositionRepo},
		&ocbSecurityRepoAdapter{repo: container.SecurityRepo},
		&ocbAllocationRepoAdapter{repo: container.AllocRepo},
		&ocbGroupingRepoAdapter{repo: container.GroupingRepo, allocRepo: container.AllocRepo},
		&ocbTradeRepoAdapter{repo: container.TradeRepo},
		&ocbScoresRepoAdapter{db: container.PortfolioDB.Conn()},
		&ocbSettingsRepoAdapter{repo: container.SettingsRepo, configRepo: container.PlannerConfigRepo},
		&ocbRegimeRepoAdapter{adapter: container.RegimeScoreProvider},
		&ocbCashManagerAdapter{manager: container.CashManager},
		&ocbPriceClientAdapter{client: container.YahooClient},
		container.PriceConversionService,
		&ocbBrokerClientAdapter{client: container.BrokerClient},
		&ocbDismissedFilterRepoAdapter{repo: container.DismissedFilterRepo},
		log,
	)
	log.Info().Msg("Opportunity context builder initialized")

	// ==========================================
	// STEP 9: Initialize Optimization Services
	// ==========================================

	// Constraints manager
	container.ConstraintsMgr = optimization.NewConstraintsManager(log)

	// Returns calculator
	container.ReturnsCalc = optimization.NewReturnsCalculator(
		container.PortfolioDB.Conn(),
		container.UniverseDB.Conn(),
		container.YahooClient,
		log,
	)

	// Kelly Position Sizer
	container.KellySizer = optimization.NewKellyPositionSizer(
		0.02,  // riskFreeRate: 2%
		0.5,   // fixedFractional: 0.5 (half-Kelly) - default, will be overridden by temperament
		0.005, // minPositionSize: 0.5% - default, will be overridden by temperament
		0.20,  // maxPositionSize: 20% - default, will be overridden by temperament
		container.ReturnsCalc,
		container.RiskBuilder,
		container.RegimeDetector,
	)
	// Wire settings service for temperament-aware Kelly parameters
	kellySettingsAdapterInstance := &kellySettingsAdapter{service: container.SettingsService}
	container.KellySizer.SetSettingsService(kellySettingsAdapterInstance)

	// CVaR Calculator
	container.CVaRCalculator = optimization.NewCVaRCalculator(
		container.RiskBuilder,
		container.RegimeDetector,
		log,
	)

	// View Generator (for Black-Litterman)
	container.ViewGenerator = optimization.NewViewGenerator(log)

	// Black-Litterman Optimizer
	container.BlackLittermanOptimizer = optimization.NewBlackLittermanOptimizer(
		container.ViewGenerator,
		container.RiskBuilder,
		log,
	)

	// Optimizer service
	container.OptimizerService = optimization.NewOptimizerService(
		container.ConstraintsMgr,
		container.ReturnsCalc,
		container.RiskBuilder,
		log,
	)

	// Wire Kelly Sizer into OptimizerService
	container.OptimizerService.SetKellySizer(container.KellySizer)

	// Wire CVaR Calculator into OptimizerService
	container.OptimizerService.SetCVaRCalculator(container.CVaRCalculator)

	// Wire Settings Service into OptimizerService (for CVaR threshold configuration)
	container.OptimizerService.SetSettingsService(container.SettingsService)

	// Wire Black-Litterman Optimizer into OptimizerService
	container.OptimizerService.SetBlackLittermanOptimizer(container.BlackLittermanOptimizer)

	// Factor Exposure Tracker
	container.FactorExposureTracker = analytics.NewFactorExposureTracker(log)

	// ==========================================
	// STEP 10: Initialize Rebalancing Services
	// ==========================================

	// Negative balance rebalancer
	container.NegativeBalanceRebalancer = rebalancing.NewNegativeBalanceRebalancer(
		log,
		cashManager,
		container.BrokerClient,
		container.SecurityRepo,
		container.PositionRepo,
		container.SettingsRepo,
		container.CurrencyExchangeService,
		container.TradeExecutionService,
		container.RecommendationRepo,
	)

	// Rebalancing service
	triggerChecker := rebalancing.NewTriggerChecker(log)
	container.RebalancingService = rebalancing.NewService(
		triggerChecker,
		container.NegativeBalanceRebalancer,
		container.PlanningService,
		container.PositionRepo,
		container.SecurityRepo,
		container.AllocRepo,
		cashManager,
		container.BrokerClient,
		container.PlannerConfigRepo,
		container.RecommendationRepo,
		container.OpportunityContextBuilder,
		container.ConfigDB.Conn(),
		log,
	)

	// ==========================================
	// STEP 11: Initialize Ticker Service
	// ==========================================

	// Ticker content service (generates ticker text)
	container.TickerContentService = ticker.NewTickerContentService(
		container.PortfolioDB.Conn(),
		container.ConfigDB.Conn(),
		container.CacheDB.Conn(),
		cashManager,
		log,
	)
	log.Info().Msg("Ticker content service initialized")

	// Health calculator (calculates portfolio health scores)
	container.HealthCalculator = display.NewHealthCalculator(
		container.UniverseDB.Conn(),
		container.PortfolioDB.Conn(),
		container.HistoryDB.Conn(),
		container.ConfigDB.Conn(),
		log,
	)
	log.Info().Msg("Health calculator initialized")

	// Health updater (periodically sends health scores to display)
	displayURL := "http://localhost:7000"
	if envURL := os.Getenv("DISPLAY_URL"); envURL != "" {
		displayURL = envURL
	}
	updateInterval := 30 * time.Minute // Default 30 minutes
	if intervalSetting, err := container.SettingsRepo.Get("display_health_update_interval"); err == nil && intervalSetting != nil {
		// Parse string to float
		var intervalFloat float64
		if _, err := fmt.Sscanf(*intervalSetting, "%f", &intervalFloat); err == nil {
			updateInterval = time.Duration(intervalFloat) * time.Second
		}
	}
	container.HealthUpdater = display.NewHealthUpdater(
		container.HealthCalculator,
		displayURL,
		updateInterval,
		log,
	)
	log.Info().Dur("interval", updateInterval).Msg("Health updater initialized")

	// Mode manager (switches between display modes)
	if displayManager != nil {
		container.ModeManager = display.NewModeManager(
			displayManager,
			container.HealthUpdater,
			container.TickerContentService,
			log,
		)
		log.Info().Msg("Display mode manager initialized")
	}

	// ==========================================
	// STEP 12: Initialize Adaptive Market Services
	// ==========================================

	// Market index service for market-wide regime detection
	container.MarketIndexService = market_regime.NewMarketIndexService(
		container.UniverseDB.Conn(),
		container.HistoryDB.Conn(),
		container.BrokerClient,
		log,
	)

	// Regime persistence for smoothing and history
	container.RegimePersistence = market_regime.NewRegimePersistence(container.ConfigDB.Conn(), log)

	// Market regime detector
	container.RegimeDetector = market_regime.NewMarketRegimeDetector(log)
	container.RegimeDetector.SetMarketIndexService(container.MarketIndexService)
	container.RegimeDetector.SetRegimePersistence(container.RegimePersistence)

	// Adaptive market service
	container.AdaptiveMarketService = adaptation.NewAdaptiveMarketService(
		container.RegimeDetector,
		nil, // performanceTracker - optional
		nil, // weightsCalculator - optional
		nil, // repository - optional
		log,
	)

	// Regime score provider adapter
	container.RegimeScoreProvider = market_regime.NewRegimeScoreProviderAdapter(container.RegimePersistence)

	// Wire up adaptive services to integration points
	container.OptimizerService.SetAdaptiveService(container.AdaptiveMarketService)
	container.OptimizerService.SetRegimeScoreProvider(container.RegimeScoreProvider)
	log.Info().Msg("Adaptive service wired to OptimizerService")

	// TagAssigner: adaptive quality gates
	// Create adapter to bridge type mismatch
	tagAssignerAdapter := &qualityGatesAdapter{service: container.AdaptiveMarketService}
	container.TagAssigner.SetAdaptiveService(tagAssignerAdapter)
	container.TagAssigner.SetRegimeScoreProvider(container.RegimeScoreProvider)
	log.Info().Msg("Adaptive service wired to TagAssigner")

	// ==========================================
	// STEP 13: Initialize Reliability Services
	// ==========================================

	// Create all database references map for reliability services
	databases := map[string]*database.DB{
		"universe":  container.UniverseDB,
		"config":    container.ConfigDB,
		"ledger":    container.LedgerDB,
		"portfolio": container.PortfolioDB,
		"history":   container.HistoryDB,
		"cache":     container.CacheDB,
	}

	// Initialize health services for each database
	dataDir := cfg.DataDir
	container.HealthServices = make(map[string]*reliability.DatabaseHealthService)
	container.HealthServices["universe"] = reliability.NewDatabaseHealthService(container.UniverseDB, "universe", dataDir+"/universe.db", log)
	container.HealthServices["config"] = reliability.NewDatabaseHealthService(container.ConfigDB, "config", dataDir+"/config.db", log)
	container.HealthServices["ledger"] = reliability.NewDatabaseHealthService(container.LedgerDB, "ledger", dataDir+"/ledger.db", log)
	container.HealthServices["portfolio"] = reliability.NewDatabaseHealthService(container.PortfolioDB, "portfolio", dataDir+"/portfolio.db", log)
	container.HealthServices["history"] = reliability.NewDatabaseHealthService(container.HistoryDB, "history", dataDir+"/history.db", log)
	container.HealthServices["cache"] = reliability.NewDatabaseHealthService(container.CacheDB, "cache", dataDir+"/cache.db", log)

	// Initialize backup service
	backupDir := dataDir + "/backups"
	container.BackupService = reliability.NewBackupService(databases, dataDir, backupDir, log)

	// Initialize R2 cloud backup services (optional - only if credentials are configured)
	r2AccountID := ""
	r2AccessKeyID := ""
	r2SecretAccessKey := ""
	r2BucketName := ""

	if container.SettingsRepo != nil {
		if val, err := container.SettingsRepo.Get("r2_account_id"); err == nil && val != nil {
			r2AccountID = *val
		}
		if val, err := container.SettingsRepo.Get("r2_access_key_id"); err == nil && val != nil {
			r2AccessKeyID = *val
		}
		if val, err := container.SettingsRepo.Get("r2_secret_access_key"); err == nil && val != nil {
			r2SecretAccessKey = *val
		}
		if val, err := container.SettingsRepo.Get("r2_bucket_name"); err == nil && val != nil {
			r2BucketName = *val
		}
	}

	// Only initialize R2 services if all credentials are provided
	if r2AccountID != "" && r2AccessKeyID != "" && r2SecretAccessKey != "" && r2BucketName != "" {
		r2Client, err := reliability.NewR2Client(r2AccountID, r2AccessKeyID, r2SecretAccessKey, r2BucketName, log)
		if err != nil {
			log.Warn().Err(err).Msg("Failed to initialize R2 client - R2 backup disabled")
		} else {
			container.R2Client = r2Client
			container.R2BackupService = reliability.NewR2BackupService(
				r2Client,
				container.BackupService,
				dataDir,
				log,
			)
			container.RestoreService = reliability.NewRestoreService(r2Client, dataDir, log)
			log.Info().Msg("R2 cloud backup services initialized")
		}
	} else {
		log.Debug().Msg("R2 credentials not configured - R2 backup disabled")
	}

	// ==========================================
	// STEP 14: Initialize Concentration Alert Service
	// ==========================================

	container.ConcentrationAlertService = allocation.NewConcentrationAlertService(
		container.PortfolioDB.Conn(),
		log,
	)

	// ==========================================
	// STEP 14.5: Initialize Quantum Calculator
	// ==========================================

	container.QuantumCalculator = quantum.NewQuantumProbabilityCalculator()

	// ==========================================
	// STEP 15: Initialize Callbacks (for jobs)
	// ==========================================

	// Display ticker update callback (called by sync cycle)
	container.UpdateDisplayTicker = func() error {
		text, err := container.TickerContentService.GenerateTickerText()
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
	container.EmergencyRebalance = func() error {
		log.Warn().Msg("EMERGENCY: Executing negative balance rebalancing")

		success, err := container.NegativeBalanceRebalancer.RebalanceNegativeBalances()
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

	log.Info().Msg("All services initialized")

	return nil
}

// qualityGatesAdapter adapts adaptation.AdaptiveMarketService to universe.AdaptiveQualityGatesProvider
type qualityGatesAdapter struct {
	service *adaptation.AdaptiveMarketService
}

func (a *qualityGatesAdapter) CalculateAdaptiveQualityGates(regimeScore float64) universe.QualityGateThresholdsProvider {
	thresholds := a.service.CalculateAdaptiveQualityGates(regimeScore)
	return thresholds // *adaptation.QualityGateThresholds implements the interface via GetFundamentals/GetLongTerm
}

// kellySettingsAdapter adapts settings.Service to optimization.KellySettingsService
type kellySettingsAdapter struct {
	service *settings.Service
}

func (a *kellySettingsAdapter) GetAdjustedKellyParams() optimization.KellyParamsConfig {
	params := a.service.GetAdjustedKellyParams()
	return optimization.KellyParamsConfig{
		FixedFractional:           params.FixedFractional,
		MinPositionSize:           params.MinPositionSize,
		MaxPositionSize:           params.MaxPositionSize,
		BearReduction:             params.BearReduction,
		BaseMultiplier:            params.BaseMultiplier,
		ConfidenceAdjustmentRange: params.ConfidenceAdjustmentRange,
		RegimeAdjustmentRange:     params.RegimeAdjustmentRange,
		MinMultiplier:             params.MinMultiplier,
		MaxMultiplier:             params.MaxMultiplier,
		BearMaxReduction:          params.BearMaxReduction,
		BullThreshold:             params.BullThreshold,
		BearThreshold:             params.BearThreshold,
	}
}

// tagSettingsAdapter adapts settings.Service to universe.TagSettingsService
type tagSettingsAdapter struct {
	service *settings.Service
}

func (a *tagSettingsAdapter) GetAdjustedValueThresholds() universe.ValueThresholds {
	params := a.service.GetAdjustedValueThresholds()
	return universe.ValueThresholds{
		ValueOpportunityDiscountPct: params.ValueOpportunityDiscountPct,
		DeepValueDiscountPct:        params.DeepValueDiscountPct,
		DeepValueExtremePct:         params.DeepValueExtremePct,
		UndervaluedPEThreshold:      params.UndervaluedPEThreshold,
		Below52wHighThreshold:       params.Below52wHighThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityThresholds() universe.QualityThresholds {
	params := a.service.GetAdjustedQualityThresholds()
	return universe.QualityThresholds{
		HighQualityFundamentals:        params.HighQualityFundamentals,
		HighQualityLongTerm:            params.HighQualityLongTerm,
		StableFundamentals:             params.StableFundamentals,
		StableVolatilityMax:            params.StableVolatilityMax,
		StableConsistency:              params.StableConsistency,
		ConsistentGrowerConsistency:    params.ConsistentGrowerConsistency,
		ConsistentGrowerCAGR:           params.ConsistentGrowerCAGR,
		StrongFundamentalsThreshold:    params.StrongFundamentalsThreshold,
		ValueOpportunityScoreThreshold: params.ValueOpportunityScoreThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedTechnicalThresholds() universe.TechnicalThresholds {
	params := a.service.GetAdjustedTechnicalThresholds()
	return universe.TechnicalThresholds{
		RSIOversold:               params.RSIOversold,
		RSIOverbought:             params.RSIOverbought,
		RecoveryMomentumThreshold: params.RecoveryMomentumThreshold,
		RecoveryFundamentalsMin:   params.RecoveryFundamentalsMin,
		RecoveryDiscountMin:       params.RecoveryDiscountMin,
	}
}

func (a *tagSettingsAdapter) GetAdjustedDividendThresholds() universe.DividendThresholds {
	params := a.service.GetAdjustedDividendThresholds()
	return universe.DividendThresholds{
		HighDividendYield:        params.HighDividendYield,
		DividendOpportunityScore: params.DividendOpportunityScore,
		DividendOpportunityYield: params.DividendOpportunityYield,
		DividendConsistencyScore: params.DividendConsistencyScore,
	}
}

func (a *tagSettingsAdapter) GetAdjustedDangerThresholds() universe.DangerThresholds {
	params := a.service.GetAdjustedDangerThresholds()
	return universe.DangerThresholds{
		OvervaluedPEThreshold:    params.OvervaluedPEThreshold,
		OvervaluedNearHighPct:    params.OvervaluedNearHighPct,
		UnsustainableGainsReturn: params.UnsustainableGainsReturn,
		ValuationStretchEMA:      params.ValuationStretchEMA,
		UnderperformingDays:      params.UnderperformingDays,
		StagnantReturnThreshold:  params.StagnantReturnThreshold,
		StagnantDaysThreshold:    params.StagnantDaysThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedPortfolioRiskThresholds() universe.PortfolioRiskThresholds {
	params := a.service.GetAdjustedPortfolioRiskThresholds()
	return universe.PortfolioRiskThresholds{
		OverweightDeviation:        params.OverweightDeviation,
		OverweightAbsolute:         params.OverweightAbsolute,
		ConcentrationRiskThreshold: params.ConcentrationRiskThreshold,
		NeedsRebalanceDeviation:    params.NeedsRebalanceDeviation,
	}
}

func (a *tagSettingsAdapter) GetAdjustedRiskProfileThresholds() universe.RiskProfileThresholds {
	params := a.service.GetAdjustedRiskProfileThresholds()
	return universe.RiskProfileThresholds{
		LowRiskVolatilityMax:          params.LowRiskVolatilityMax,
		LowRiskFundamentalsMin:        params.LowRiskFundamentalsMin,
		LowRiskDrawdownMax:            params.LowRiskDrawdownMax,
		MediumRiskVolatilityMin:       params.MediumRiskVolatilityMin,
		MediumRiskVolatilityMax:       params.MediumRiskVolatilityMax,
		MediumRiskFundamentalsMin:     params.MediumRiskFundamentalsMin,
		HighRiskVolatilityThreshold:   params.HighRiskVolatilityThreshold,
		HighRiskFundamentalsThreshold: params.HighRiskFundamentalsThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedBubbleTrapThresholds() universe.BubbleTrapThresholds {
	params := a.service.GetAdjustedBubbleTrapThresholds()
	return universe.BubbleTrapThresholds{
		BubbleCAGRThreshold:         params.BubbleCAGRThreshold,
		BubbleSharpeThreshold:       params.BubbleSharpeThreshold,
		BubbleVolatilityThreshold:   params.BubbleVolatilityThreshold,
		BubbleFundamentalsThreshold: params.BubbleFundamentalsThreshold,
		ValueTrapFundamentals:       params.ValueTrapFundamentals,
		ValueTrapLongTerm:           params.ValueTrapLongTerm,
		ValueTrapMomentum:           params.ValueTrapMomentum,
		ValueTrapVolatility:         params.ValueTrapVolatility,
		QuantumBubbleHighProb:       params.QuantumBubbleHighProb,
		QuantumBubbleWarningProb:    params.QuantumBubbleWarningProb,
		QuantumTrapHighProb:         params.QuantumTrapHighProb,
		QuantumTrapWarningProb:      params.QuantumTrapWarningProb,
		GrowthTagCAGRThreshold:      params.GrowthTagCAGRThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedTotalReturnThresholds() universe.TotalReturnThresholds {
	params := a.service.GetAdjustedTotalReturnThresholds()
	return universe.TotalReturnThresholds{
		ExcellentTotalReturn:     params.ExcellentTotalReturn,
		HighTotalReturn:          params.HighTotalReturn,
		ModerateTotalReturn:      params.ModerateTotalReturn,
		DividendTotalReturnYield: params.DividendTotalReturnYield,
		DividendTotalReturnCAGR:  params.DividendTotalReturnCAGR,
	}
}

func (a *tagSettingsAdapter) GetAdjustedRegimeThresholds() universe.RegimeThresholds {
	params := a.service.GetAdjustedRegimeThresholds()
	return universe.RegimeThresholds{
		BearSafeVolatility:        params.BearSafeVolatility,
		BearSafeFundamentals:      params.BearSafeFundamentals,
		BearSafeDrawdown:          params.BearSafeDrawdown,
		BullGrowthCAGR:            params.BullGrowthCAGR,
		BullGrowthFundamentals:    params.BullGrowthFundamentals,
		RegimeVolatileVolatility:  params.RegimeVolatileVolatility,
		SidewaysValueFundamentals: params.SidewaysValueFundamentals,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityGateParams() universe.QualityGateParams {
	params := a.service.GetAdjustedQualityGateParams()
	return universe.QualityGateParams{
		FundamentalsThreshold:            params.FundamentalsThreshold,
		LongTermThreshold:                params.LongTermThreshold,
		ExceptionalThreshold:             params.ExceptionalThreshold,
		AbsoluteMinCAGR:                  params.AbsoluteMinCAGR,
		ExceptionalExcellenceThreshold:   params.ExceptionalExcellenceThreshold,
		QualityValueFundamentalsMin:      params.QualityValueFundamentalsMin,
		QualityValueOpportunityMin:       params.QualityValueOpportunityMin,
		QualityValueLongTermMin:          params.QualityValueLongTermMin,
		DividendIncomeFundamentalsMin:    params.DividendIncomeFundamentalsMin,
		DividendIncomeScoreMin:           params.DividendIncomeScoreMin,
		DividendIncomeYieldMin:           params.DividendIncomeYieldMin,
		RiskAdjustedLongTermThreshold:    params.RiskAdjustedLongTermThreshold,
		RiskAdjustedSharpeThreshold:      params.RiskAdjustedSharpeThreshold,
		RiskAdjustedSortinoThreshold:     params.RiskAdjustedSortinoThreshold,
		RiskAdjustedVolatilityMax:        params.RiskAdjustedVolatilityMax,
		CompositeFundamentalsWeight:      params.CompositeFundamentalsWeight,
		CompositeLongTermWeight:          params.CompositeLongTermWeight,
		CompositeScoreMin:                params.CompositeScoreMin,
		CompositeFundamentalsFloor:       params.CompositeFundamentalsFloor,
		GrowthOpportunityCAGRMin:         params.GrowthOpportunityCAGRMin,
		GrowthOpportunityFundamentalsMin: params.GrowthOpportunityFundamentalsMin,
		GrowthOpportunityVolatilityMax:   params.GrowthOpportunityVolatilityMax,
		HighScoreThreshold:               params.HighScoreThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedVolatilityParams() universe.VolatilityParams {
	params := a.service.GetAdjustedVolatilityParams()
	return universe.VolatilityParams{
		VolatileThreshold:     params.VolatileThreshold,
		HighThreshold:         params.HighThreshold,
		MaxAcceptable:         params.MaxAcceptable,
		MaxAcceptableDrawdown: params.MaxAcceptableDrawdown,
	}
}

// dataSourceSettingsAdapter adapts settings.Repository to services.SettingsGetter
type dataSourceSettingsAdapter struct {
	repo *settings.Repository
}

func (a *dataSourceSettingsAdapter) Get(key string) (*string, error) {
	if a.repo == nil {
		return nil, nil
	}
	return a.repo.Get(key)
}

// brokerClientAdapter adapts domain.BrokerClient to services.BrokerClientInterface
type brokerClientAdapter struct {
	client domain.BrokerClient
}

func (a *brokerClientAdapter) GetHistoricalPrices(symbol string, from, to int64, interval int) ([]domain.BrokerOHLCV, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	return a.client.GetHistoricalPrices(symbol, from, to, interval)
}

func (a *brokerClientAdapter) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	return a.client.GetQuotes(symbols)
}

func (a *brokerClientAdapter) IsConnected() bool {
	if a.client == nil {
		return false
	}
	return a.client.IsConnected()
}

// yahooClientAdapter adapts yahoo.NativeClient to services.DataFetcherYahooClient
type yahooClientAdapter struct {
	client *yahoo.NativeClient
}

func (a *yahooClientAdapter) GetHistoricalPrices(symbol string, yahooSymbolOverride *string, period string) ([]yahoo.HistoricalPrice, error) {
	if a.client == nil {
		return nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetHistoricalPrices(symbol, yahooSymbolOverride, period)
}

func (a *yahooClientAdapter) GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error) {
	if a.client == nil {
		return nil, nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetSecurityCountryAndExchange(symbol, yahooSymbolOverride)
}

func (a *yahooClientAdapter) GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error) {
	if a.client == nil {
		return nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetSecurityIndustry(symbol, yahooSymbolOverride)
}

func (a *yahooClientAdapter) GetQuoteName(symbol string, yahooSymbolOverride *string) (*string, error) {
	if a.client == nil {
		return nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetQuoteName(symbol, yahooSymbolOverride)
}

func (a *yahooClientAdapter) GetQuoteType(symbol string, yahooSymbolOverride *string) (string, error) {
	if a.client == nil {
		return "", fmt.Errorf("yahoo client not available")
	}
	return a.client.GetQuoteType(symbol, yahooSymbolOverride)
}

func (a *yahooClientAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if a.client == nil {
		return nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetBatchQuotes(symbolMap)
}

// historicalDataFetcherAdapter adapts services.DataFetcherService to universe.HistoricalDataFetcher
type historicalDataFetcherAdapter struct {
	fetcher *services.DataFetcherService
}

func (a *historicalDataFetcherAdapter) GetHistoricalPrices(tradernetSymbol string, yahooSymbol string, years int) ([]universe.HistoricalPriceData, string, error) {
	if a.fetcher == nil {
		return nil, "", fmt.Errorf("data fetcher service not available")
	}

	prices, source, err := a.fetcher.GetHistoricalPrices(tradernetSymbol, yahooSymbol, years)
	if err != nil {
		return nil, "", err
	}

	// Convert services.HistoricalPrice to universe.HistoricalPriceData
	result := make([]universe.HistoricalPriceData, len(prices))
	for i, p := range prices {
		result[i] = universe.HistoricalPriceData{
			Date:   p.Date,
			Open:   p.Open,
			High:   p.High,
			Low:    p.Low,
			Close:  p.Close,
			Volume: p.Volume,
		}
	}

	return result, string(source), nil
}

// metadataFetcherAdapter adapts services.DataFetcherService to universe.MetadataFetcher
type metadataFetcherAdapter struct {
	fetcher *services.DataFetcherService
}

func (a *metadataFetcherAdapter) GetSecurityMetadata(tradernetSymbol string, yahooSymbol string) (*universe.SecurityMetadataResult, string, error) {
	if a.fetcher == nil {
		return nil, "", fmt.Errorf("data fetcher service not available")
	}

	metadata, source, err := a.fetcher.GetSecurityMetadata(tradernetSymbol, yahooSymbol)
	if err != nil {
		return nil, "", err
	}

	// Convert services.SecurityMetadata to universe.SecurityMetadataResult
	return &universe.SecurityMetadataResult{
		Name:        metadata.Name,
		Country:     metadata.Country,
		Exchange:    metadata.Exchange,
		Industry:    metadata.Industry,
		Sector:      metadata.Sector,
		Currency:    metadata.Currency,
		ProductType: metadata.ProductType,
	}, string(source), nil
}

// ==========================================
// Adapters for OpportunityContextBuilder
// ==========================================

// ocbPositionRepoAdapter adapts portfolio.PositionRepository to services.PositionRepository
type ocbPositionRepoAdapter struct {
	repo *portfolio.PositionRepository
}

func (a *ocbPositionRepoAdapter) GetAll() ([]portfolio.Position, error) {
	return a.repo.GetAll()
}

// ocbSecurityRepoAdapter adapts universe.SecurityRepository to services.SecurityRepository
type ocbSecurityRepoAdapter struct {
	repo *universe.SecurityRepository
}

func (a *ocbSecurityRepoAdapter) GetAllActive() ([]universe.Security, error) {
	return a.repo.GetAllActive()
}

func (a *ocbSecurityRepoAdapter) GetByISIN(isin string) (*universe.Security, error) {
	return a.repo.GetByISIN(isin)
}

func (a *ocbSecurityRepoAdapter) GetBySymbol(symbol string) (*universe.Security, error) {
	return a.repo.GetBySymbol(symbol)
}

// ocbAllocationRepoAdapter adapts allocation.Repository to services.AllocationRepository
type ocbAllocationRepoAdapter struct {
	repo *allocation.Repository
}

func (a *ocbAllocationRepoAdapter) GetAll() (map[string]float64, error) {
	return a.repo.GetAll()
}

// ocbGroupingRepoAdapter adapts allocation.GroupingRepository to services.GroupingRepository
type ocbGroupingRepoAdapter struct {
	repo      *allocation.GroupingRepository
	allocRepo *allocation.Repository
}

func (a *ocbGroupingRepoAdapter) GetCountryGroups() (map[string][]string, error) {
	return a.repo.GetCountryGroups()
}

func (a *ocbGroupingRepoAdapter) GetIndustryGroups() (map[string][]string, error) {
	return a.repo.GetIndustryGroups()
}

func (a *ocbGroupingRepoAdapter) GetGroupWeights(groupType string) (map[string]float64, error) {
	// Get weights from allocation repository (targets)
	if a.allocRepo == nil {
		return make(map[string]float64), nil
	}
	return a.allocRepo.GetAll()
}

// ocbTradeRepoAdapter adapts trading.TradeRepository to services.TradeRepository
type ocbTradeRepoAdapter struct {
	repo *trading.TradeRepository
}

func (a *ocbTradeRepoAdapter) GetRecentlySoldISINs(days int) (map[string]bool, error) {
	return a.repo.GetRecentlySoldISINs(days)
}

func (a *ocbTradeRepoAdapter) GetRecentlyBoughtISINs(days int) (map[string]bool, error) {
	return a.repo.GetRecentlyBoughtISINs(days)
}

// ocbScoresRepoAdapter adapts database to services.ScoresRepository
// Uses direct database queries like the scheduler adapters
type ocbScoresRepoAdapter struct {
	db *sql.DB // portfolio.db - scores table
}

func (a *ocbScoresRepoAdapter) GetTotalScores(isinList []string) (map[string]float64, error) {
	totalScores := make(map[string]float64)
	if len(isinList) == 0 {
		return totalScores, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, total_score FROM scores WHERE isin IN (%s) AND total_score IS NOT NULL`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var totalScore sql.NullFloat64
		if err := rows.Scan(&isin, &totalScore); err != nil {
			continue
		}
		if totalScore.Valid && totalScore.Float64 > 0 {
			totalScores[isin] = totalScore.Float64
		}
	}
	return totalScores, nil
}

func (a *ocbScoresRepoAdapter) GetCAGRs(isinList []string) (map[string]float64, error) {
	cagrs := make(map[string]float64)
	if len(isinList) == 0 {
		return cagrs, nil
	}

	query := `SELECT isin, cagr_score FROM scores WHERE cagr_score IS NOT NULL AND cagr_score > 0`
	rows, err := a.db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	isinSet := make(map[string]bool)
	for _, isin := range isinList {
		isinSet[isin] = true
	}

	for rows.Next() {
		var isin string
		var cagrScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore); err != nil {
			continue
		}
		if !isinSet[isin] {
			continue
		}
		if cagrScore.Valid && cagrScore.Float64 > 0 {
			// Convert CAGR score (0-100) to CAGR value (e.g., 0.11 for 11%)
			cagrValue := (cagrScore.Float64 / 100.0) * 0.30 // Assuming max 30% CAGR
			if cagrValue > 0 {
				cagrs[isin] = cagrValue
			}
		}
	}
	return cagrs, nil
}

func (a *ocbScoresRepoAdapter) GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error) {
	longTermScores := make(map[string]float64)
	fundamentalsScores := make(map[string]float64)
	if len(isinList) == 0 {
		return longTermScores, fundamentalsScores, nil
	}

	query := `SELECT isin, cagr_score, fundamental_score FROM scores WHERE isin != '' AND isin IS NOT NULL`
	rows, err := a.db.Query(query)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	isinSet := make(map[string]bool)
	for _, isin := range isinList {
		isinSet[isin] = true
	}

	for rows.Next() {
		var isin string
		var cagrScore, fundamentalScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore, &fundamentalScore); err != nil {
			continue
		}
		if !isinSet[isin] {
			continue
		}
		if cagrScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64/100.0))
			longTermScores[isin] = normalized
		}
		if fundamentalScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, fundamentalScore.Float64/100.0))
			fundamentalsScores[isin] = normalized
		}
	}
	return longTermScores, fundamentalsScores, nil
}

func (a *ocbScoresRepoAdapter) GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
	opportunityScores := make(map[string]float64)
	momentumScores := make(map[string]float64)
	volatility := make(map[string]float64)
	if len(isinList) == 0 {
		return opportunityScores, momentumScores, volatility, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, opportunity_score, volatility, drawdown_score FROM scores WHERE isin IN (%s)`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, nil, nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var opportunityScore, vol, drawdownScore sql.NullFloat64
		if err := rows.Scan(&isin, &opportunityScore, &vol, &drawdownScore); err != nil {
			continue
		}
		if opportunityScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, opportunityScore.Float64/100.0))
			opportunityScores[isin] = normalized
		}
		if vol.Valid && vol.Float64 > 0 {
			volatility[isin] = vol.Float64
		}
		if drawdownScore.Valid {
			rawDrawdown := math.Max(-1.0, math.Min(0.0, drawdownScore.Float64/100.0))
			momentum := 1.0 + rawDrawdown
			momentum = (momentum * 2.0) - 1.0
			momentum = math.Max(-1.0, math.Min(1.0, momentum))
			momentumScores[isin] = momentum
		}
	}
	return opportunityScores, momentumScores, volatility, nil
}

func (a *ocbScoresRepoAdapter) GetRiskMetrics(isinList []string) (map[string]float64, map[string]float64, error) {
	sharpe := make(map[string]float64)
	maxDrawdown := make(map[string]float64)
	if len(isinList) == 0 {
		return sharpe, maxDrawdown, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, sharpe_score, drawdown_score FROM scores WHERE isin IN (%s)`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var sharpeScore, drawdownScore sql.NullFloat64
		if err := rows.Scan(&isin, &sharpeScore, &drawdownScore); err != nil {
			continue
		}
		if sharpeScore.Valid {
			// Sharpe score (0-100) to ratio (e.g., 1.5)
			sharpe[isin] = (sharpeScore.Float64 / 100.0) * 3.0 // Max 3.0 Sharpe
		}
		if drawdownScore.Valid {
			// Drawdown score to max drawdown (negative percentage)
			maxDrawdown[isin] = -(100.0 - drawdownScore.Float64) / 100.0
		}
	}
	return sharpe, maxDrawdown, nil
}

// ocbSettingsRepoAdapter adapts settings.Repository to services.SettingsRepository
type ocbSettingsRepoAdapter struct {
	repo       *settings.Repository
	configRepo *planningrepo.ConfigRepository
}

func (a *ocbSettingsRepoAdapter) GetTargetReturnSettings() (float64, float64, error) {
	// Get from planner config if available
	if a.configRepo != nil {
		config, err := a.configRepo.GetDefaultConfig()
		if err == nil && config != nil {
			return config.OptimizerTargetReturn, 0.80, nil // OptimizerTargetReturn is the target return setting
		}
	}
	return 0.11, 0.80, nil // Defaults: 11% target return, 80% threshold
}

func (a *ocbSettingsRepoAdapter) GetCooloffDays() (int, error) {
	if a.configRepo != nil {
		config, err := a.configRepo.GetDefaultConfig()
		if err == nil && config != nil && config.SellCooldownDays > 0 {
			return config.SellCooldownDays, nil
		}
	}
	return 180, nil // Default
}

func (a *ocbSettingsRepoAdapter) GetVirtualTestCash() (float64, error) {
	if a.repo == nil {
		return 0, nil
	}
	// Check if research mode is enabled
	val, err := a.repo.Get("research_mode")
	if err != nil || val == nil || *val != "true" {
		return 0, nil
	}
	// Get virtual test cash amount
	cashStr, err := a.repo.Get("virtual_test_cash")
	if err != nil || cashStr == nil {
		return 0, nil
	}
	var cash float64
	if _, err := fmt.Sscanf(*cashStr, "%f", &cash); err != nil {
		return 0, nil
	}
	return cash, nil
}

func (a *ocbSettingsRepoAdapter) IsCooloffDisabled() (bool, error) {
	if a.repo == nil {
		return false, nil
	}
	// Check if research mode is enabled - cooloff can only be disabled in research mode
	modeVal, err := a.repo.Get("trading_mode")
	if err != nil || modeVal == nil || *modeVal != "research" {
		return false, nil
	}
	// Check if cooloff checks are disabled
	val, err := a.repo.Get("disable_cooloff_checks")
	if err != nil || val == nil {
		return false, nil
	}
	var disabled float64
	if _, err := fmt.Sscanf(*val, "%f", &disabled); err != nil {
		return false, nil
	}
	return disabled >= 1.0, nil
}

// ocbRegimeRepoAdapter adapts market_regime.RegimeScoreProviderAdapter to services.RegimeRepository
type ocbRegimeRepoAdapter struct {
	adapter *market_regime.RegimeScoreProviderAdapter
}

func (a *ocbRegimeRepoAdapter) GetCurrentRegimeScore() (float64, error) {
	if a.adapter == nil {
		return 0.0, nil
	}
	return a.adapter.GetCurrentRegimeScore()
}

// ocbCashManagerAdapter adapts domain.CashManager to services.CashManager
type ocbCashManagerAdapter struct {
	manager domain.CashManager
}

func (a *ocbCashManagerAdapter) GetAllCashBalances() (map[string]float64, error) {
	return a.manager.GetAllCashBalances()
}

// ocbPriceClientAdapter adapts yahoo.NativeClient to services.PriceClient
type ocbPriceClientAdapter struct {
	client *yahoo.NativeClient
}

func (a *ocbPriceClientAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if a.client == nil {
		return nil, fmt.Errorf("yahoo client not available")
	}
	return a.client.GetBatchQuotes(symbolMap)
}

// ocbBrokerClientAdapter adapts domain.BrokerClient to services.BrokerClient (for OCB)
type ocbBrokerClientAdapter struct {
	client domain.BrokerClient
}

func (a *ocbBrokerClientAdapter) IsConnected() bool {
	if a.client == nil {
		return false
	}
	return a.client.IsConnected()
}

func (a *ocbBrokerClientAdapter) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	return a.client.GetPendingOrders()
}

// ocbDismissedFilterRepoAdapter adapts DismissedFilterRepository to services.DismissedFilterRepository
type ocbDismissedFilterRepoAdapter struct {
	repo *planningrepo.DismissedFilterRepository
}

func (a *ocbDismissedFilterRepoAdapter) GetAll() (map[string]map[string][]string, error) {
	if a.repo == nil {
		return make(map[string]map[string][]string), nil
	}
	return a.repo.GetAll()
}
