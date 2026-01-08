// Package tradernet provides client functionality for interacting with the Tradernet API.
package tradernet

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/rs/zerolog"

	"github.com/aristath/sentinel/internal/clients/tradernet/sdk"
)

// Client for Tradernet API (using SDK directly)
type Client struct {
	sdkClient SDKClient
	log       zerolog.Logger
	apiKey    string
	apiSecret string
}

// ServiceResponse is the standard response format (kept for backward compatibility)
type ServiceResponse struct {
	Success   bool            `json:"success"`
	Data      json.RawMessage `json:"data"`
	Error     *string         `json:"error"`
	Timestamp string          `json:"timestamp"`
}

// NewClient creates a new Tradernet client using SDK
// Always creates an SDK client, even with empty credentials (SDK will validate and return errors)
func NewClient(apiKey, apiSecret string, log zerolog.Logger) *Client {
	// Always create SDK client - it will validate credentials and return errors if invalid
	sdkClient := sdk.NewClient(apiKey, apiSecret, log)

	return &Client{
		sdkClient: sdkClient,
		log:       log.With().Str("client", "tradernet").Logger(),
		apiKey:    apiKey,
		apiSecret: apiSecret,
	}
}

// NewClientWithSDK creates a new Tradernet client with a provided SDK client (for testing)
func NewClientWithSDK(sdkClient SDKClient, log zerolog.Logger) *Client {
	return &Client{
		sdkClient: sdkClient,
		log:       log.With().Str("client", "tradernet").Logger(),
	}
}

// SetCredentials sets the API credentials for the client
// This will recreate the SDK client with new credentials
func (c *Client) SetCredentials(apiKey, apiSecret string) {
	c.apiKey = apiKey
	c.apiSecret = apiSecret
	// Always recreate SDK client with new credentials (even if empty - SDK will validate)
	c.sdkClient = sdk.NewClient(apiKey, apiSecret, c.log)
}

// PlaceOrderRequest is the request for placing an order
type PlaceOrderRequest struct {
	Symbol   string  `json:"symbol"`
	Side     string  `json:"side"`
	Quantity float64 `json:"quantity"`
}

// OrderResult is the result of placing an order
type OrderResult struct {
	OrderID  string  `json:"order_id"`
	Symbol   string  `json:"symbol"`
	Side     string  `json:"side"`
	Quantity float64 `json:"quantity"`
	Price    float64 `json:"price"`
}

// PlaceOrder executes a trade order
func (c *Client) PlaceOrder(symbol, side string, quantity float64) (*OrderResult, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Str("symbol", symbol).Str("side", side).Float64("quantity", quantity).Msg("PlaceOrder: calling SDK")

	quantityInt := int(quantity)
	var result interface{}
	var err error

	if side == "BUY" {
		result, err = c.sdkClient.Buy(symbol, quantityInt, 0.0, "day", false, nil)
	} else if side == "SELL" {
		result, err = c.sdkClient.Sell(symbol, quantityInt, 0.0, "day", false, nil)
	} else {
		return nil, fmt.Errorf("invalid side: %s (must be BUY or SELL)", side)
	}

	if err != nil {
		c.log.Error().Err(err).Msg("PlaceOrder: SDK Buy/Sell failed")
		return nil, fmt.Errorf("failed to place order: %w", err)
	}

	orderResult, err := transformOrderResult(result, symbol, side, quantity)
	if err != nil {
		c.log.Error().Err(err).Msg("PlaceOrder: transformOrderResult failed")
		return nil, fmt.Errorf("failed to transform order result: %w", err)
	}

	return orderResult, nil
}

// Position represents a portfolio position
type Position struct {
	Symbol         string  `json:"symbol"`
	Quantity       float64 `json:"quantity"`
	AvgPrice       float64 `json:"avg_price"`
	CurrentPrice   float64 `json:"current_price"`
	MarketValue    float64 `json:"market_value"`
	MarketValueEUR float64 `json:"market_value_eur"`
	UnrealizedPnL  float64 `json:"unrealized_pnl"`
	Currency       string  `json:"currency"`
	CurrencyRate   float64 `json:"currency_rate"`
}

// PositionsResponse is the response for GetPortfolio
type PositionsResponse struct {
	Positions []Position `json:"positions"`
}

// GetPortfolio gets current portfolio positions
func (c *Client) GetPortfolio() ([]Position, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Msg("GetPortfolio: calling SDK AccountSummary")
	result, err := c.sdkClient.AccountSummary()
	if err != nil {
		c.log.Error().Err(err).Msg("GetPortfolio: SDK AccountSummary failed")
		return nil, fmt.Errorf("failed to get account summary: %w", err)
	}

	positions, err := transformPositions(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetPortfolio: transformPositions failed")
		return nil, fmt.Errorf("failed to transform positions: %w", err)
	}

	c.log.Debug().Int("positions_count", len(positions)).Msg("GetPortfolio: successfully parsed")
	return positions, nil
}

// CashBalance represents cash balance in a currency
type CashBalance struct {
	Currency string  `json:"currency"`
	Amount   float64 `json:"amount"`
}

