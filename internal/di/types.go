/**
 * Package di provides dependency injection type definitions.
 *
 * This package defines the Container type which holds all application dependencies.
 * The Container is the single source of truth for all service instances and is
 * passed to handlers for access to services.
 */
package di

import (
	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/aristath/sentinel/internal/clients/tradernet"
	"github.com/aristath/sentinel/internal/database"
	"github.com/aristath/sentinel/internal/deployment"
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/events"
	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/analytics"
	"github.com/aristath/sentinel/internal/modules/calculations"
	"github.com/aristath/sentinel/internal/modules/cash_flows"
	"github.com/aristath/sentinel/internal/modules/config"
	"github.com/aristath/sentinel/internal/modules/display"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/market_hours"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/planning"
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
	"github.com/aristath/sentinel/internal/services"
	"github.com/aristath/sentinel/internal/ticker"
)

/**
 * Container holds all dependencies for the application.
 *
 * This is the single source of truth for all service instances.
 * The container is created by Wire() and passed to handlers for access to services.
 *
 * Architecture:
 * - Databases: 8-database architecture (universe, config, ledger, portfolio, history, cache, client_data, calculations)
 * - Clients: External API clients (broker, market status WebSocket)
 * - Repositories: Data access layer (positions, securities, scores, trades, etc.)
 * - Services: Business logic layer (trading, portfolio, planning, optimization, etc.)
 * - Work Components: Background job processor with event-driven execution
 * - Callbacks: Functions for jobs to trigger display updates and emergency actions
 *
 * All dependencies are injected via constructor injection following clean architecture principles.
 */
