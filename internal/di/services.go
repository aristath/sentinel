// Package di provides dependency injection for service implementations.
package di

import (
	"fmt"
	"time"

	"github.com/aristath/sentinel/internal/clients/exchangerate"
	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/clients/yahoo"
	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
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
	planningevaluation "github.com/aristath/sentinel/internal/modules/planning/evaluation"
	planninghash "github.com/aristath/sentinel/internal/modules/planning/hash"
	planningplanner "github.com/aristath/sentinel/internal/modules/planning/planner"
	planningstatemonitor "github.com/aristath/sentinel/internal/modules/planning/state_monitor"
	planninguniverse "github.com/aristath/sentinel/internal/modules/planning/universe_monitor"
	"github.com/aristath/sentinel/internal/modules/portfolio"
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
	container.ExchangeRateAPIClient = exchangerate.NewClient(log)
	log.Info().Msg("ExchangeRateAPI client initialized")

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

	// Exchange rate cache service (wraps ExchangeRateAPI + CurrencyExchangeService + Yahoo fallback)
	container.ExchangeRateCacheService = services.NewExchangeRateCacheService(
		container.ExchangeRateAPIClient,   // NEW: Primary source (exchangerate-api.com)
		container.CurrencyExchangeService, // Tradernet (now secondary)
		container.YahooClient,
		container.HistoryDBClient,
		container.SettingsService,
		log,
	)

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
		container.PlannerConfigRepo, // NEW: Planner config for transaction costs
		container.OrderBookService,  // NEW: Order book analysis for optimal limit pricing
		container.YahooClient,
		container.HistoryDB.Conn(), // Get underlying *sql.DB
		container.SecurityRepo,
		log,
	)

	// ==========================================
	// STEP 5: Initialize Universe Services
	// ==========================================

	// Historical sync service
	container.HistoricalSyncService = universe.NewHistoricalSyncService(
		container.YahooClient,
		container.SecurityRepo,
		container.HistoryDBClient,
		time.Second*2, // Rate limit delay
		log,
	)

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

	// Sync service (scoreCalculator will be set later)
	container.SyncService = universe.NewSyncService(
		container.SecurityRepo,
		container.HistoricalSyncService,
		container.YahooClient,
		nil, // scoreCalculator - will be set later
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

	// Security scorer (used by handlers)
	container.SecurityScorer = scorers.NewSecurityScorer()

	// ==========================================
	// STEP 8: Initialize Planning Services
	// ==========================================

	// Opportunities service
	container.OpportunitiesService = opportunities.NewService(log)

	// Risk builder (needed for sequences service)
	container.RiskBuilder = optimization.NewRiskModelBuilder(container.HistoryDB.Conn(), container.UniverseDB.Conn(), log)

	// Sequences service
	container.SequencesService = sequences.NewService(log, container.RiskBuilder)

	// Evaluation service (4 workers)
	container.EvaluationService = planningevaluation.NewService(4, log)

	// Planner service (core planner)
	container.PlannerService = planningplanner.NewPlanner(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		container.CurrencyExchangeService,
		log,
	)

	// Planning service
	container.PlanningService = planning.NewService(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		container.CurrencyExchangeService,
		log,
	)

	// Universe monitor (monitors state changes and invalidates recommendations)
	// DEPRECATED: Now replaced by StateMonitor with unified state hashing
	// Kept for backward compatibility but not started
	// TODO: Remove once StateMonitor is confirmed working
	container.UniverseMonitor = planninguniverse.NewUniverseMonitor(
		container.SecurityRepo,
		container.PositionRepo,
		container.CashManager,
		container.PlannerConfigRepo,
		container.RecommendationRepo,
		container.PlannerRepo,
		container.ConfigDB.Conn(),
		log,
	)
	log.Info().Msg("Universe monitor initialized (not started - replaced by StateMonitor)")

	// State hash service (calculates unified state hash for change detection)
	container.StateHashService = planninghash.NewStateHashService(
		container.PositionRepo,
		container.SecurityRepo,
		container.ScoreRepo,
		container.CashManager,
		container.SettingsRepo,
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
		0.5,   // fixedFractional: 0.5 (half-Kelly)
		0.005, // minPositionSize: 0.5%
		0.20,  // maxPositionSize: 20%
		container.ReturnsCalc,
		container.RiskBuilder,
		container.RegimeDetector,
	)

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
		container.YahooClient,
		container.PriceConversionService,
		container.PlannerConfigRepo,
		container.RecommendationRepo,
		container.PortfolioDB.Conn(),
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
		// "agents": removed - sequences/evaluations now in-memory
		"history": container.HistoryDB,
		"cache":   container.CacheDB,
	}

	// Initialize health services for each database
	dataDir := cfg.DataDir
	container.HealthServices = make(map[string]*reliability.DatabaseHealthService)
	container.HealthServices["universe"] = reliability.NewDatabaseHealthService(container.UniverseDB, "universe", dataDir+"/universe.db", log)
	container.HealthServices["config"] = reliability.NewDatabaseHealthService(container.ConfigDB, "config", dataDir+"/config.db", log)
	container.HealthServices["ledger"] = reliability.NewDatabaseHealthService(container.LedgerDB, "ledger", dataDir+"/ledger.db", log)
	container.HealthServices["portfolio"] = reliability.NewDatabaseHealthService(container.PortfolioDB, "portfolio", dataDir+"/portfolio.db", log)
	// container.HealthServices["agents"] removed - sequences/evaluations now in-memory
	container.HealthServices["history"] = reliability.NewDatabaseHealthService(container.HistoryDB, "history", dataDir+"/history.db", log)
	container.HealthServices["cache"] = reliability.NewDatabaseHealthService(container.CacheDB, "cache", dataDir+"/cache.db", log)

	// Initialize backup service
	backupDir := dataDir + "/backups"
	container.BackupService = reliability.NewBackupService(databases, dataDir, backupDir, log)

	// ==========================================
	// STEP 14: Initialize Concentration Alert Service
	// ==========================================

	container.ConcentrationAlertService = allocation.NewConcentrationAlertService(
		container.PortfolioDB.Conn(),
		log,
	)

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
