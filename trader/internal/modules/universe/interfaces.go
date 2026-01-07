package universe

import (
	"database/sql"
	"time"

	"github.com/aristath/sentinel/internal/clients/yahoo"
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
	// GetBySymbol returns a security by symbol
	GetBySymbol(symbol string) (*Security, error)

	// GetByISIN returns a security by ISIN
	GetByISIN(isin string) (*Security, error)

	// GetByIdentifier returns a security by symbol or ISIN (smart lookup)
	GetByIdentifier(identifier string) (*Security, error)

	// GetAllActive returns all active securities
	GetAllActive() ([]Security, error)

	// GetDistinctExchanges returns all distinct exchange names
	GetDistinctExchanges() ([]string, error)

	// GetAllActiveTradable returns all active and tradable securities
	GetAllActiveTradable() ([]Security, error)

	// GetAll returns all securities (active and inactive)
	GetAll() ([]Security, error)

	// Create creates a new security
	Create(security Security) error

	// Update updates a security by ISIN
	Update(isin string, updates map[string]interface{}) error

	// Delete deletes a security by ISIN
	Delete(isin string) error

	// GetWithScores returns securities with their scores joined
	GetWithScores(portfolioDB *sql.DB) ([]SecurityWithScore, error)

	// SetTagsForSecurity replaces all tags for a security (deletes existing, inserts new)
	// symbol parameter is kept for backward compatibility, but we look up ISIN internally
	SetTagsForSecurity(symbol string, tagIDs []string) error

	// GetTagsForSecurity returns all tag IDs for a security (public method)
	// symbol parameter is kept for backward compatibility, but we look up ISIN internally
	GetTagsForSecurity(symbol string) ([]string, error)

	// GetTagsWithUpdateTimes returns all tags for a security with their last update times
	// symbol parameter is kept for backward compatibility, but we look up ISIN internally
	GetTagsWithUpdateTimes(symbol string) (map[string]time.Time, error)

	// UpdateSpecificTags updates only the specified tags for a security, preserving other tags
	// symbol parameter is kept for backward compatibility, but we look up ISIN internally
	UpdateSpecificTags(symbol string, tagIDs []string) error

	// GetByTags returns active securities matching any of the provided tags
	GetByTags(tagIDs []string) ([]Security, error)

	// GetPositionsByTags returns securities that are in the provided position symbols AND have the specified tags
	GetPositionsByTags(positionSymbols []string, tagIDs []string) ([]Security, error)
}

// Compile-time check that SecurityRepository implements SecurityRepositoryInterface
var _ SecurityRepositoryInterface = (*SecurityRepository)(nil)

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

// Note: CurrencyExchangeServiceInterface has been moved to domain/interfaces.go
// It is now available as domain.CurrencyExchangeServiceInterface
