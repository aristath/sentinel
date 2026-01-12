package services

import (
	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// Interfaces for OpportunityContextBuilder dependencies
// Following Dependency Inversion Principle - the service defines what it needs,
// and the infrastructure layer implements it.

// PositionRepository provides access to portfolio positions.
type PositionRepository interface {
	GetAll() ([]portfolio.Position, error)
}

// SecurityRepository provides access to securities in the universe.
type SecurityRepository interface {
	GetAllActive() ([]universe.Security, error)
	GetByISIN(isin string) (*universe.Security, error)
	GetBySymbol(symbol string) (*universe.Security, error)
}

// AllocationRepository provides access to allocation targets.
type AllocationRepository interface {
	GetAll() (map[string]float64, error)
}

// GroupingRepository provides access to country/industry groupings.
type GroupingRepository interface {
	GetCountryGroups() (map[string][]string, error)
	GetIndustryGroups() (map[string][]string, error)
	GetGroupWeights(groupType string) (map[string]float64, error)
}

// TradeRepository provides access to trade history for cooloff calculations.
type TradeRepository interface {
	GetRecentlySoldISINs(days int) (map[string]bool, error)
	GetRecentlyBoughtISINs(days int) (map[string]bool, error)
}

// ScoresRepository provides access to security scores.
type ScoresRepository interface {
	GetTotalScores(isinList []string) (map[string]float64, error)
	GetCAGRs(isinList []string) (map[string]float64, error)
	GetQualityScores(isinList []string) (longTermScores, fundamentalsScores map[string]float64, err error)
	GetValueTrapData(isinList []string) (opportunityScores, momentumScores, volatility map[string]float64, err error)
	GetRiskMetrics(isinList []string) (sharpe, maxDrawdown map[string]float64, err error)
}

// SettingsRepository provides access to planner settings.
type SettingsRepository interface {
	GetTargetReturnSettings() (targetReturn, thresholdPct float64, err error)
	GetCooloffDays() (int, error)
	GetVirtualTestCash() (float64, error)
}

// RegimeRepository provides access to market regime data.
type RegimeRepository interface {
	GetCurrentRegimeScore() (float64, error)
}

// CashManager provides access to cash balances.
type CashManager interface {
	GetAllCashBalances() (map[string]float64, error)
}

// PriceClient provides access to current prices.
type PriceClient interface {
	GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error)
}

// PriceConversionServiceInterface converts prices to EUR.
type PriceConversionServiceInterface interface {
	ConvertPricesToEUR(prices map[string]float64, securities []universe.Security) map[string]float64
}

// BrokerClient provides access to broker operations for pending orders.
type BrokerClient interface {
	IsConnected() bool
	GetPendingOrders() ([]domain.BrokerPendingOrder, error)
}

// DismissedFilterRepository provides access to user-dismissed pre-filter reasons.
type DismissedFilterRepository interface {
	GetAll() (map[string]map[string][]string, error) // map[ISIN][calculator][]reasons
}
