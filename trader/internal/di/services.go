// Package di provides dependency injection for service implementations.
package di

import (
	"fmt"
	"time"

	"github.com/aristath/portfolioManager/internal/clients/tradernet"
	"github.com/aristath/portfolioManager/internal/clients/yahoo"
	"github.com/aristath/portfolioManager/internal/config"
	"github.com/aristath/portfolioManager/internal/database"
	"github.com/aristath/portfolioManager/internal/events"
	"github.com/aristath/portfolioManager/internal/modules/adaptation"
	"github.com/aristath/portfolioManager/internal/modules/allocation"
	"github.com/aristath/portfolioManager/internal/modules/analytics"
	"github.com/aristath/portfolioManager/internal/modules/cash_flows"
	"github.com/aristath/portfolioManager/internal/modules/display"
	"github.com/aristath/portfolioManager/internal/modules/market_hours"
	"github.com/aristath/portfolioManager/internal/modules/opportunities"
	"github.com/aristath/portfolioManager/internal/modules/optimization"
	"github.com/aristath/portfolioManager/internal/modules/planning"
	planningevaluation "github.com/aristath/portfolioManager/internal/modules/planning/evaluation"
	planningplanner "github.com/aristath/portfolioManager/internal/modules/planning/planner"
	"github.com/aristath/portfolioManager/internal/modules/portfolio"
	"github.com/aristath/portfolioManager/internal/modules/rebalancing"
	"github.com/aristath/portfolioManager/internal/modules/scoring/scorers"
	"github.com/aristath/portfolioManager/internal/modules/sequences"
	"github.com/aristath/portfolioManager/internal/modules/settings"
	"github.com/aristath/portfolioManager/internal/modules/trading"
	"github.com/aristath/portfolioManager/internal/modules/universe"
	"github.com/aristath/portfolioManager/internal/queue"
	"github.com/aristath/portfolioManager/internal/reliability"
	"github.com/aristath/portfolioManager/internal/services"
	"github.com/aristath/portfolioManager/internal/ticker"
	"github.com/rs/zerolog"
)

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

	// Tradernet client
	container.TradernetClient = tradernet.NewClient(cfg.TradernetAPIKey, cfg.TradernetAPISecret, log)

	// Yahoo Finance client (native Go implementation)
	container.YahooClient = yahoo.NewNativeClient(log)
	log.Info().Msg("Using native Go Yahoo Finance client")

	// ==========================================
	// STEP 2: Initialize Basic Services
	// ==========================================

	// Currency exchange service
	container.CurrencyExchangeService = services.NewCurrencyExchangeService(container.TradernetClient, log)

	// Market hours service
	container.MarketHoursService = market_hours.NewMarketHoursService()

	// Event system (new bus-based architecture)
	container.EventBus = events.NewBus(log)
	container.EventManager = events.NewManager(container.EventBus, log)

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

	// Settings service (needed for trade safety and other services)
	container.SettingsService = settings.NewService(container.SettingsRepo, log)

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
		container.TradernetClient,
		container.TradeSafetyService,
		log,
	)

	// Trade execution service for emergency rebalancing
	container.TradeExecutionService = services.NewTradeExecutionService(
		container.TradernetClient,
		container.TradeRepo,
		container.PositionRepo,
		cashManager, // Use concrete type for now, will be interface later
		container.CurrencyExchangeService,
		log,
	)

	// ==========================================
	// STEP 5: Initialize Portfolio Service
	// ==========================================

	// Portfolio service
	container.PortfolioService = portfolio.NewPortfolioService(
		container.PositionRepo,
		container.AllocRepo,
		cashManager, // Use concrete type
		container.UniverseDB.Conn(),
		container.TradernetClient,
		container.CurrencyExchangeService,
		log,
	)

	// ==========================================
	// STEP 6: Initialize Cash Flows Services
	// ==========================================

	// Dividend service implementation (adapter - uses existing dividendRepo)
	container.DividendService = cash_flows.NewDividendServiceImpl(container.DividendRepo, log)

	// Dividend creator
	container.DividendCreator = cash_flows.NewDividendCreator(container.DividendService, log)

	// Deposit processor (uses CashManager)
	container.DepositProcessor = cash_flows.NewDepositProcessor(cashManager, log)

	// Tradernet adapter (adapts tradernet.Client to cash_flows.TradernetClient)
	tradernetAdapter := cash_flows.NewTradernetAdapter(container.TradernetClient)

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
	// STEP 7: Initialize Universe Services
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
		container.TradernetClient,
		container.SecurityRepo,
		log,
	)

	// Security setup service (scoreCalculator will be set later)
	container.SetupService = universe.NewSecuritySetupService(
		container.SymbolResolver,
		container.SecurityRepo,
		container.TradernetClient,
		container.YahooClient,
		container.HistoricalSyncService,
		container.EventManager,
		nil, // scoreCalculator - will be set later
		log,
	)

	// Sync service (scoreCalculator will be set later)
	container.SyncService = universe.NewSyncService(
		container.SecurityRepo,
		container.HistoricalSyncService,
		container.YahooClient,
		nil, // scoreCalculator - will be set later
		container.TradernetClient,
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
		log,
	)

	// Planning service
	container.PlanningService = planning.NewService(
		container.OpportunitiesService,
		container.SequencesService,
		container.EvaluationService,
		container.SecurityRepo,
		log,
	)

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
		container.TradernetClient,
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
		container.TradernetClient,
		container.YahooClient,
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
	container.MarketIndexService = portfolio.NewMarketIndexService(
		container.UniverseDB.Conn(),
		container.HistoryDB.Conn(),
		container.TradernetClient,
		log,
	)

	// Regime persistence for smoothing and history
	container.RegimePersistence = portfolio.NewRegimePersistence(container.ConfigDB.Conn(), log)

	// Market regime detector
	container.RegimeDetector = portfolio.NewMarketRegimeDetector(log)
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
	container.RegimeScoreProvider = portfolio.NewRegimeScoreProviderAdapter(container.RegimePersistence)

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
		"agents":    container.AgentsDB,
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
	container.HealthServices["agents"] = reliability.NewDatabaseHealthService(container.AgentsDB, "agents", dataDir+"/agents.db", log)
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
