package tradernet

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog"
)

// Client for Tradernet microservice
type Client struct {
	baseURL   string
	client    *http.Client
	log       zerolog.Logger
	apiKey    string
	apiSecret string
}

// ServiceResponse is the standard response format
type ServiceResponse struct {
	Success   bool            `json:"success"`
	Data      json.RawMessage `json:"data"`
	Error     *string         `json:"error"`
	Timestamp string          `json:"timestamp"`
}

// NewClient creates a new Tradernet microservice client
func NewClient(baseURL string, log zerolog.Logger) *Client {
	return &Client{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log.With().Str("client", "tradernet").Logger(),
	}
}

// SetCredentials sets the API credentials for the client
func (c *Client) SetCredentials(apiKey, apiSecret string) {
	c.apiKey = apiKey
	c.apiSecret = apiSecret
}

// post makes a POST request to the microservice
func (c *Client) post(endpoint string, request interface{}) (*ServiceResponse, error) {
	body, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	url := c.baseURL + endpoint
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	// Add credentials to headers if available
	if c.apiKey != "" {
		req.Header.Set("X-Tradernet-API-Key", c.apiKey)
	}
	if c.apiSecret != "" {
		req.Header.Set("X-Tradernet-API-Secret", c.apiSecret)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp)
}

// get makes a GET request to the microservice
func (c *Client) get(endpoint string) (*ServiceResponse, error) {
	url := c.baseURL + endpoint
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Add credentials to headers if available
	if c.apiKey != "" {
		req.Header.Set("X-Tradernet-API-Key", c.apiKey)
	}
	if c.apiSecret != "" {
		req.Header.Set("X-Tradernet-API-Secret", c.apiSecret)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp)
}

// parseResponse parses the service response
func (c *Client) parseResponse(resp *http.Response) (*ServiceResponse, error) {
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var result ServiceResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if !result.Success {
		errMsg := "unknown error"
		if result.Error != nil {
			errMsg = *result.Error
		}
		return &result, fmt.Errorf("microservice error: %s", errMsg)
	}

	return &result, nil
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
	req := PlaceOrderRequest{
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
	}

	resp, err := c.post("/api/trading/place-order", req)
	if err != nil {
		return nil, err
	}

	var result OrderResult
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse order result: %w", err)
	}

	return &result, nil
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
	resp, err := c.get("/api/portfolio/positions")
	if err != nil {
		return nil, err
	}

	var result PositionsResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse positions: %w", err)
	}

	return result.Positions, nil
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
	resp, err := c.get("/api/portfolio/cash-balances")
	if err != nil {
		return nil, err
	}

	var result CashBalancesResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse cash balances: %w", err)
	}

	return result.Balances, nil
}

// CashMovementsResponse is the response for GetCashMovements
type CashMovementsResponse struct {
	TotalWithdrawals float64                  `json:"total_withdrawals"`
	Withdrawals      []map[string]interface{} `json:"withdrawals"`
	Note             string                   `json:"note"`
}

// GetCashMovements gets withdrawal history
func (c *Client) GetCashMovements() (*CashMovementsResponse, error) {
	resp, err := c.get("/api/transactions/cash-movements")
	if err != nil {
		return nil, err
	}

	var result CashMovementsResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse cash movements: %w", err)
	}

	return &result, nil
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
	url := fmt.Sprintf("/api/securities/find?symbol=%s", symbol)
	if exchange != nil {
		url += fmt.Sprintf("&exchange=%s", *exchange)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result FindSymbolResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse find symbol result: %w", err)
	}

	return result.Found, nil
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
	url := fmt.Sprintf("/api/transactions/executed-trades?limit=%d", limit)
	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result ExecutedTradesResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse executed trades: %w", err)
	}

	return result.Trades, nil
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
	url := fmt.Sprintf("/api/transactions/cash-flows?limit=%d", limit)
	resp, err := c.get(url)
	if err != nil {
		c.log.Error().Err(err).Msg("Failed to fetch cash flows from Tradernet")
		return nil, fmt.Errorf("failed to fetch cash flows: %w", err)
	}

	var result CashFlowsResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse cash flows: %w", err)
	}

	c.log.Info().Int("count", len(result.CashFlows)).Msg("Fetched cash flows from Tradernet")
	return result.CashFlows, nil
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

// HealthCheck checks the health of the Tradernet microservice
// The /health endpoint returns plain JSON, not the standard ServiceResponse format
func (c *Client) HealthCheck() (*HealthCheckResult, error) {
	url := c.baseURL + "/health"
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil
	}

	// Add credentials to headers if available (for testing connection)
	if c.apiKey != "" {
		req.Header.Set("X-Tradernet-API-Key", c.apiKey)
	}
	if c.apiSecret != "" {
		req.Header.Set("X-Tradernet-API-Secret", c.apiSecret)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		c.log.Debug().Err(err).Msg("Failed to connect to Tradernet microservice health endpoint")
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil // Return result, not error - service unavailable means not connected
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		c.log.Debug().Int("status_code", resp.StatusCode).Msg("Tradernet microservice health check returned non-200 status")
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		c.log.Debug().Err(err).Msg("Failed to read health check response")
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil
	}

	var healthResp HealthResponse
	if err := json.Unmarshal(body, &healthResp); err != nil {
		c.log.Debug().Err(err).Msg("Failed to parse health check response")
		return &HealthCheckResult{
			Connected: false,
			Timestamp: time.Now().Format(time.RFC3339),
		}, nil
	}

	return &HealthCheckResult{
		Connected: healthResp.TradernetConnected,
		Timestamp: healthResp.Timestamp,
	}, nil
}

// IsConnected checks if the Tradernet microservice is reachable
func (c *Client) IsConnected() bool {
	// Try a simple health check endpoint
	resp, err := c.get("/health")
	if err != nil {
		c.log.Debug().Err(err).Msg("Tradernet microservice not connected")
		return false
	}
	return resp.Success
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
	url := fmt.Sprintf("/api/quotes/%s", symbol)
	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result QuoteResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse quote: %w", err)
	}

	return &result.Quote, nil
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
	resp, err := c.get("/api/orders/pending")
	if err != nil {
		return nil, err
	}

	var result PendingOrdersResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse pending orders: %w", err)
	}

	return result.Orders, nil
}
