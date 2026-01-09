package scheduler

import (
	"github.com/aristath/sentinel/internal/events"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// UniverseServiceInterface defines the contract for universe service operations
// Used by scheduler to enable testing with mocks
type UniverseServiceInterface interface {
	SyncPrices() error
}

// BalanceServiceInterface defines the contract for balance service operations
// Used by scheduler to enable testing with mocks
type BalanceServiceInterface interface {
	GetAllCurrencies() ([]string, error)
	GetTotalByCurrency(currency string) (float64, error)
}

// EventManagerInterface defines the contract for event emission
type EventManagerInterface interface {
	Emit(eventType events.EventType, module string, data map[string]interface{})
	EmitTyped(eventType events.EventType, module string, data events.EventData)
}

// TradingServiceInterface defines the contract for trading service operations
// Used by scheduler to enable testing with mocks
type TradingServiceInterface interface {
	SyncFromTradernet() error
}

// CashFlowsServiceInterface defines the contract for cash flows service operations
// Used by scheduler to enable testing with mocks
type CashFlowsServiceInterface interface {
	SyncFromTradernet() error
}

// PortfolioServiceInterface defines the contract for portfolio service operations
// Used by scheduler to enable testing with mocks
type PortfolioServiceInterface interface {
	SyncFromTradernet() error
}

// DisplayManagerInterface defines the contract for display manager operations
// Used by scheduler to enable testing with mocks
type DisplayManagerInterface interface {
	UpdateTicker() error
}

// PositionRepositoryInterface defines the contract for position repository operations
// Used by scheduler to enable testing with mocks
type PositionRepositoryInterface interface {
	GetAll() ([]interface{}, error) // Returns []portfolio.Position but using interface{} to avoid import cycle
}

// SecurityRepositoryInterface defines the contract for security repository operations
// Used by scheduler to enable testing with mocks
type SecurityRepositoryInterface interface {
	GetAllActive() ([]interface{}, error) // Returns []universe.Security but using interface{} to avoid import cycle
}

// AllocationRepositoryInterface defines the contract for allocation repository operations
// Used by scheduler to enable testing with mocks
type AllocationRepositoryInterface interface {
	GetAll() (map[string]float64, error)
}

// GroupingRepositoryInterface defines the contract for country/industry grouping operations
// Used by scheduler to enable testing with mocks
type GroupingRepositoryInterface interface {
	GetCountryGroups() (map[string][]string, error)  // Returns map: group_name -> [country_names]
	GetIndustryGroups() (map[string][]string, error) // Returns map: group_name -> [industry_names]
}

// CashManagerInterface defines the contract for cash manager operations
// Used by scheduler to enable testing with mocks
type CashManagerInterface interface {
	GetAllCashBalances() (map[string]float64, error)
}

// TradernetClientInterfaceForJobs defines the contract for Tradernet client operations for jobs
// Used by scheduler to enable testing with mocks
type TradernetClientInterfaceForJobs interface {
	GetPendingOrders() ([]interface{}, error) // Returns pending orders
}

// OptimizerServiceInterface defines the contract for optimizer service operations
// Used by scheduler to enable testing with mocks
type OptimizerServiceInterface interface {
	Optimize(state interface{}, settings interface{}) (interface{}, error) // Returns optimization result
}

// PriceConversionServiceInterface defines the contract for price conversion operations
// Used by scheduler to enable testing with mocks
type PriceConversionServiceInterface interface {
	ConvertPricesToEUR(prices map[string]float64, securities []universe.Security) map[string]float64
}

// OpportunitiesServiceInterface defines the contract for opportunities service operations
// Used by scheduler to enable testing with mocks
type OpportunitiesServiceInterface interface {
	IdentifyOpportunities(ctx interface{}, config interface{}) (interface{}, error) // Returns OpportunitiesByCategory
}

// SequencesServiceInterface defines the contract for sequences service operations
// Used by scheduler to enable testing with mocks
type SequencesServiceInterface interface {
	GenerateSequences(opportunities interface{}, config interface{}) ([]interface{}, error) // Returns []ActionSequence
}

// EvaluationServiceInterface defines the contract for evaluation service operations
// Used by scheduler to enable testing with mocks
type EvaluationServiceInterface interface {
	EvaluateBatch(sequences []interface{}, portfolioHash string) ([]interface{}, error) // Returns evaluated sequences
}

// PlannerServiceInterface defines the contract for planner service operations
// Used by scheduler to enable testing with mocks
type PlannerServiceInterface interface {
	CreatePlan(ctx interface{}, config interface{}) (interface{}, error) // Returns HolisticPlan
}

// RecommendationRepositoryInterface defines the contract for recommendation repository operations
// Used by scheduler to enable testing with mocks
type RecommendationRepositoryInterface interface {
	StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error
}

// PriceClientInterface defines the contract for price fetching operations
// Used by scheduler to enable testing with mocks
type PriceClientInterface interface {
	GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error)
}

