package domain

// CashManager defines operations for managing cash balances
// This interface breaks circular dependencies between portfolio, cash_flows, and services packages
// Merged from:
//   - portfolio.CashManager (UpdateCashPosition, GetAllCashBalances)
//   - services.CashManagerInterface (GetCashBalance)
type CashManager interface {
	// UpdateCashPosition updates or creates a cash balance for the given currency
	UpdateCashPosition(currency string, balance float64) error

	// GetAllCashBalances returns all cash balances as a map of currency -> balance
	GetAllCashBalances() (map[string]float64, error)

	// GetCashBalance returns the cash balance for the given currency
	// Returns 0 if no balance exists (not an error)
	GetCashBalance(currency string) (float64, error)
}

// BrokerClient defines broker-agnostic trading and portfolio operations
// This interface abstracts away broker-specific implementations (Tradernet, IBKR, etc.)
// All broker operations should go through this interface for maximum flexibility
type BrokerClient interface {
	// Portfolio operations
	GetPortfolio() ([]BrokerPosition, error)
	GetCashBalances() ([]BrokerCashBalance, error)

	// Trading operations
	PlaceOrder(symbol, side string, quantity, limitPrice float64) (*BrokerOrderResult, error)
	GetExecutedTrades(limit int) ([]BrokerTrade, error)
	GetPendingOrders() ([]BrokerPendingOrder, error)

	// Market data operations
	GetQuote(symbol string) (*BrokerQuote, error)
	FindSymbol(symbol string, exchange *string) ([]BrokerSecurityInfo, error)

	// Cash operations
	GetAllCashFlows(limit int) ([]BrokerCashFlow, error)
	GetCashMovements() (*BrokerCashMovement, error)

	// Connection & health
	IsConnected() bool
	HealthCheck() (*BrokerHealthResult, error)
	SetCredentials(apiKey, apiSecret string)
}

// CurrencyExchangeServiceInterface defines the contract for currency exchange operations
// Used by portfolio, services, optimization, and universe packages
// This interface avoids import cycles with the services package
type CurrencyExchangeServiceInterface interface {
	// GetRate returns the exchange rate from one currency to another
	GetRate(fromCurrency, toCurrency string) (float64, error)

	// EnsureBalance ensures there is sufficient balance in the target currency
	// If insufficient, it will convert from source currency automatically
	// Returns true if successful, false if unable to ensure balance
	EnsureBalance(currency string, minAmount float64, sourceCurrency string) (bool, error)
}

// AllocationTargetProvider provides access to allocation targets
// This interface breaks the circular dependency between portfolio and allocation packages
type AllocationTargetProvider interface {
	// GetAll returns all allocation targets as a map of name -> target percentage
	GetAll() (map[string]float64, error)
}

// PortfolioSummaryProvider provides portfolio summary data without creating
// a dependency on the portfolio package. This interface breaks the circular
// dependency: allocation → portfolio → cash_flows → trading → allocation
type PortfolioSummaryProvider interface {
	// GetPortfolioSummary returns the current portfolio summary
	GetPortfolioSummary() (PortfolioSummary, error)
}

// ConcentrationAlertProvider provides concentration alert detection without
// requiring direct dependency on ConcentrationAlertService. This interface
// breaks the circular dependency: trading → allocation
type ConcentrationAlertProvider interface {
	// DetectAlerts detects concentration alerts from a portfolio summary
	DetectAlerts(summary PortfolioSummary) ([]ConcentrationAlert, error)
}

// PortfolioSummary represents complete portfolio allocation summary
// This is the domain model used by the allocation package
// Note: This is different from portfolio.PortfolioSummary (which uses AllocationStatus)
// This version uses PortfolioAllocation for compatibility with allocation package
type PortfolioSummary struct {
	CountryAllocations  []PortfolioAllocation
	IndustryAllocations []PortfolioAllocation
	TotalValue          float64
	CashBalance         float64
}

// PortfolioAllocation represents allocation info for display
type PortfolioAllocation struct {
	Name         string
	TargetPct    float64
	CurrentPct   float64
	CurrentValue float64
	Deviation    float64
}

// ConcentrationAlert represents alert for approaching concentration limit
type ConcentrationAlert struct {
	Type              string
	Name              string
	Severity          string
	CurrentPct        float64
	LimitPct          float64
	AlertThresholdPct float64
}
