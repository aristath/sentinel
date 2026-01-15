// Package di provides dependency injection type definitions.
package di

import (
	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/aristath/sentinel/internal/clients/tradernet"
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
	"github.com/aristath/sentinel/internal/scheduler"
	"github.com/aristath/sentinel/internal/services"
	"github.com/aristath/sentinel/internal/ticker"
)

// Container holds all dependencies for the application
// This is the single source of truth for all service instances
type Container struct {
	// Databases (8-database architecture)
	UniverseDB     *database.DB
	ConfigDB       *database.DB
	LedgerDB       *database.DB
	PortfolioDB    *database.DB
	HistoryDB      *database.DB
	CacheDB        *database.DB
	ClientDataDB   *database.DB
	CalculationsDB *database.DB

	// Clients
	BrokerClient   domain.BrokerClient
	MarketStatusWS *tradernet.MarketStatusWebSocket

	// Repositories
	PositionRepo       *portfolio.PositionRepository
	SecurityRepo       *universe.SecurityRepository
	ScoreRepo          *universe.ScoreRepository
	OverrideRepo       *universe.OverrideRepository
	DividendRepo       *dividends.DividendRepository
	CashRepo           *cash_flows.CashRepository
	TradeRepo          *trading.TradeRepository
	AllocRepo          *allocation.Repository
	SettingsRepo       *settings.Repository
	CashFlowsRepo      *cash_flows.Repository
	RecommendationRepo planning.RecommendationRepositoryInterface // Interface - can be DB or in-memory
	PlannerConfigRepo  *planningrepo.ConfigRepository
	PlannerRepo        planningrepo.PlannerRepositoryInterface // Interface - can be DB or in-memory
	HistoryDBClient    universe.HistoryDBInterface
	ClientDataRepo     *clientdata.Repository

	// Services
	CurrencyExchangeService  *services.CurrencyExchangeService
	ExchangeRateCacheService *services.ExchangeRateCacheService
	PriceConversionService   *services.PriceConversionService
	DividendYieldCalculator  *dividends.DividendYieldCalculator
	CashManager              domain.CashManager // Interface
	TradeSafetyService       *trading.TradeSafetyService
	TradingService           *trading.TradingService
	PortfolioService         *portfolio.PortfolioService
	CashFlowsService         *cash_flows.CashFlowsService
	UniverseService          *universe.UniverseService
	TagAssigner              *universe.TagAssigner
	TradeExecutionService    *services.TradeExecutionService
	SettingsService          *settings.Service
	MarketHoursService       *market_hours.MarketHoursService
	MarketStateDetector      *market_regime.MarketStateDetector
	EventBus                 *events.Bus
	EventManager             *events.Manager
	TickerContentService     *ticker.TickerContentService
	HealthCalculator         *display.HealthCalculator
	HealthUpdater            *display.HealthUpdater
	ModeManager              *display.ModeManager
	QueueManager             *queue.Manager
	WorkerPool               *queue.WorkerPool
	// NOTE: TimeScheduler removed - Work Processor handles all automatic scheduling
	JobHistory                *queue.History
	JobRegistry               *queue.Registry
	NegativeBalanceRebalancer *rebalancing.NegativeBalanceRebalancer
	OpportunitiesService      *opportunities.Service
	RiskBuilder               *optimization.RiskModelBuilder
	ConstraintsMgr            *optimization.ConstraintsManager
	ReturnsCalc               *optimization.ReturnsCalculator
	KellySizer                *optimization.KellyPositionSizer
	CVaRCalculator            *optimization.CVaRCalculator
	BlackLittermanOptimizer   *optimization.BlackLittermanOptimizer
	ViewGenerator             *optimization.ViewGenerator
	OptimizerService          *optimization.OptimizerService
	SequencesService          *sequences.Service
	EvaluationService         *planningevaluation.Service
	PlannerService            *planningplanner.Planner
	PlanningService           *planning.Service
	RebalancingService        *rebalancing.Service
	SecurityScorer            *scorers.SecurityScorer
	MarketIndexService        *market_regime.MarketIndexService
	IndexRepository           *market_regime.IndexRepository
	IndexSyncService          *market_regime.IndexSyncService
	RegimePersistence         *market_regime.RegimePersistence
	RegimeDetector            *market_regime.MarketRegimeDetector
	AdaptiveMarketService     *adaptation.AdaptiveMarketService
	RegimeScoreProvider       *market_regime.RegimeScoreProviderAdapter
	DividendService           *cash_flows.DividendServiceImpl
	DividendCreator           *cash_flows.DividendCreator
	DepositProcessor          *cash_flows.DepositProcessor
	HistoricalSyncService     *universe.HistoricalSyncService
	SyncService               *universe.SyncService
	SetupService              *universe.SecuritySetupService
	SecurityDeletionService   *universe.SecurityDeletionService
	SymbolResolver            *universe.SymbolResolver
	ConcentrationAlertService *allocation.ConcentrationAlertService
	BackupService             *reliability.BackupService
	HealthServices            map[string]*reliability.DatabaseHealthService
	FactorExposureTracker     *analytics.FactorExposureTracker
	StateHashService          *planninghash.StateHashService
	StateMonitor              *planningstatemonitor.StateMonitor
	R2Client                  *reliability.R2Client
	R2BackupService           *reliability.R2BackupService
	RestoreService            *reliability.RestoreService
	QuantumCalculator         *quantum.QuantumProbabilityCalculator
	OpportunityContextBuilder *services.OpportunityContextBuilder
	CalculationCache          *calculations.Cache

	// Work Processor (replaces IdleProcessor and queue-based jobs)
	WorkComponents *WorkComponents

	// Handlers (will be populated in handlers.go)
	// Note: Handlers are created per-route, so we don't store them in container
	// Instead, we provide factory methods that use container services

	// Callbacks (for jobs)
	UpdateDisplayTicker func() error
	EmergencyRebalance  func() error
}

