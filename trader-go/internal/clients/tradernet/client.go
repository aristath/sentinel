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
	baseURL string
	client  *http.Client
	log     zerolog.Logger
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

// post makes a POST request to the microservice
func (c *Client) post(endpoint string, request interface{}) (*ServiceResponse, error) {
	body, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	url := c.baseURL + endpoint
	resp, err := c.client.Post(url, "application/json", bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp)
}

// get makes a GET request to the microservice
func (c *Client) get(endpoint string) (*ServiceResponse, error) {
	url := c.baseURL + endpoint
	resp, err := c.client.Get(url)
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
