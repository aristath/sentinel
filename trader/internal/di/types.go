// Package di provides dependency injection type definitions.
package di

import (
	"github.com/aristath/portfolioManager/internal/clients/tradernet"
	"github.com/aristath/portfolioManager/internal/clients/yahoo"
	"github.com/aristath/portfolioManager/internal/database"
	"github.com/aristath/portfolioManager/internal/domain"
	"github.com/aristath/portfolioManager/internal/events"
	"github.com/aristath/portfolioManager/internal/modules/adaptation"
	"github.com/aristath/portfolioManager/internal/modules/allocation"
	"github.com/aristath/portfolioManager/internal/modules/analytics"
	"github.com/aristath/portfolioManager/internal/modules/cash_flows"
	"github.com/aristath/portfolioManager/internal/modules/dividends"
	"github.com/aristath/portfolioManager/internal/modules/market_hours"
	"github.com/aristath/portfolioManager/internal/modules/opportunities"
	"github.com/aristath/portfolioManager/internal/modules/optimization"
	"github.com/aristath/portfolioManager/internal/modules/planning"
	planningevaluation "github.com/aristath/portfolioManager/internal/modules/planning/evaluation"
	planningplanner "github.com/aristath/portfolioManager/internal/modules/planning/planner"
	planningrepo "github.com/aristath/portfolioManager/internal/modules/planning/repository"
	"github.com/aristath/portfolioManager/internal/modules/portfolio"
	"github.com/aristath/portfolioManager/internal/modules/rebalancing"
	"github.com/aristath/portfolioManager/internal/modules/scoring/scorers"
	"github.com/aristath/portfolioManager/internal/modules/sequences"
	"github.com/aristath/portfolioManager/internal/modules/settings"
	"github.com/aristath/portfolioManager/internal/modules/trading"
	"github.com/aristath/portfolioManager/internal/modules/universe"
	"github.com/aristath/portfolioManager/internal/queue"
	"github.com/aristath/portfolioManager/internal/reliability"
	"github.com/aristath/portfolioManager/internal/scheduler"
	"github.com/aristath/portfolioManager/internal/services"
	"github.com/aristath/portfolioManager/internal/ticker"
)

// Container holds all dependencies for the application
// This is the single source of truth for all service instances
type Container struct {
	// Databases (7-database architecture)
	UniverseDB  *database.DB
	ConfigDB    *database.DB
	LedgerDB    *database.DB
	PortfolioDB *database.DB
	AgentsDB    *database.DB
	HistoryDB   *database.DB
	CacheDB     *database.DB

	// Clients
	TradernetClient *tradernet.Client
	YahooClient     *yahoo.NativeClient

	// Repositories
	PositionRepo       *portfolio.PositionRepository
	SecurityRepo       *universe.SecurityRepository
	ScoreRepo          *universe.ScoreRepository
	DividendRepo       *dividends.DividendRepository
	CashRepo           *cash_flows.CashRepository
	TradeRepo          *trading.TradeRepository
	AllocRepo          *allocation.Repository
	SettingsRepo       *settings.Repository
	CashFlowsRepo      *cash_flows.Repository
	RecommendationRepo *planning.RecommendationRepository
	PlannerConfigRepo  *planningrepo.ConfigRepository
	GroupingRepo       *allocation.GroupingRepository
	HistoryDBClient    *universe.HistoryDB

	// Services
	CurrencyExchangeService   *services.CurrencyExchangeService
	CashManager               domain.CashManager // Interface
	TradeSafetyService        *trading.TradeSafetyService
	TradingService            *trading.TradingService
	PortfolioService          *portfolio.PortfolioService
	CashFlowsService          *cash_flows.CashFlowsService
	UniverseService           *universe.UniverseService
	TagAssigner               *universe.TagAssigner
	TradeExecutionService     *services.TradeExecutionService
	SettingsService           *settings.Service
	MarketHoursService        *market_hours.MarketHoursService
	EventBus                  *events.Bus
	EventManager              *events.Manager
	TickerContentService      *ticker.TickerContentService
	QueueManager              *queue.Manager
	WorkerPool                *queue.WorkerPool
	TimeScheduler             *queue.Scheduler
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
	MarketIndexService        *portfolio.MarketIndexService
	RegimePersistence         *portfolio.RegimePersistence
	RegimeDetector            *portfolio.MarketRegimeDetector
	AdaptiveMarketService     *adaptation.AdaptiveMarketService
	RegimeScoreProvider       *portfolio.RegimeScoreProviderAdapter
	DividendService           *cash_flows.DividendServiceImpl
	DividendCreator           *cash_flows.DividendCreator
	DepositProcessor          *cash_flows.DepositProcessor
	HistoricalSyncService     *universe.HistoricalSyncService
	SyncService               *universe.SyncService
	SetupService              *universe.SecuritySetupService
	SymbolResolver            *universe.SymbolResolver
	ConcentrationAlertService *allocation.ConcentrationAlertService
	BackupService             *reliability.BackupService
	HealthServices            map[string]*reliability.DatabaseHealthService
	FactorExposureTracker     *analytics.FactorExposureTracker

	// Handlers (will be populated in handlers.go)
	// Note: Handlers are created per-route, so we don't store them in container
	// Instead, we provide factory methods that use container services

	// Callbacks (for jobs)
	UpdateDisplayTicker func() error
	EmergencyRebalance  func() error
}

// JobInstances holds references to all registered jobs for manual triggering
type JobInstances struct {
	// Original jobs
	HealthCheck       scheduler.Job
	SyncCycle         scheduler.Job
	DividendReinvest  scheduler.Job
	PlannerBatch      scheduler.Job
	EventBasedTrading scheduler.Job
	TagUpdate         scheduler.Job

	// Reliability jobs
	HistoryCleanup     scheduler.Job
	HourlyBackup       scheduler.Job
	DailyBackup        scheduler.Job
	DailyMaintenance   scheduler.Job
	WeeklyBackup       scheduler.Job
	WeeklyMaintenance  scheduler.Job
	MonthlyBackup      scheduler.Job
	MonthlyMaintenance scheduler.Job

	// Symbolic Regression jobs
	FormulaDiscovery scheduler.Job

	// Adaptive Market job
	AdaptiveMarketJob scheduler.Job
}
