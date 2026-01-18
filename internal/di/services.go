/**
 * Package di provides dependency injection for service implementations.
 *
 * This package initializes all business logic services in the correct dependency order.
 * Services are the SINGLE SOURCE OF TRUTH for all service creation - all services
 * must be created here to ensure proper dependency injection and initialization order.
 *
 * Initialization Sequence:
 * 1. Clients (broker, market status WebSocket)
 * 2. Basic Services (currency exchange, market hours, event system)
 * 3. Cash Manager (cash-as-balances architecture)
 * 4. Trading Services (trade safety, trading, trade execution)
 * 5. Universe Services (historical sync, symbol resolver, security setup)
 * 6. Portfolio Service (portfolio management)
 * 7. Cash Flows Services (dividends, deposits)
 * 8. Remaining Universe Services (sync, universe, tag assigner)
 * 9. Planning Services (opportunities, sequences, evaluation, planner)
 * 10. Optimization Services (risk builder, constraints, returns, Kelly, CVaR, BL, optimizer)
 * 11. Calculation Cache and Analytics
 * 12. Rebalancing Services
 * 13. Ticker and Display Services
 * 14. Adaptive Market Services (market regime detection)
 * 15. Reliability Services (backup, health checks, R2)
 * 16. Concentration Alert Service
 * 17. Quantum Calculator
 * 18. Callbacks (for jobs)
 */
package di

import (
	"database/sql"
	"fmt"
	"math"
	"os"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/config"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/analytics"
	"github.com/aristath/sentinel/internal/modules/calculations"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/aristath/sentinel/internal/modules/optimization"
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
	"github.com/aristath/sentinel/internal/reliability"
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/internal/services"
	"github.com/aristath/sentinel/internal/ticker"
	"github.com/rs/zerolog"
)

/**
 * securitySetupServiceAdapter adapts universe.SecuritySetupService to portfolio.SecuritySetupServiceInterface.
 *
 * This adapter is needed because Go doesn't support return type covariance in interfaces.
 * The portfolio package expects a different interface signature than what universe provides.
 *
 * Note: User-configurable fields (min_lot, allow_buy, allow_sell) are set via security_overrides
 * after security creation, not during the AddSecurityByIdentifier call.
 */
type securitySetupServiceAdapter struct {
	service *universe.SecuritySetupService
}

/**
 * AddSecurityByIdentifier implements portfolio.SecuritySetupServiceInterface.
 *
 * Delegates to the underlying universe.SecuritySetupService.
 *
 * @param identifier - Security identifier (ISIN or symbol)
 * @returns interface{} - Created security (type assertion needed by caller)
 * @returns error - Error if security creation fails
 */
func (a *securitySetupServiceAdapter) AddSecurityByIdentifier(identifier string) (interface{}, error) {
	return a.service.AddSecurityByIdentifier(identifier)
}

/**
 * InitializeServices creates all services and stores them in the container.
 *
 * This is the SINGLE SOURCE OF TRUTH for all service creation.
 * Services are created in dependency order to ensure all dependencies exist
 * before they are needed.
 *
 * The initialization is organized into logical steps:
 * - Step 1: Clients (external API integrations)
 * - Step 2: Basic Services (foundational services)
 * - Step 3: Cash Manager (cash-as-balances architecture)
 * - Step 4: Trading Services (trade validation and execution)
 * - Step 5: Universe Services (security management)
 * - Step 6: Portfolio Service (portfolio management)
 * - Step 7: Cash Flows Services (dividends, deposits)
 * - Step 8: Remaining Universe Services (sync, tagging)
 * - Step 9: Planning Services (opportunity identification, sequence generation, evaluation)
 * - Step 10: Optimization Services (risk models, constraints, portfolio optimization)
 * - Step 11: Calculation Cache and Analytics
 * - Step 12: Rebalancing Services
 * - Step 13: Ticker and Display Services
 * - Step 14: Adaptive Market Services (market regime detection)
 * - Step 15: Reliability Services (backup, health checks)
 * - Step 16: Concentration Alert Service
 * - Step 17: Quantum Calculator
 * - Step 18: Callbacks (for jobs)
 *
 * @param container - Container to store service instances (must not be nil)
 * @param cfg - Application configuration (with settings loaded from database)
 * @param displayManager - LED display state manager (can be nil in tests)
 * @param log - Structured logger instance
 * @returns error - Error if service initialization fails
 */
