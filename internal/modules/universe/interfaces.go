package universe

import (
	"database/sql"
	"time"
)

// ProgressReporter interface for progress reporting (avoids import cycle)
type ProgressReporter interface {
	Report(current, total int, message string)
}

// SyncServiceInterface defines the contract for sync service operations
// Used by UniverseService to enable testing with mocks
type SyncServiceInterface interface {
	SyncAllPrices() (int, error)
	SyncAllPricesWithReporter(reporter ProgressReporter) (int, error)
	SyncPricesForSymbols(symbolMap map[string]*string) (int, error)
}

// SecurityRepositoryInterface defines the contract for security repository operations
// Used by UniverseService to enable testing with mocks
type SecurityRepositoryInterface interface {
	// Core lookups
	GetBySymbol(symbol string) (*Security, error)
	GetByISIN(isin string) (*Security, error)
	GetByIdentifier(identifier string) (*Security, error)

	// Batch lookups
	GetAll() ([]Security, error)
	GetByISINs(isins []string) ([]Security, error)
	GetBySymbols(symbols []string) ([]Security, error)

	// Filtered queries
	GetTradable() ([]Security, error)
	GetByMarketCode(marketCode string) ([]Security, error)
	GetByGeography(geography string) ([]Security, error)
	GetByIndustry(industry string) ([]Security, error)
	GetByTags(tagIDs []string) ([]Security, error)
	GetPositionsByTags(positionSymbols []string, tagIDs []string) ([]Security, error)

	// Metadata queries (NEW - replace direct queries)
	GetDistinctGeographies() ([]string, error)
	GetDistinctIndustries() ([]string, error)
	GetDistinctExchanges() ([]string, error)
	GetGeographiesAndIndustries() (map[string][]string, error)
	GetSecuritiesForOptimization() ([]SecurityOptimizationData, error)
	GetSecuritiesForCharts() ([]SecurityChartData, error)

	// Symbol/ISIN conversion (NEW - replace 15+ direct queries)
	GetISINBySymbol(symbol string) (string, error)
	GetSymbolByISIN(isin string) (string, error)
	BatchGetISINsBySymbols(symbols []string) (map[string]string, error)

	// Existence checks (NEW - replace validation queries)
	Exists(isin string) (bool, error)
	ExistsBySymbol(symbol string) (bool, error)
	CountTradable() (int, error)

	// WithScores (joins with portfolio.db)
	GetWithScores(portfolioDB *sql.DB) ([]SecurityWithScore, error)

	// Write operations
	Create(security Security) error
	Update(isin string, updates map[string]interface{}) error
	Delete(isin string) error
	HardDelete(isin string) error

	// Tag operations
	SetTagsForSecurity(symbol string, tagIDs []string) error
	GetTagsForSecurity(symbol string) ([]string, error)
	GetTagsWithUpdateTimes(symbol string) (map[string]time.Time, error)
	UpdateSpecificTags(symbol string, tagIDs []string) error

	// Legacy methods (to be removed after refactoring)
	GetAllActive() ([]Security, error)
	GetAllActiveTradable() ([]Security, error)
}

// SecurityOptimizationData is the minimal data needed for portfolio optimization
type SecurityOptimizationData struct {
	Symbol             string  `json:"symbol"`
	ISIN               string  `json:"isin"`
	ProductType        string  `json:"product_type"`
	Geography          string  `json:"geography"`
	Industry           string  `json:"industry"`
	MinPortfolioTarget float64 `json:"min_portfolio_target"`
	MaxPortfolioTarget float64 `json:"max_portfolio_target"`
}

// SecurityChartData is the minimal data needed for chart generation
type SecurityChartData struct {
	Symbol string `json:"symbol"`
	ISIN   string `json:"isin"`
}

// SecurityProvider provides read-only access to securities (subset of SecurityRepositoryInterface)
// Used by other modules to avoid requiring write permissions
type SecurityProvider interface {
	GetByISIN(isin string) (*Security, error)
	GetBySymbol(symbol string) (*Security, error)
	GetByIdentifier(identifier string) (*Security, error)
	GetAll() ([]Security, error)
	GetByISINs(isins []string) ([]Security, error)
	GetBySymbols(symbols []string) ([]Security, error)
	GetTradable() ([]Security, error)
	GetByMarketCode(marketCode string) ([]Security, error)
	GetByGeography(geography string) ([]Security, error)
	GetByIndustry(industry string) ([]Security, error)
	GetByTags(tagIDs []string) ([]Security, error)
	GetDistinctGeographies() ([]string, error)
	GetDistinctIndustries() ([]string, error)
	GetGeographiesAndIndustries() (map[string][]string, error)
	GetSecuritiesForOptimization() ([]SecurityOptimizationData, error)
	GetSecuritiesForCharts() ([]SecurityChartData, error)
	GetISINBySymbol(symbol string) (string, error)
	GetSymbolByISIN(isin string) (string, error)
	BatchGetISINsBySymbols(symbols []string) (map[string]string, error)
	Exists(isin string) (bool, error)
	ExistsBySymbol(symbol string) (bool, error)
	CountTradable() (int, error)
	GetWithScores(portfolioDB *sql.DB) ([]SecurityWithScore, error)
}

// Compile-time check that SecurityRepository implements SecurityRepositoryInterface
var _ SecurityRepositoryInterface = (*SecurityRepository)(nil)

// SecurityDeletionServiceInterface defines the contract for hard deletion operations
type SecurityDeletionServiceInterface interface {
	// HardDelete permanently removes a security and all related data across databases
	// Returns error if security has open positions, pending orders, or does not exist
	HardDelete(isin string) error
}

// Compile-time check that SecurityDeletionService implements SecurityDeletionServiceInterface
var _ SecurityDeletionServiceInterface = (*SecurityDeletionService)(nil)

// DBExecutor defines the contract for database execution operations
// Used by SyncService to enable testing with mocks
type DBExecutor interface {
	Exec(query string, args ...interface{}) (sql.Result, error)
}

// Note: CurrencyExchangeServiceInterface has been moved to domain/interfaces.go
// It is now available as domain.CurrencyExchangeServiceInterface