type Container struct {
	// Databases (8-database architecture)
	// Each database uses SQLite with WAL mode and profile-specific PRAGMAs for optimal performance
	UniverseDB     *database.DB // Investment universe (securities, groups)
	ConfigDB       *database.DB // Application configuration (settings, allocation targets)
	LedgerDB       *database.DB // Immutable financial audit trail (trades, cash flows, dividends)
	PortfolioDB    *database.DB // Current portfolio state (positions, scores, metrics, snapshots)
	HistoryDB      *database.DB // Historical time-series data (prices, rates, cleanup tracking)
	CacheDB        *database.DB // Ephemeral operational data (job history)
	ClientDataDB   *database.DB // Cache for exchange rates and current prices
	CalculationsDB *database.DB // Calculation cache (technical indicators, optimizer results)

	// Clients - External API integrations
	BrokerClient   domain.BrokerClient              // Broker API client (Tradernet adapter)
	MarketStatusWS *tradernet.MarketStatusWebSocket // Market status WebSocket for real-time updates

	// Repositories - Data access layer
	// Repositories abstract database access and provide clean interfaces for services
	PositionRepo       *portfolio.PositionRepository              // Portfolio positions
	SecurityRepo       *universe.SecurityRepository               // Investment universe securities
	ScoreRepo          *universe.ScoreRepository                  // Security scores and metrics
	OverrideRepo       *universe.OverrideRepository               // Security overrides (user-configurable fields)
	DividendRepo       *dividends.DividendRepository              // Dividend transactions
	CashRepo           *cash_flows.CashRepository                 // Cash balances
	TradeRepo          *trading.TradeRepository                   // Trade transactions
	AllocRepo          *allocation.Repository                     // Allocation targets (geography, industry)
	SettingsRepo       *settings.Repository                       // Application settings
	MarketIndexRepo    *config.MarketIndexRepository              // Market indices configuration
	CashFlowsRepo      *cash_flows.Repository                     // Cash flow transactions
	RecommendationRepo planning.RecommendationRepositoryInterface // Planning recommendations (interface - can be DB or in-memory)
	PlannerConfigRepo  planningrepo.ConfigRepositoryInterface     // Planner configuration (with settings overrides)
	PlannerRepo        planningrepo.PlannerRepositoryInterface    // Planner sequences/evaluations (interface - can be DB or in-memory)
	HistoryDBClient    universe.HistoryDBInterface                // Historical price data with read-time filtering
	ClientDataRepo     *clientdata.Repository                     // Client-specific symbol mappings and cached data

	// Services - Business logic layer
	// Services implement business logic and coordinate between repositories and domain models
	CurrencyExchangeService   *services.CurrencyExchangeService             // Currency exchange rate fetching
	ExchangeRateCacheService  *services.ExchangeRateCacheService            // Exchange rate caching (Tradernet + DB)
	PriceConversionService    *services.PriceConversionService              // Price conversion to EUR
	DividendYieldCalculator   *dividends.DividendYieldCalculator            // Dividend yield calculations
	CashManager               domain.CashManager                            // Cash balance management (interface)
	TradeSafetyService        *trading.TradeSafetyService                   // Trade validation and safety checks
	TradingService            *trading.TradingService                       // Trading operations
	PortfolioService          *portfolio.PortfolioService                   // Portfolio management
	CashFlowsService          *cash_flows.CashFlowsService                  // Cash flow processing
	UniverseService           *universe.UniverseService                     // Security universe management
	SecurityService           *services.SecurityService                     // Complete security data loading (all sources)
	TagAssigner               *universe.TagAssigner                         // Auto-tagging securities
	TradeExecutionService     *services.TradeExecutionService               // Trade execution (broker integration)
	SettingsService           *settings.Service                             // Settings management
	MarketHoursService        *market_hours.MarketHoursService              // Market hours and holidays
	MarketStateDetector       *market_regime.MarketStateDetector            // Market state detection (for scheduling)
	EventBus                  *events.Bus                                   // Event bus for pub/sub
	EventManager              *events.Manager                               // Event manager (wraps bus)
	TickerContentService      *ticker.TickerContentService                  // LED ticker text generation
	HealthCalculator          *display.HealthCalculator                     // Portfolio health score calculation
	HealthUpdater             *display.HealthUpdater                        // Periodic health score updates to display
	ModeManager               *display.ModeManager                          // Display mode switching
	NegativeBalanceRebalancer *rebalancing.NegativeBalanceRebalancer        // Emergency rebalancing
	OpportunitiesService      *opportunities.Service                        // Trading opportunity identification
	RiskBuilder               *optimization.RiskModelBuilder                // Risk model construction
	ConstraintsMgr            *optimization.ConstraintsManager              // Portfolio constraints management
	ReturnsCalc               *optimization.ReturnsCalculator               // Expected returns calculation
	KellySizer                *optimization.KellyPositionSizer              // Kelly criterion position sizing
	CVaRCalculator            *optimization.CVaRCalculator                  // Conditional Value at Risk calculation
	BlackLittermanOptimizer   *optimization.BlackLittermanOptimizer         // Black-Litterman optimization
	ViewGenerator             *optimization.ViewGenerator                   // Market views generation
	OptimizerService          *optimization.OptimizerService                // Portfolio optimization (HRP, MV, BL)
	OptimizerWeightsService   *optimization.OptimizerWeightsService         // Optimizer weights calculation service
	SequencesService          *sequences.Service                            // Trade sequence generation
	EvaluationService         *planningevaluation.Service                   // Sequence evaluation (worker pool)
	PlannerService            *planningplanner.Planner                      // Core planner (sequence generation)
	RebalancingService        *rebalancing.Service                          // Rebalancing logic
	SecurityScorer            *scorers.SecurityScorer                       // Security scoring
	MarketIndexService        *market_regime.MarketIndexService             // Market index management
	IndexRepository           *market_regime.IndexRepository                // Market index persistence
	IndexSyncService          *market_regime.IndexSyncService               // Index synchronization
	RegimePersistence         *market_regime.RegimePersistence              // Regime history and smoothing
	RegimeDetector            *market_regime.MarketRegimeDetector           // Market regime detection
	AdaptiveMarketService     *adaptation.AdaptiveMarketService             // Adaptive Market Hypothesis
	RegimeScoreProvider       *market_regime.RegimeScoreProviderAdapter     // Regime score provider
	DividendService           *cash_flows.DividendServiceImpl               // Dividend service implementation
	DividendCreator           *cash_flows.DividendCreator                   // Dividend creation
	DepositProcessor          *cash_flows.DepositProcessor                  // Deposit processing
	HistoricalSyncService     *universe.HistoricalSyncService               // Historical price synchronization
	SyncService               *universe.SyncService                         // Security synchronization
	SetupService              *universe.SecuritySetupService                // Security setup (auto-add missing)
	SecurityDeletionService   *universe.SecurityDeletionService             // Security deletion
	MetadataSyncService       *universe.MetadataSyncService                 // Security metadata synchronization (batch + individual)
	SymbolResolver            *universe.SymbolResolver                      // Symbol resolution (ISIN, symbol)
	ConcentrationAlertService *allocation.ConcentrationAlertService         // Portfolio concentration alerts
	BackupService             *reliability.BackupService                    // Local database backups
	HealthServices            map[string]*reliability.DatabaseHealthService // Database health checks
	FactorExposureTracker     *analytics.FactorExposureTracker              // Factor exposure analytics
	StateHashService          *planninghash.StateHashService                // Unified state hash calculation
	StateMonitor              *planningstatemonitor.StateMonitor            // State change monitoring
	R2Client                  *reliability.R2Client                         // Cloudflare R2 client (optional)
	R2BackupService           *reliability.R2BackupService                  // R2 cloud backup service (optional)
	RestoreService            *reliability.RestoreService                   // Database restore service
	QuantumCalculator         *quantum.QuantumProbabilityCalculator         // Quantum probability calculations
	OpportunityContextBuilder *services.OpportunityContextBuilder           // Opportunity context building
	CalculationCache          *calculations.Cache                           // Calculation result caching
	DeploymentManager         *deployment.Manager                           // Auto-deployment manager (optional)

	// Work Processor - Background job system
	// Replaces IdleProcessor and queue-based jobs with event-driven execution
	WorkComponents *WorkComponents

	// Handlers - HTTP request handlers
	// Note: Handlers are created per-route, so we don't store them in container.
	// Instead, we provide factory methods that use container services.

	// Callbacks - Functions for jobs to trigger actions
	UpdateDisplayTicker func() error // Updates LED ticker text (called by sync cycle)
	EmergencyRebalance  func() error // Emergency rebalancing (called when negative balance detected)
}