// ConfigRepositoryInterface defines the contract for planner configuration repository operations
// Used by scheduler to enable testing with mocks
type ConfigRepositoryInterface interface {
	GetDefaultConfig() (interface{}, error) // Returns *planningdomain.PlannerConfiguration
}

// ScoresRepositoryInterface defines the contract for scores database operations
// Used by scheduler to enable testing with mocks
type ScoresRepositoryInterface interface {
	GetCAGRs(isinList []string) (map[string]float64, error)                                                 // Returns map keyed by ISIN and symbol
	GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error)                     // Returns longTermScores, fundamentalsScores
	GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) // Returns opportunityScores, momentumScores, volatility
	GetTotalScores(isinList []string) (map[string]float64, error)                                           // Returns total scores keyed by ISIN
}

// SettingsRepositoryInterface defines the contract for settings database operations
// Used by scheduler to enable testing with mocks
type SettingsRepositoryInterface interface {
	GetTargetReturnSettings() (float64, float64, error) // Returns targetReturn, thresholdPct
	GetVirtualTestCash() (float64, error)               // Returns virtual test cash amount, 0 if not in research mode
}

// RegimeRepositoryInterface defines the contract for regime score operations
// Used by scheduler to enable testing with mocks
type RegimeRepositoryInterface interface {
	GetCurrentRegimeScore() (float64, error) // Returns current regime score
}

// DividendRepositoryInterface defines the contract for dividend repository operations
// Used by scheduler to enable testing with mocks
type DividendRepositoryInterface interface {
	GetUnreinvestedDividends(minAmountEUR float64) ([]interface{}, error) // Returns []dividends.DividendRecord
	SetPendingBonus(dividendID int, bonus float64) error
	MarkReinvested(dividendID int, quantity int) error
}

// SecurityRepositoryForDividendsInterface defines the contract for security repository operations for dividends
// Used by scheduler to enable testing with mocks
type SecurityRepositoryForDividendsInterface interface {
	GetBySymbol(symbol string) (*SecurityForDividends, error)
}

// SecurityForDividends is a simplified interface for security data
type SecurityForDividends struct {
	Symbol      string
	YahooSymbol string
	Name        string
	Currency    string
	MinLot      int
}

// YahooClientForDividendsInterface defines the contract for Yahoo client operations for dividends
// Used by scheduler to enable testing with mocks
type YahooClientForDividendsInterface interface {
	GetCurrentPrice(symbol string, yahooSymbolOverride *string, maxRetries int) (*float64, error)
	GetFundamentalData(symbol string, yahooSymbolOverride *string) (*FundamentalDataForDividends, error)
}

// FundamentalDataForDividends is a simplified interface for fundamental data
type FundamentalDataForDividends struct {
	DividendYield *float64
}

// TradeExecutionServiceInterface defines the contract for trade execution service operations
// Used by scheduler to enable testing with mocks
type TradeExecutionServiceInterface interface {
	ExecuteTrades(recommendations []TradeRecommendationForDividends) []TradeResultForDividends
}

// TradeRecommendationForDividends is a simplified trade recommendation
type TradeRecommendationForDividends struct {
	Symbol         string
	Side           string
	Quantity       float64
	EstimatedPrice float64
	Currency       string
	Reason         string
}

// TradeResultForDividends is the result of executing a trade
type TradeResultForDividends struct {
	Symbol string
	Status string // "success", "blocked", "error"
	Error  *string
}
