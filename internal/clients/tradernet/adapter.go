package tradernet

import (
	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
)

// TradernetBrokerAdapter adapts tradernet.Client to domain.BrokerClient
// This adapter owns the Tradernet client internally and provides a broker-agnostic interface
type TradernetBrokerAdapter struct {
	client *Client
}

// NewTradernetBrokerAdapter creates a new Tradernet broker adapter
// The adapter owns the Tradernet client internally
func NewTradernetBrokerAdapter(apiKey, apiSecret string, log zerolog.Logger) *TradernetBrokerAdapter {
	client := NewClient(apiKey, apiSecret, log)
	return &TradernetBrokerAdapter{
		client: client,
	}
}

// GetPortfolio implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetPortfolio() ([]domain.BrokerPosition, error) {
	tnPositions, err := a.client.GetPortfolio()
	if err != nil {
		return nil, err
	}
	return transformPositionsToDomain(tnPositions), nil
}

// GetCashBalances implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	tnBalances, err := a.client.GetCashBalances()
	if err != nil {
		return nil, err
	}
	return transformCashBalancesToDomain(tnBalances), nil
}

// PlaceOrder implements domain.BrokerClient
func (a *TradernetBrokerAdapter) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	tnResult, err := a.client.PlaceOrder(symbol, side, quantity, limitPrice)
	if err != nil {
		return nil, err
	}
	return transformOrderResultToDomain(tnResult), nil
}

// GetExecutedTrades implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	tnTrades, err := a.client.GetExecutedTrades(limit)
	if err != nil {
		return nil, err
	}
	return transformTradesToDomain(tnTrades), nil
}

// GetPendingOrders implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	tnOrders, err := a.client.GetPendingOrders()
	if err != nil {
		return nil, err
	}
	return transformPendingOrdersToDomain(tnOrders), nil
}

// GetQuote implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	tnQuote, err := a.client.GetQuote(symbol)
	if err != nil {
		return nil, err
	}
	return transformQuoteToDomain(tnQuote), nil
}

// GetQuotes implements domain.BrokerClient
// Fetches quotes for multiple symbols in a single batch call
func (a *TradernetBrokerAdapter) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	if len(symbols) == 0 {
		return make(map[string]*domain.BrokerQuote), nil
	}

	tnQuotes, err := a.client.GetQuotes(symbols)
	if err != nil {
		return nil, err
	}
	return transformQuotesToDomain(tnQuotes), nil
}

// GetHistoricalPrices implements domain.BrokerClient
// Fetches OHLCV candlestick data for a symbol
func (a *TradernetBrokerAdapter) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	tnCandles, err := a.client.GetHistoricalPrices(symbol, start, end, timeframeSeconds)
	if err != nil {
		return nil, err
	}
	return transformOHLCVToDomain(tnCandles), nil
}

// GetLevel1Quote implements domain.BrokerClient
// Fetches Level 1 market data (best bid and best ask) from Tradernet
func (a *TradernetBrokerAdapter) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	tnOrderBook, err := a.client.GetLevel1Quote(symbol)
	if err != nil {
		return nil, err
	}
	return transformOrderBookToDomain(tnOrderBook), nil
}

// FindSymbol implements domain.BrokerClient
func (a *TradernetBrokerAdapter) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	tnSecurities, err := a.client.FindSymbol(symbol, exchange)
	if err != nil {
		return nil, err
	}
	return transformSecurityInfoToDomain(tnSecurities), nil
}

// GetSecurityMetadata implements domain.BrokerClient
// Uses getAllSecurities API which returns issuer_country_code and sector_code
func (a *TradernetBrokerAdapter) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	tnSecurity, err := a.client.GetSecurityMetadata(symbol)
	if err != nil {
		return nil, err
	}
	if tnSecurity == nil {
		return nil, nil
	}
	// Transform single security to domain type
	results := transformSecurityInfoToDomain([]SecurityInfo{*tnSecurity})
	if len(results) == 0 {
		return nil, nil
	}
	return &results[0], nil
}

// GetFXRates implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	rates, err := a.client.GetFXRates(baseCurrency, currencies)
	if err != nil {
		return nil, err
	}
	return rates, nil
}

// GetAllCashFlows implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	tnFlows, err := a.client.GetAllCashFlows(limit)
	if err != nil {
		return nil, err
	}
	return transformCashFlowsToDomain(tnFlows), nil
}

// GetCashMovements implements domain.BrokerClient
func (a *TradernetBrokerAdapter) GetCashMovements() (*domain.BrokerCashMovement, error) {
	tnMovements, err := a.client.GetCashMovements()
	if err != nil {
		return nil, err
	}
	return transformCashMovementsToDomain(tnMovements), nil
}

// IsConnected implements domain.BrokerClient
func (a *TradernetBrokerAdapter) IsConnected() bool {
	return a.client.IsConnected()
}

// HealthCheck implements domain.BrokerClient
func (a *TradernetBrokerAdapter) HealthCheck() (*domain.BrokerHealthResult, error) {
	tnHealth, err := a.client.HealthCheck()
	if err != nil {
		return nil, err
	}
	return transformHealthResultToDomain(tnHealth), nil
}

// SetCredentials implements domain.BrokerClient
func (a *TradernetBrokerAdapter) SetCredentials(apiKey, apiSecret string) {
	a.client.SetCredentials(apiKey, apiSecret)
}

// Close gracefully shuts down the adapter and its underlying client
func (a *TradernetBrokerAdapter) Close() {
	if a.client != nil {
		a.client.Close()
	}
}