// CashBalancesResponse is the response for GetCashBalances
type CashBalancesResponse struct {
	Balances []CashBalance `json:"balances"`
}

// GetCashBalances gets cash balances in all currencies
func (c *Client) GetCashBalances() ([]CashBalance, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Msg("GetCashBalances: calling SDK AccountSummary")
	result, err := c.sdkClient.AccountSummary()
	if err != nil {
		c.log.Error().Err(err).Msg("GetCashBalances: SDK AccountSummary failed")
		return nil, fmt.Errorf("failed to get account summary: %w", err)
	}

	balances, err := transformCashBalances(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetCashBalances: transformCashBalances failed")
		return nil, fmt.Errorf("failed to transform cash balances: %w", err)
	}

	return balances, nil
}

// CashMovementsResponse is the response for GetCashMovements
type CashMovementsResponse struct {
	TotalWithdrawals float64                  `json:"total_withdrawals"`
	Withdrawals      []map[string]interface{} `json:"withdrawals"`
	Note             string                   `json:"note"`
}

// GetCashMovements gets withdrawal history
func (c *Client) GetCashMovements() (*CashMovementsResponse, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Msg("GetCashMovements: calling SDK GetClientCpsHistory")
	result, err := c.sdkClient.GetClientCpsHistory("", "", nil, nil, nil, nil, nil)
	if err != nil {
		c.log.Error().Err(err).Msg("GetCashMovements: SDK GetClientCpsHistory failed")
		return nil, fmt.Errorf("failed to get cash movements: %w", err)
	}

	response, err := transformCashMovements(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetCashMovements: transformCashMovements failed")
		return nil, fmt.Errorf("failed to transform cash movements: %w", err)
	}

	return response, nil
}

// SecurityInfo represents security lookup result
type SecurityInfo struct {
	Symbol       string  `json:"symbol"`
	Name         *string `json:"name"`
	ISIN         *string `json:"isin"`
	Currency     *string `json:"currency"`
	Market       *string `json:"market"`
	ExchangeCode *string `json:"exchange_code"`
}

// FindSymbolResponse is the response for FindSymbol
type FindSymbolResponse struct {
	Found []SecurityInfo `json:"found"`
}

// FindSymbol finds security by symbol or ISIN
func (c *Client) FindSymbol(symbol string, exchange *string) ([]SecurityInfo, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Str("symbol", symbol).Msg("FindSymbol: calling SDK FindSymbol")

	result, err := c.sdkClient.FindSymbol(symbol, exchange)
	if err != nil {
		c.log.Error().Err(err).Msg("FindSymbol: SDK FindSymbol failed")
		return nil, fmt.Errorf("failed to find symbol: %w", err)
	}

	securities, err := transformSecurityInfo(result)
	if err != nil {
		c.log.Error().Err(err).Msg("FindSymbol: transformSecurityInfo failed")
		return nil, fmt.Errorf("failed to transform security info: %w", err)
	}

	return securities, nil
}

// Trade represents an executed trade
type Trade struct {
	OrderID    string  `json:"order_id"`
	Symbol     string  `json:"symbol"`
	Side       string  `json:"side"`
	Quantity   float64 `json:"quantity"`
	Price      float64 `json:"price"`
	ExecutedAt string  `json:"executed_at"`
}

// ExecutedTradesResponse is the response for GetExecutedTrades
type ExecutedTradesResponse struct {
	Trades []Trade `json:"trades"`
}

// GetExecutedTrades gets executed trade history
func (c *Client) GetExecutedTrades(limit int) ([]Trade, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Int("limit", limit).Msg("GetExecutedTrades: calling SDK GetTradesHistory")

	limitPtr := &limit
	result, err := c.sdkClient.GetTradesHistory("", "", nil, limitPtr, nil, nil, nil)
	if err != nil {
		c.log.Error().Err(err).Msg("GetExecutedTrades: SDK GetTradesHistory failed")
		return nil, fmt.Errorf("failed to get executed trades: %w", err)
	}

	trades, err := transformTrades(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetExecutedTrades: transformTrades failed")
		return nil, fmt.Errorf("failed to transform trades: %w", err)
	}

	return trades, nil
}

// CashFlowTransaction represents a cash flow transaction from Tradernet API
type CashFlowTransaction struct {
	ID              string                 `json:"id"`
	TransactionID   string                 `json:"transaction_id"`
	TypeDocID       int                    `json:"type_doc_id"`
	Type            string                 `json:"type"`
	TransactionType string                 `json:"transaction_type"`
	DT              string                 `json:"dt"`
	Date            string                 `json:"date"`
	SM              float64                `json:"sm"`
	Amount          float64                `json:"amount"`
	Curr            string                 `json:"curr"`
	Currency        string                 `json:"currency"`
	SMEUR           float64                `json:"sm_eur"`
	AmountEUR       float64                `json:"amount_eur"`
	Status          string                 `json:"status"`
	StatusC         int                    `json:"status_c"`
	Description     string                 `json:"description"`
	Params          map[string]interface{} `json:"params"`
}

