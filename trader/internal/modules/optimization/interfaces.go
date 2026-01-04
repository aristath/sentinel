package optimization

import "github.com/aristath/arduino-trader/internal/clients/tradernet"

// TradernetClientInterface defines the contract for Tradernet client operations
// Used by Handler to enable testing with mocks
type TradernetClientInterface interface {
	GetCashBalances() ([]tradernet.CashBalance, error)
}

// CurrencyExchangeServiceInterface defines the contract for currency exchange operations
// Used by Handler to enable testing with mocks
type CurrencyExchangeServiceInterface interface {
	GetRate(fromCurrency, toCurrency string) (float64, error)
}
