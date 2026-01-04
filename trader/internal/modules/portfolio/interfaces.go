package portfolio

import "github.com/aristath/arduino-trader/internal/clients/tradernet"

// TradernetClientInterface defines the contract for Tradernet client operations
// Used by PortfolioService to enable testing with mocks
type TradernetClientInterface interface {
	GetPortfolio() ([]tradernet.Position, error)
	GetCashBalances() ([]tradernet.CashBalance, error)
}

// PositionRepositoryInterface defines the contract for position repository operations
// Used by PortfolioService to enable testing with mocks
type PositionRepositoryInterface interface {
	GetAll() ([]Position, error)
	GetWithSecurityInfo() ([]PositionWithSecurity, error)
	GetBySymbol(symbol string) (*Position, error)
	Upsert(position Position) error
	Delete(symbol string) error
}