func InitializeServices(container *Container, cfg *config.Config, displayManager *display.StateManager, log zerolog.Logger) error {
	if container == nil {
		return fmt.Errorf("container cannot be nil")
	}

	// ==========================================
	// STEP 1: Initialize Clients
	// ==========================================
	// External API clients must be initialized first as they are dependencies
	// for many services (currency exchange, price fetching, trade execution)

	// Broker client (Tradernet adapter) - single external data source
	// Tradernet is the only external data source for prices, quotes, and trade execution
	container.BrokerClient = tradernet.NewTradernetBrokerAdapter(cfg.TradernetAPIKey, cfg.TradernetAPISecret, log)
	log.Info().Msg("Broker client initialized (Tradernet adapter)")

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
			// Allow manual override via settings (for testing/development)
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

	// ==========================================
	// STEP 2: Initialize Basic Services
	// ==========================================
	// Foundational services that other services depend on

	// Currency exchange service
	// Fetches exchange rates from Tradernet API
	container.CurrencyExchangeService = services.NewCurrencyExchangeService(container.BrokerClient, log)

	// Market hours service
	// Provides market hours and holiday information for all exchanges
	container.MarketHoursService = market_hours.NewMarketHoursService()

	// Market state detector (for market-aware scheduling)
	// Detects whether markets are open/closed for work processor scheduling
	container.MarketStateDetector = market_regime.NewMarketStateDetector(
		container.SecurityRepo,
		container.MarketHoursService,
		log,
	)

	// Event system (bus-based architecture)
	// EventBus provides pub/sub for system-wide events
	// EventManager wraps the bus with additional functionality
	container.EventBus = events.NewBus(log)
	container.EventManager = events.NewManager(container.EventBus, log)

	// Market status WebSocket client
	// Connects to Tradernet WebSocket for real-time market status updates
	// Publishes events to EventBus when market status changes
	container.MarketStatusWS = tradernet.NewMarketStatusWebSocket(
		"wss://wss.tradernet.com/",
		"", // Empty string for demo mode (SID not required)
		container.EventBus,
		log,
	)

	// Start WebSocket connection (non-blocking, will auto-retry)
	// Connection failures don't fail startup - reconnect loop handles retries
	if err := container.MarketStatusWS.Start(); err != nil {
		log.Warn().Err(err).Msg("Market status WebSocket connection failed, will auto-retry")
		// Don't fail startup - reconnect loop will handle it
	}

	// Settings service (needed for trade safety and other services)
	// Provides access to application settings with temperament-aware adjustments
	container.SettingsService = settings.NewService(container.SettingsRepo, log)

	// Exchange rate cache service (Tradernet + DB cache)
	// Primary: Fetches from Tradernet API
	// Secondary: Falls back to DB cache if API unavailable
	container.ExchangeRateCacheService = services.NewExchangeRateCacheService(
		container.CurrencyExchangeService, // Tradernet (primary)
		container.HistoryDBClient,         // DB cache (secondary)
		container.SettingsService,
		log,
	)

	// Price conversion service (converts native currency prices to EUR)
	// Converts prices from security's native currency to EUR for portfolio calculations
	container.PriceConversionService = services.NewPriceConversionService(
		container.CurrencyExchangeService,
		log,
	)

	// ==========================================
	// STEP 3: Initialize Cash Manager
	// ==========================================
	// Cash manager implements cash-as-balances architecture

	// Cash manager (cash-as-balances architecture)
	// Manages cash balances with dual-write to both CashRepo and PositionRepo
	// This implements domain.CashManager interface
	cashManager := cash_flows.NewCashManagerWithDualWrite(container.CashRepo, container.PositionRepo, log)
	container.CashManager = cashManager // Store as interface

	// ==========================================
	// STEP 4: Initialize Trading Services
	// ==========================================
	// Trading services handle trade validation, execution, and safety checks

	// Trade safety service with all validation layers
	// Validates trades against frequency limits, cooloff periods, market hours, etc.
	container.TradeSafetyService = trading.NewTradeSafetyService(
		container.TradeRepo,
		container.PositionRepo,
		container.SecurityRepo,
		container.SettingsService,
		container.MarketHoursService,
		log,
	)

	// Trading service
	// Orchestrates trading operations (validation, execution, event publishing)
	container.TradingService = trading.NewTradingService(
		container.TradeRepo,
		container.BrokerClient,
		container.TradeSafetyService,
		container.EventManager,
		log,
	)

	// Trade execution service - uses market orders for simplicity
	// Executes trades via broker API, updates positions, manages cash, publishes events
	container.TradeExecutionService = services.NewTradeExecutionService(
		container.BrokerClient,
		container.TradeRepo,
		container.PositionRepo,
		cashManager, // Use concrete type for now, will be interface later
		container.CurrencyExchangeService,
		container.EventManager,
		container.SettingsService,
		container.PlannerConfigRepo,
		container.HistoryDB.Conn(),
		container.SecurityRepo,
		container.MarketHoursService, // Market hours validation
		log,
	)

	// ==========================================
	// STEP 5: Initialize Universe Services
	// ==========================================
	// Universe services manage the investment universe (securities, historical data, symbol resolution)

	// Historical sync service (uses Tradernet as primary source for historical data)
	// Fetches historical prices from Tradernet API and stores in history.db
	// Stores raw data - filtering happens on read via HistoryDB's PriceFilter
	container.HistoricalSyncService = universe.NewHistoricalSyncService(
		container.BrokerClient, // Tradernet is now single source of truth
		container.SecurityRepo,
		container.HistoryDBClient,
		log,
	)

	// Symbol resolver
	// Resolves security identifiers (ISIN, symbol) to security objects
	container.SymbolResolver = universe.NewSymbolResolver(
		container.BrokerClient,
		container.SecurityRepo,
		log,
	)

	// Security setup service (scoreCalculator will be set later)
	// Auto-adds missing securities when referenced in trades/positions
	// scoreCalculator will be wired later after SecurityScorer is created
	container.SetupService = universe.NewSecuritySetupService(
		container.SymbolResolver,
		container.SecurityRepo,
		container.BrokerClient,
		container.HistoricalSyncService,
		container.EventManager,
		nil, // scoreCalculator - will be set later
		log,
	)

	// Security deletion service
	// Handles security deletion with cleanup of related data (positions, scores, history)
	container.SecurityDeletionService = universe.NewSecurityDeletionService(
		container.SecurityRepo,
		container.PositionRepo,
		container.ScoreRepo,
		container.HistoryDBClient,
		container.BrokerClient,
		log,
	)

	// Metadata sync service (batch + individual)
	// Syncs security metadata from broker API (supports batch operations to avoid 429 rate limits)
	// Used by both the scheduled batch job (3 AM) and work processor (individual retries)
	container.MetadataSyncService = universe.NewMetadataSyncService(
		container.SecurityRepo,
		container.BrokerClient,
		log,
	)

	// Scheduler for time-based jobs (robfig/cron)
	// Manages cron-based job execution with proper concurrency control
	container.Scheduler = scheduler.New(log)

	// Daily batch metadata sync job (runs at 3 AM)
	// Uses MetadataSyncService to sync all security metadata in a single batch API call
	metadataSyncJob := scheduler.NewMetadataSyncJob(container.MetadataSyncService, log)
	if err := container.Scheduler.AddJob("0 0 3 * * *", metadataSyncJob); err != nil {
		return fmt.Errorf("failed to register metadata sync job: %w", err)
	}

	// Create adapter for SecuritySetupService to match portfolio.SecuritySetupServiceInterface
	// This bridges the interface mismatch between universe and portfolio packages
	setupServiceAdapter := &securitySetupServiceAdapter{service: container.SetupService}

	// ==========================================
	// STEP 6: Initialize Portfolio Service
	// ==========================================
	// Portfolio service manages portfolio state and operations

	// Portfolio service (with SecuritySetupService adapter for auto-adding missing securities)
	// Manages portfolio state, positions, and provides portfolio-level operations
	// Auto-adds missing securities via SecuritySetupService adapter
	portfolioSecurityProvider := NewSecurityProviderAdapter(container.SecurityRepo)
	container.PortfolioService = portfolio.NewPortfolioService(
		container.PositionRepo,
		container.AllocRepo,
		cashManager, // Use concrete type
		container.UniverseDB.Conn(),
		portfolioSecurityProvider,
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
	// Cash flows services handle dividends, deposits, and cash flow processing

	// Dividend service implementation (adapter - uses existing dividendRepo)
	// Provides dividend-related operations (create, get, list)
	container.DividendService = cash_flows.NewDividendServiceImpl(container.DividendRepo, log)

	// Dividend creator
	// Creates dividend transactions from broker data
	container.DividendCreator = cash_flows.NewDividendCreator(container.DividendService, log)

	// Dividend yield calculator (uses ledger.db dividend transactions for yield calculation)
	// Calculates dividend yield based on dividend history and position values
	// Adapter for PositionRepo to implement PositionValueProvider interface
	positionValueAdapter := &positionValueProviderAdapter{positionRepo: container.PositionRepo}
	container.DividendYieldCalculator = dividends.NewDividendYieldCalculator(
		container.DividendRepo, // DividendRepository already implements DividendRepositoryInterface
		positionValueAdapter,
		log,
	)

	// Deposit processor (uses CashManager)
	// Processes deposit transactions and updates cash balances
	container.DepositProcessor = cash_flows.NewDepositProcessor(cashManager, log)

	// Tradernet adapter (adapts tradernet.Client to cash_flows.TradernetClient)
	// Bridges interface mismatch between broker client and cash flows service
	tradernetAdapter := cash_flows.NewTradernetAdapter(container.BrokerClient)

	// Cash flows sync job (created but not stored - used by service)
	// Syncs cash flows (deposits, dividends) from broker API
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
	// Orchestrates cash flow operations (sync, processing)
	container.CashFlowsService = cash_flows.NewCashFlowsService(syncJob, log)

	// ==========================================
	// STEP 8: Initialize Remaining Universe Services
	// ==========================================
	// Additional universe services (sync, tagging, scoring)

	// Sync service (scoreCalculator will be set later)
	// Syncs security data (prices, scores) from broker API
	// scoreCalculator will be wired later after SecurityScorer is created
	container.SyncService = universe.NewSyncService(
		container.SecurityRepo,
		container.HistoricalSyncService,
		nil, // scoreCalculator - will be set later
		container.BrokerClient,
		container.SetupService,
		container.PortfolioDB.Conn(),
		log,
	)

	// Universe service with cleanup coordination
	// Manages security universe with cleanup of orphaned data
	container.UniverseService = universe.NewUniverseService(
		container.SecurityRepo,
		container.HistoryDB,
		container.PortfolioDB,
		container.SyncService,
		log,
	)

	// Tag assigner for auto-tagging securities
	// Automatically assigns tags to securities based on their characteristics
	// (e.g., high-quality, value-opportunity, dividend-income)
	container.TagAssigner = universe.NewTagAssigner(log)
	// Wire settings service for temperament-aware tag thresholds
	// Tag thresholds adjust based on user's investment temperament
	tagSettingsAdapterInstance := &tagSettingsAdapter{service: container.SettingsService}
	container.TagAssigner.SetSettingsService(tagSettingsAdapterInstance)

	// Security scorer (used by handlers)
	// Calculates security scores (total score, component scores)
	container.SecurityScorer = scorers.NewSecurityScorer()

	// ==========================================
	// STEP 9: Initialize Planning Services
	// ==========================================
	// Planning services handle opportunity identification, sequence generation, and evaluation

	// Opportunities service (with unified calculators - tag-based optimization controlled by config)
	// Identifies trading opportunities using various calculators (profit-taking, averaging-down, etc.)
	// Tag-based filtering can be enabled/disabled via planner config
	// After removing domain.Security: universe.SecurityRepository directly implements opportunities.SecurityRepository
	tagFilter := opportunities.NewTagBasedFilter(container.SecurityRepo, log)
	container.OpportunitiesService = opportunities.NewService(tagFilter, container.SecurityRepo, log)

	// Risk builder (needed for sequences service)
	// Builds risk models (covariance matrices) for portfolio optimization
	// Use TradingSecurityProviderAdapter for ISIN lookups
	optimizationSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.RiskBuilder = optimization.NewRiskModelBuilder(container.HistoryDBClient, optimizationSecurityProvider, container.ConfigDB.Conn(), log)

	// Constraint enforcer for sequences service
	// Enforces per-security constraints (allow_buy, allow_sell) during sequence generation
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
	// Generates trade sequences (ordered lists of trades) for portfolio optimization
	container.SequencesService = sequences.NewService(log, container.RiskBuilder, sequencesEnforcer)

	// Evaluation service (4 workers)
	// Evaluates trade sequences using in-process worker pool
	// Calculates portfolio scores, transaction costs, and other metrics
	container.EvaluationService = planningevaluation.NewService(4, log)
	// Wire settings service for temperament-aware scoring
	// Evaluation weights adjust based on user's investment temperament
	container.EvaluationService.SetSettingsService(container.SettingsService)

	// Planner service (core planner)
	// Core planning logic: generates opportunities, creates sequences, evaluates them
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
	// High-level planning orchestration (wraps PlannerService)
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
	// Calculates a hash of the entire portfolio state (positions, scores, cash, settings, allocation)
	// Used to detect when portfolio state changes and trigger re-planning
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
	// Periodically checks state hash and emits PORTFOLIO_CHANGED events when state changes
	// NOTE: Not started here - will be started in main.go after all services initialized
	container.StateMonitor = planningstatemonitor.NewStateMonitor(
		container.StateHashService,
		container.EventManager,
		log,
	)
	log.Info().Msg("State monitor initialized (not started yet)")

	// Returns calculator - moved here to be available for OpportunityContextBuilder
	// Calculates expected returns for securities based on historical data
	// This is the SINGLE source of truth for expected return calculations (applies multipliers, regime adjustment, etc.)
	container.ReturnsCalc = optimization.NewReturnsCalculator(
		container.PortfolioDB.Conn(),
		optimizationSecurityProvider,
		log,
	)

	// Opportunity Context Builder - unified context building for opportunities, planning, and rebalancing
	// Builds comprehensive context objects for opportunity calculators, planning, and rebalancing
	// Context includes positions, securities, allocation, recent trades, scores, settings, regime, cash, prices
	// Uses ReturnsCalc for unified expected return calculations (same as optimizer)
	container.OpportunityContextBuilder = services.NewOpportunityContextBuilder(
		&ocbPositionRepoAdapter{repo: container.PositionRepo},
		&ocbSecurityRepoAdapter{repo: container.SecurityRepo},
		&ocbAllocationRepoAdapter{repo: container.AllocRepo},
		&ocbTradeRepoAdapter{repo: container.TradeRepo},
		&ocbScoresRepoAdapter{db: container.PortfolioDB.Conn()},
		&ocbSettingsRepoAdapter{repo: container.SettingsRepo, configRepo: container.PlannerConfigRepo},
		&ocbRegimeRepoAdapter{adapter: container.RegimeScoreProvider},
		&ocbCashManagerAdapter{manager: container.CashManager},
		&brokerPriceClientAdapter{client: container.BrokerClient},
		container.PriceConversionService,
		&ocbBrokerClientAdapter{client: container.BrokerClient},
		container.ReturnsCalc, // Unified expected returns calculator
		log,
	)
	log.Info().Msg("Opportunity context builder initialized")

	// ==========================================
	// STEP 10: Initialize Optimization Services
	// ==========================================
	// Optimization services handle portfolio optimization (HRP, Mean-Variance, Black-Litterman)

	// Constraints manager
	// Manages portfolio constraints (allocation limits, concentration limits, etc.)
	container.ConstraintsMgr = optimization.NewConstraintsManager(log)

	// Note: ReturnsCalc already initialized above (before OpportunityContextBuilder) for unified expected returns

	// Kelly Position Sizer
	// Calculates optimal position sizes using Kelly Criterion
	// Default parameters will be overridden by temperament settings
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
	// Kelly sizing adjusts based on user's risk tolerance and aggression
	kellySettingsAdapterInstance := &kellySettingsAdapter{service: container.SettingsService}
	container.KellySizer.SetSettingsService(kellySettingsAdapterInstance)

	// CVaR Calculator
	// Calculates Conditional Value at Risk (expected shortfall)
	container.CVaRCalculator = optimization.NewCVaRCalculator(
		container.RiskBuilder,
		container.RegimeDetector,
		log,
	)

	// View Generator (for Black-Litterman)
	// Generates market views for Black-Litterman optimization
	container.ViewGenerator = optimization.NewViewGenerator(log)

	// Black-Litterman Optimizer
	// Implements Black-Litterman portfolio optimization (combines market equilibrium with views)
	container.BlackLittermanOptimizer = optimization.NewBlackLittermanOptimizer(
		container.ViewGenerator,
		container.RiskBuilder,
		log,
	)

	// Optimizer service
	// Main portfolio optimization service (HRP, Mean-Variance, Black-Litterman)
	container.OptimizerService = optimization.NewOptimizerService(
		container.ConstraintsMgr,
		container.ReturnsCalc,
		container.RiskBuilder,
		log,
	)

	// Wire Kelly Sizer into OptimizerService
	// Optimizer uses Kelly sizing for position size recommendations
	container.OptimizerService.SetKellySizer(container.KellySizer)

	// Wire CVaR Calculator into OptimizerService
	// Optimizer uses CVaR for risk-adjusted optimization
	container.OptimizerService.SetCVaRCalculator(container.CVaRCalculator)

	// Wire Settings Service into OptimizerService (for CVaR threshold configuration)
	// CVaR thresholds adjust based on user's risk tolerance
	container.OptimizerService.SetSettingsService(container.SettingsService)

	// Wire Black-Litterman Optimizer into OptimizerService
	// Optimizer can use Black-Litterman for view-based optimization
	container.OptimizerService.SetBlackLittermanOptimizer(container.BlackLittermanOptimizer)

	// ==========================================
	// STEP 11: Initialize Calculation Cache and Analytics
	// ==========================================
	// Calculation cache stores expensive computation results (risk models, optimizer results)

	// Calculation cache (for technical indicators and optimizer results)
	// Caches expensive computation results (risk models, HRP allocations, MV allocations)
	// Reduces computation time for repeated calculations
	container.CalculationCache = calculations.NewCache(container.CalculationsDB.Conn())

	// Wire cache into RiskBuilder for optimizer caching
	// Risk models (covariance matrices) are expensive to compute - cache them
	container.RiskBuilder.SetCache(container.CalculationCache)

	// Wire cache into OptimizerService for HRP and MV caching
	// Optimizer results (HRP allocations, MV allocations) are cached
	container.OptimizerService.SetCache(container.CalculationCache)

	// Factor Exposure Tracker
	// Tracks portfolio exposure to various risk factors (sector, geography, etc.)
	container.FactorExposureTracker = analytics.NewFactorExposureTracker(log)

	// ==========================================
	// STEP 12: Initialize Rebalancing Services
	// ==========================================
	// Rebalancing services handle portfolio rebalancing and negative balance correction

	// Negative balance rebalancer
	// Handles emergency rebalancing when negative balances are detected
	// Sells positions to correct negative cash balances
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
	// Orchestrates portfolio rebalancing based on allocation targets and triggers
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
	// STEP 13: Initialize Ticker and Display Services
	// ==========================================
	// Display services handle LED ticker text generation and portfolio health visualization

	// Ticker content service (generates ticker text)
	// Generates scrolling text for LED display (portfolio value, cash, next actions)
	container.TickerContentService = ticker.NewTickerContentService(
		container.PortfolioDB.Conn(),
		container.ConfigDB.Conn(),
		container.CacheDB.Conn(),
		cashManager,
		log,
	)
	log.Info().Msg("Ticker content service initialized")

	// Health calculator (calculates portfolio health scores)
	// Calculates health scores for each security in the portfolio
	// Health scores are used for LED display visualization
	container.HealthCalculator = display.NewHealthCalculator(
		container.PortfolioDB.Conn(),
		container.HistoryDBClient,
		container.ConfigDB.Conn(),
		log,
	)
	log.Info().Msg("Health calculator initialized")

	// Health updater (periodically sends health scores to display)
	// Sends portfolio health data to LED display for animated visualization
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
	// Manages LED display modes: TEXT (ticker), HEALTH (animated visualization), STATS (pixel count)
	if displayManager != nil {
		container.ModeManager = display.NewModeManager(
			displayManager,
			container.HealthUpdater,
			container.TickerContentService,
			log,
		)
		log.Info().Msg("Display mode manager initialized")

		// Apply display mode from settings (if configured)
		// Display mode can be set via Settings UI
		if container.SettingsRepo != nil {
			if mode, err := container.SettingsRepo.Get("display_mode"); err == nil && mode != nil && *mode != "" {
				if err := container.ModeManager.SetMode(display.DisplayMode(*mode)); err != nil {
					log.Warn().Err(err).Str("mode", *mode).Msg("Failed to set display mode from settings, using default")
				} else {
					log.Info().Str("mode", *mode).Msg("Applied display mode from settings")
				}
			}
		}
	}

	// ==========================================
	// STEP 14: Initialize Adaptive Market Services
	// ==========================================
	// Adaptive market services handle market regime detection and adaptive behavior

	// Market index service for market-wide regime detection
	// Manages market indices (SPY, QQQ, etc.) for regime detection
	// Use TradingSecurityProviderAdapter for ISIN lookups
	marketIndexSecurityProvider := NewTradingSecurityProviderAdapter(container.SecurityRepo)
	container.MarketIndexService = market_regime.NewMarketIndexService(
		marketIndexSecurityProvider,
		container.HistoryDBClient,
		container.BrokerClient,
		log,
	)

	// Index repository for per-region market indices
	// Stores market index configuration (which indices to track per region)
	container.IndexRepository = market_regime.NewIndexRepository(container.ConfigDB.Conn(), log)

	// Index sync service - ensures indices exist in both config DB and universe DB
	// Syncs index definitions to both databases (idempotent operation)
	container.IndexSyncService = market_regime.NewIndexSyncService(
		container.SecurityRepo,
		container.OverrideRepo,
		container.ConfigDB.Conn(),
		log,
	)

	// Sync known indices to both databases (idempotent - safe to run on every startup)
	// This ensures indices are in market_indices (config) AND securities (universe) tables
	// Market regime detection needs indices in both places
	if err := container.IndexSyncService.SyncAll(); err != nil {
		log.Warn().Err(err).Msg("Failed to sync market indices to databases (will use fallback)")
		// Don't fail startup - fallback to hardcoded indices will work
	}

	// Sync historical prices for indices (needed for regime calculation)
	// This fetches price data from broker API for all PRICE indices
	// First run: fetches 10 years of data; subsequent runs: fetches 1 year of updates
	// Regime detection requires historical price data to calculate moving averages
	if container.HistoricalSyncService != nil {
		if err := container.IndexSyncService.SyncHistoricalPricesForIndices(container.HistoricalSyncService); err != nil {
			log.Warn().Err(err).Msg("Failed to sync historical prices for indices (regime calculation may be limited)")
			// Don't fail startup - regime detection will fall back to neutral scores
		}
	}

	// Regime persistence for smoothing and history
	// Stores regime history and provides smoothing to prevent regime oscillation
	container.RegimePersistence = market_regime.NewRegimePersistence(container.ConfigDB.Conn(), log)

	// Market regime detector
	// Detects market regime (bull, bear, sideways) based on index moving averages
	container.RegimeDetector = market_regime.NewMarketRegimeDetector(log)
	container.RegimeDetector.SetMarketIndexService(container.MarketIndexService)
	container.RegimeDetector.SetRegimePersistence(container.RegimePersistence)

	// Adaptive market service
	// Implements Adaptive Market Hypothesis - adjusts behavior based on market regime
	container.AdaptiveMarketService = adaptation.NewAdaptiveMarketService(
		container.RegimeDetector,
		nil, // performanceTracker - optional
		nil, // weightsCalculator - optional
		nil, // repository - optional
		log,
	)

	// Regime score provider adapter
	// Provides current regime score (0-1) for adaptive services
	container.RegimeScoreProvider = market_regime.NewRegimeScoreProviderAdapter(container.RegimePersistence)

	// Wire up adaptive services to integration points
	// OptimizerService uses adaptive service for regime-aware optimization
	container.OptimizerService.SetAdaptiveService(container.AdaptiveMarketService)
	container.OptimizerService.SetRegimeScoreProvider(container.RegimeScoreProvider)
	log.Info().Msg("Adaptive service wired to OptimizerService")

	// TagAssigner: adaptive quality gates
	// Quality gate thresholds adjust based on market regime
	// Create adapter to bridge type mismatch
	tagAssignerAdapter := &qualityGatesAdapter{service: container.AdaptiveMarketService}
	container.TagAssigner.SetAdaptiveService(tagAssignerAdapter)
	container.TagAssigner.SetRegimeScoreProvider(container.RegimeScoreProvider)
	log.Info().Msg("Adaptive service wired to TagAssigner")

	// SecurityScorer: adaptive weights and per-region regime scores
	// Scoring weights adjust based on market regime
	// AdaptiveMarketService implements scorers.AdaptiveWeightsProvider interface directly
	container.SecurityScorer.SetAdaptiveService(container.AdaptiveMarketService)
	container.SecurityScorer.SetRegimeScoreProvider(container.RegimeScoreProvider)
	log.Info().Msg("Adaptive service and regime score provider wired to SecurityScorer")

	// ==========================================
	// STEP 15: Initialize Reliability Services
	// ==========================================
	// Reliability services handle backups, health checks, and data integrity

	// Create all database references map for reliability services
	// Health services monitor database integrity and file size
	databases := map[string]*database.DB{
		"universe":  container.UniverseDB,
		"config":    container.ConfigDB,
		"ledger":    container.LedgerDB,
		"portfolio": container.PortfolioDB,
		"history":   container.HistoryDB,
		"cache":     container.CacheDB,
	}

	// Initialize health services for each database
	// Health services check database integrity, file size, and corruption
	dataDir := cfg.DataDir
	container.HealthServices = make(map[string]*reliability.DatabaseHealthService)
	container.HealthServices["universe"] = reliability.NewDatabaseHealthService(container.UniverseDB, "universe", dataDir+"/universe.db", log)
	container.HealthServices["config"] = reliability.NewDatabaseHealthService(container.ConfigDB, "config", dataDir+"/config.db", log)
	container.HealthServices["ledger"] = reliability.NewDatabaseHealthService(container.LedgerDB, "ledger", dataDir+"/ledger.db", log)
	container.HealthServices["portfolio"] = reliability.NewDatabaseHealthService(container.PortfolioDB, "portfolio", dataDir+"/portfolio.db", log)
	container.HealthServices["history"] = reliability.NewDatabaseHealthService(container.HistoryDB, "history", dataDir+"/history.db", log)
	container.HealthServices["cache"] = reliability.NewDatabaseHealthService(container.CacheDB, "cache", dataDir+"/cache.db", log)

	// Initialize backup service
	// Creates local backups of all databases
	backupDir := dataDir + "/backups"
	container.BackupService = reliability.NewBackupService(databases, dataDir, backupDir, log)

	// Initialize R2 cloud backup services (optional - only if credentials are configured)
	// R2 backup provides cloud storage for database backups
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
	// R2 backup is optional - system works without it
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
	// STEP 16: Initialize Concentration Alert Service
	// ==========================================
	// Concentration alert service detects portfolio concentration breaches

	container.ConcentrationAlertService = allocation.NewConcentrationAlertService(
		container.PortfolioDB.Conn(),
		log,
	)

	// ==========================================
	// STEP 17: Initialize Quantum Calculator
	// ==========================================
	// Quantum calculator provides quantum probability calculations for bubble/trap detection

	container.QuantumCalculator = quantum.NewQuantumProbabilityCalculator()

	// ==========================================
	// STEP 18: Initialize Callbacks (for jobs)
	// ==========================================
	// Callbacks are functions that jobs can call to trigger actions

	// Display ticker update callback (called by sync cycle)
	// Updates LED ticker text with current portfolio information
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
	// Triggers emergency rebalancing to correct negative cash balances
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

	// ==========================================
	// Note: IdleProcessor has been replaced by the Work Processor
	// See InitializeWork() in work.go for the new event-driven job system
	// Work Processor provides event-driven execution, dependency resolution, and market-aware scheduling

	log.Info().Msg("All services initialized")

	return nil
}

// qualityGatesAdapter adapts adaptation.AdaptiveMarketService to universe.AdaptiveQualityGatesProvider
type qualityGatesAdapter struct {
	service *adaptation.AdaptiveMarketService
}

func (a *qualityGatesAdapter) CalculateAdaptiveQualityGates(regimeScore float64) universe.QualityGateThresholdsProvider {
	thresholds := a.service.CalculateAdaptiveQualityGates(regimeScore)
	return thresholds // *adaptation.QualityGateThresholds implements the interface via GetStability/GetLongTerm
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
		Below52wHighThreshold:       params.Below52wHighThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityThresholds() universe.QualityThresholds {
	params := a.service.GetAdjustedQualityThresholds()
	return universe.QualityThresholds{
		HighQualityStability:           params.HighQualityStability,
		HighQualityLongTerm:            params.HighQualityLongTerm,
		StableStability:                params.StableStability,
		StableVolatilityMax:            params.StableVolatilityMax,
		StableConsistency:              params.StableConsistency,
		ConsistentGrowerConsistency:    params.ConsistentGrowerConsistency,
		ConsistentGrowerCAGR:           params.ConsistentGrowerCAGR,
		HighStabilityThreshold:         params.HighStabilityThreshold,
		ValueOpportunityScoreThreshold: params.ValueOpportunityScoreThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedTechnicalThresholds() universe.TechnicalThresholds {
	params := a.service.GetAdjustedTechnicalThresholds()
	return universe.TechnicalThresholds{
		RSIOversold:               params.RSIOversold,
		RSIOverbought:             params.RSIOverbought,
		RecoveryMomentumThreshold: params.RecoveryMomentumThreshold,
		RecoveryStabilityMin:      params.RecoveryStabilityMin,
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
		LowRiskVolatilityMax:        params.LowRiskVolatilityMax,
		LowRiskStabilityMin:         params.LowRiskStabilityMin,
		LowRiskDrawdownMax:          params.LowRiskDrawdownMax,
		MediumRiskVolatilityMin:     params.MediumRiskVolatilityMin,
		MediumRiskVolatilityMax:     params.MediumRiskVolatilityMax,
		MediumRiskStabilityMin:      params.MediumRiskStabilityMin,
		HighRiskVolatilityThreshold: params.HighRiskVolatilityThreshold,
		HighRiskStabilityThreshold:  params.HighRiskStabilityThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedBubbleTrapThresholds() universe.BubbleTrapThresholds {
	params := a.service.GetAdjustedBubbleTrapThresholds()
	return universe.BubbleTrapThresholds{
		BubbleCAGRThreshold:       params.BubbleCAGRThreshold,
		BubbleSharpeThreshold:     params.BubbleSharpeThreshold,
		BubbleVolatilityThreshold: params.BubbleVolatilityThreshold,
		BubbleStabilityThreshold:  params.BubbleStabilityThreshold,
		ValueTrapStability:        params.ValueTrapStability,
		ValueTrapLongTerm:         params.ValueTrapLongTerm,
		ValueTrapMomentum:         params.ValueTrapMomentum,
		ValueTrapVolatility:       params.ValueTrapVolatility,
		QuantumBubbleHighProb:     params.QuantumBubbleHighProb,
		QuantumBubbleWarningProb:  params.QuantumBubbleWarningProb,
		QuantumTrapHighProb:       params.QuantumTrapHighProb,
		QuantumTrapWarningProb:    params.QuantumTrapWarningProb,
		GrowthTagCAGRThreshold:    params.GrowthTagCAGRThreshold,
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
		BearSafeVolatility:       params.BearSafeVolatility,
		BearSafeStability:        params.BearSafeStability,
		BearSafeDrawdown:         params.BearSafeDrawdown,
		BullGrowthCAGR:           params.BullGrowthCAGR,
		BullGrowthStability:      params.BullGrowthStability,
		RegimeVolatileVolatility: params.RegimeVolatileVolatility,
		SidewaysValueStability:   params.SidewaysValueStability,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityGateParams() universe.QualityGateParams {
	params := a.service.GetAdjustedQualityGateParams()
	return universe.QualityGateParams{
		StabilityThreshold:             params.StabilityThreshold,
		LongTermThreshold:              params.LongTermThreshold,
		ExceptionalThreshold:           params.ExceptionalThreshold,
		AbsoluteMinCAGR:                params.AbsoluteMinCAGR,
		ExceptionalExcellenceThreshold: params.ExceptionalExcellenceThreshold,
		QualityValueStabilityMin:       params.QualityValueStabilityMin,
		QualityValueOpportunityMin:     params.QualityValueOpportunityMin,
		QualityValueLongTermMin:        params.QualityValueLongTermMin,
		DividendIncomeStabilityMin:     params.DividendIncomeStabilityMin,
		DividendIncomeScoreMin:         params.DividendIncomeScoreMin,
		DividendIncomeYieldMin:         params.DividendIncomeYieldMin,
		RiskAdjustedLongTermThreshold:  params.RiskAdjustedLongTermThreshold,
		RiskAdjustedSharpeThreshold:    params.RiskAdjustedSharpeThreshold,
		RiskAdjustedSortinoThreshold:   params.RiskAdjustedSortinoThreshold,
		RiskAdjustedVolatilityMax:      params.RiskAdjustedVolatilityMax,
		CompositeStabilityWeight:       params.CompositeStabilityWeight,
		CompositeLongTermWeight:        params.CompositeLongTermWeight,
		CompositeScoreMin:              params.CompositeScoreMin,
		CompositeStabilityFloor:        params.CompositeStabilityFloor,
		GrowthOpportunityCAGRMin:       params.GrowthOpportunityCAGRMin,
		GrowthOpportunityStabilityMin:  params.GrowthOpportunityStabilityMin,
		GrowthOpportunityVolatilityMax: params.GrowthOpportunityVolatilityMax,
		HighScoreThreshold:             params.HighScoreThreshold,
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

func (a *ocbAllocationRepoAdapter) GetGeographyTargets() (map[string]float64, error) {
	return a.repo.GetGeographyTargets()
}

func (a *ocbAllocationRepoAdapter) GetIndustryTargets() (map[string]float64, error) {
	return a.repo.GetIndustryTargets()
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
	stabilityScores := make(map[string]float64)
	if len(isinList) == 0 {
		return longTermScores, stabilityScores, nil
	}

	query := `SELECT isin, cagr_score, stability_score FROM scores WHERE isin != '' AND isin IS NOT NULL`
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
		var cagrScore, stabilityScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore, &stabilityScore); err != nil {
			continue
		}
		if !isinSet[isin] {
			continue
		}
		if cagrScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64))
			longTermScores[isin] = normalized
		}
		if stabilityScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, stabilityScore.Float64))
			stabilityScores[isin] = normalized
		}
	}
	return longTermScores, stabilityScores, nil
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

// positionValueProviderAdapter adapts PositionRepository to dividends.PositionValueProvider
type positionValueProviderAdapter struct {
	positionRepo *portfolio.PositionRepository
}

func (a *positionValueProviderAdapter) GetMarketValueByISIN(isin string) (float64, error) {
	if a.positionRepo == nil {
		return 0, fmt.Errorf("position repository not available")
	}
	position, err := a.positionRepo.GetByISIN(isin)
	if err != nil {
		return 0, err
	}
	if position == nil {
		return 0, fmt.Errorf("position not found for ISIN: %s", isin)
	}
	return position.MarketValueEUR, nil
}

// brokerPriceClientAdapter adapts domain.BrokerClient to services.PriceClient for OCB
type brokerPriceClientAdapter struct {
	client domain.BrokerClient
}

func (a *brokerPriceClientAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	// Extract symbols from map
	symbols := make([]string, 0, len(symbolMap))
	for symbol := range symbolMap {
		symbols = append(symbols, symbol)
	}

	// Get quotes from broker
	quotes, err := a.client.GetQuotes(symbols)
	if err != nil {
		return nil, fmt.Errorf("failed to get broker quotes: %w", err)
	}

	// Convert to price map
	prices := make(map[string]*float64)
	for symbol, quote := range quotes {
		if quote != nil && quote.Price > 0 {
			price := quote.Price
			prices[symbol] = &price
		}
	}

	return prices, nil
}
