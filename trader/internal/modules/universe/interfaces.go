package universe

import "database/sql"

// SyncServiceInterface defines the contract for sync service operations
// Used by UniverseService to enable testing with mocks
type SyncServiceInterface interface {
	SyncAllPrices() (int, error)
	SyncPricesForSymbols(symbolMap map[string]*string) (int, error)
}

// SecurityRepositoryInterface defines the contract for security repository operations
// Used by UniverseService to enable testing with mocks
type SecurityRepositoryInterface interface {
	GetGroupedByExchange() (map[string][]Security, error)
	GetAllActive() ([]Security, error)
	Update(symbol string, updates map[string]interface{}) error
}

// YahooClientInterface defines the contract for Yahoo Finance client operations
// Used by SyncService to enable testing with mocks
type YahooClientInterface interface {
	GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error)
	GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error)
	GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error)
}

// DBExecutor defines the contract for database execution operations
// Used by SyncService to enable testing with mocks
type DBExecutor interface {
	Exec(query string, args ...interface{}) (sql.Result, error)
}