// JobInstances holds references to all registered jobs for manual triggering
// NOTE: Composite jobs (SyncCycle, PlannerBatch) removed - orchestration handled by Work Processor
type JobInstances struct {
	HealthCheck       scheduler.Job
	DividendReinvest  scheduler.Job
	EventBasedTrading scheduler.Job
	TagUpdate         scheduler.Job

	// Individual sync jobs
	SyncTrades            scheduler.Job
	SyncCashFlows         scheduler.Job
	SyncPortfolio         scheduler.Job
	SyncPrices            scheduler.Job
	SyncExchangeRates     scheduler.Job
	CheckNegativeBalances scheduler.Job
	UpdateDisplayTicker   scheduler.Job
	RetryTrades           scheduler.Job

	// Individual planning jobs
	GeneratePortfolioHash   scheduler.Job
	GetOptimizerWeights     scheduler.Job
	BuildOpportunityContext scheduler.Job
	CreateTradePlan         scheduler.Job
	StoreRecommendations    scheduler.Job

	// Individual dividend jobs
	GetUnreinvestedDividends      scheduler.Job
	GroupDividendsBySymbol        scheduler.Job
	CheckDividendYields           scheduler.Job
	CreateDividendRecommendations scheduler.Job
	SetPendingBonuses             scheduler.Job
	ExecuteDividendTrades         scheduler.Job

	// Individual health check jobs
	CheckCoreDatabases    scheduler.Job
	CheckHistoryDatabases scheduler.Job
	CheckWALCheckpoints   scheduler.Job

	// Reliability jobs
	HistoryCleanup     scheduler.Job
	RecommendationGC   scheduler.Job
	ClientDataCleanup  scheduler.Job
	HourlyBackup       scheduler.Job
	DailyBackup        scheduler.Job
	DailyMaintenance   scheduler.Job
	WeeklyBackup       scheduler.Job
	WeeklyMaintenance  scheduler.Job
	MonthlyBackup      scheduler.Job
	MonthlyMaintenance scheduler.Job

	// R2 Cloud Backup jobs
	R2Backup         scheduler.Job
	R2BackupRotation scheduler.Job

	// Calculation cleanup job
	CalculationCleanup scheduler.Job

	// Symbolic Regression jobs
	FormulaDiscovery scheduler.Job

	// Adaptive Market job
	AdaptiveMarketJob scheduler.Job

	// Deployment job
	Deployment scheduler.Job

	// Tradernet metadata sync job
	TradernetMetadataSync scheduler.Job
}