// CashFlowsResponse is the response for GetAllCashFlows
type CashFlowsResponse struct {
	CashFlows []CashFlowTransaction `json:"cash_flows"`
}

// GetAllCashFlows fetches all cash flows from Tradernet API
// Combines multiple sources: transaction history, corporate actions, fees
func (c *Client) GetAllCashFlows(limit int) ([]CashFlowTransaction, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Int("limit", limit).Msg("GetAllCashFlows: calling SDK GetClientCpsHistory")

	limitPtr := &limit
	result, err := c.sdkClient.GetClientCpsHistory("", "", nil, nil, limitPtr, nil, nil)
	if err != nil {
		c.log.Error().Err(err).Msg("GetAllCashFlows: SDK GetClientCpsHistory failed")
		return nil, fmt.Errorf("failed to get cash flows: %w", err)
	}

	transactions, err := transformCashFlows(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetAllCashFlows: transformCashFlows failed")
		return nil, fmt.Errorf("failed to transform cash flows: %w", err)
	}

	c.log.Info().Int("count", len(transactions)).Msg("Fetched cash flows from Tradernet")
	return transactions, nil
}

// HealthResponse represents the health check response from the microservice
type HealthResponse struct {
	Status             string `json:"status"`
	Service            string `json:"service"`
	Version            string `json:"version"`
	Timestamp          string `json:"timestamp"`
	TradernetConnected bool   `json:"tradernet_connected"`
}

// HealthCheckResult represents the result of a health check
type HealthCheckResult struct {
	Connected bool
	Timestamp string
}

// HealthCheck checks the health of the Tradernet API using UserInfo()
func (c *Client) HealthCheck() (*HealthCheckResult, error) {
	if c.sdkClient == nil {
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil
	}

	c.log.Debug().Msg("HealthCheck: calling SDK UserInfo")

	_, err := c.sdkClient.UserInfo()
	if err != nil {
		c.log.Debug().Err(err).Msg("HealthCheck: SDK UserInfo failed")
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil // Return result, not error - service unavailable means not connected
	}

	return &HealthCheckResult{
		Connected: true,
		Timestamp: time.Now().Format(time.RFC3339),
	}, nil
}

// IsConnected checks if the Tradernet API is reachable
func (c *Client) IsConnected() bool {
	if c.sdkClient == nil {
		c.log.Debug().Msg("IsConnected: SDK client is nil")
		return false
	}

	c.log.Debug().Msg("IsConnected: calling SDK UserInfo")

	_, err := c.sdkClient.UserInfo()
	if err != nil {
		c.log.Debug().Err(err).Msg("IsConnected: SDK UserInfo failed")
		return false
	}

	return true
}

// Quote represents a security quote
type Quote struct {
	Symbol    string  `json:"symbol"`
	Price     float64 `json:"price"`
	Change    float64 `json:"change"`
	ChangePct float64 `json:"change_pct"`
	Volume    int64   `json:"volume"`
	Timestamp string  `json:"timestamp"`
}

// QuoteResponse is the response for GetQuote
type QuoteResponse struct {
	Quote Quote `json:"quote"`
}

// GetQuote gets current quote for a symbol
func (c *Client) GetQuote(symbol string) (*Quote, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Str("symbol", symbol).Msg("GetQuote: calling SDK GetQuotes")

	result, err := c.sdkClient.GetQuotes([]string{symbol})
	if err != nil {
		c.log.Error().Err(err).Msg("GetQuote: SDK GetQuotes failed")
		return nil, fmt.Errorf("failed to get quote: %w", err)
	}

	quote, err := transformQuote(result, symbol)
	if err != nil {
		c.log.Error().Err(err).Msg("GetQuote: transformQuote failed")
		return nil, fmt.Errorf("failed to transform quote: %w", err)
	}

	return quote, nil
}

// PendingOrder represents a pending order in the broker
type PendingOrder struct {
	OrderID  string  `json:"order_id"`
	Symbol   string  `json:"symbol"`
	Side     string  `json:"side"`
	Quantity float64 `json:"quantity"`
	Price    float64 `json:"price"`
	Currency string  `json:"currency"`
}

// PendingOrdersResponse is the response for GetPendingOrders
type PendingOrdersResponse struct {
	Orders []PendingOrder `json:"orders"`
}

// GetPendingOrders retrieves all pending orders from the broker
func (c *Client) GetPendingOrders() ([]PendingOrder, error) {
	if c.sdkClient == nil {
		return nil, fmt.Errorf("SDK client not initialized")
	}

	c.log.Debug().Msg("GetPendingOrders: calling SDK GetPlaced")
	result, err := c.sdkClient.GetPlaced(true)
	if err != nil {
		c.log.Error().Err(err).Msg("GetPendingOrders: SDK GetPlaced failed")
		return nil, fmt.Errorf("failed to get pending orders: %w", err)
	}

	orders, err := transformPendingOrders(result)
	if err != nil {
		c.log.Error().Err(err).Msg("GetPendingOrders: transformPendingOrders failed")
		return nil, fmt.Errorf("failed to transform pending orders: %w", err)
	}

	return orders, nil
}
