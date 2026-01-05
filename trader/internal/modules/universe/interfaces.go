package universe

import (
	"database/sql"

	"github.com/aristath/arduino-trader/internal/clients/yahoo"
)

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
	GetBySymbol(symbol string) (*Security, error)             // Helper method - looks up ISIN first
	GetByISIN(isin string) (*Security, error)                 // Primary method
	Update(isin string, updates map[string]interface{}) error // Changed from symbol to ISIN
}

// YahooClientInterface defines the contract for Yahoo Finance client operations
// Used by SyncService to enable testing with mocks
type YahooClientInterface interface {
	GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error)
	GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error)
	GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error)
}

// YahooHistoricalClientInterface defines the contract for historical price operations
// Used by HistoricalSyncService to enable testing with mocks
type YahooHistoricalClientInterface interface {
	GetHistoricalPrices(symbol string, yahooSymbolOverride *string, period string) ([]yahoo.HistoricalPrice, error)
}

// YahooFullClientInterface combines all Yahoo Finance client interfaces
// This is used by services that need both sync and historical operations
type YahooFullClientInterface interface {
	YahooClientInterface
	YahooHistoricalClientInterface
}

// DBExecutor defines the contract for database execution operations
// Used by SyncService to enable testing with mocks
type DBExecutor interface {
	Exec(query string, args ...interface{}) (sql.Result, error)
}

// CurrencyExchangeServiceInterface defines the contract for currency exchange operations
// Used by UniverseHandlers to enable testing with mocks
// This interface avoids import cycles with the services package
type CurrencyExchangeServiceInterface interface {
	GetRate(fromCurrency, toCurrency string) (float64, error)
}
