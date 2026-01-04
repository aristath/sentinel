package scheduler

// UniverseServiceInterface defines the contract for universe service operations
// Used by scheduler to enable testing with mocks
type UniverseServiceInterface interface {
	SyncPrices() error
	SyncPricesForExchanges(exchangeNames []string) error
}

// MarketHoursServiceInterface defines the contract for market hours operations
// Used by scheduler to enable testing with mocks
type MarketHoursServiceInterface interface {
	GetAllMarketStatuses() []MarketStatus
	IsMarketOpen(exchangeName string) bool
}

// BalanceServiceInterface defines the contract for balance service operations
// Used by scheduler to enable testing with mocks
type BalanceServiceInterface interface {
	GetAllCurrencies() ([]string, error)
	GetTotalByCurrency(currency string) (float64, error)
}
