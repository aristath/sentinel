package yahoo

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog"
)

// MicroserviceClient is an HTTP client for the Yahoo Finance microservice
type MicroserviceClient struct {
	baseURL string
	client  *http.Client
	log     zerolog.Logger
}

// ServiceResponse is the standard response format from the microservice
type ServiceResponse struct {
	Success   bool            `json:"success"`
	Data      json.RawMessage `json:"data"`
	Error     *string         `json:"error"`
	Timestamp string          `json:"timestamp"`
}

// NewMicroserviceClient creates a new Yahoo Finance microservice client
func NewMicroserviceClient(baseURL string, log zerolog.Logger) *MicroserviceClient {
	return &MicroserviceClient{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log.With().Str("client", "yahoo-microservice").Logger(),
	}
}

// post makes a POST request to the microservice
func (c *MicroserviceClient) post(endpoint string, request interface{}) (*ServiceResponse, error) {
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

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp)
}

// get makes a GET request to the microservice
func (c *MicroserviceClient) get(endpoint string) (*ServiceResponse, error) {
	url := c.baseURL + endpoint
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp)
}

// parseResponse parses the service response
func (c *MicroserviceClient) parseResponse(resp *http.Response) (*ServiceResponse, error) {
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

// BatchQuotesRequest is the request for batch quotes
type BatchQuotesRequest struct {
	Symbols        []string          `json:"symbols"`
	YahooOverrides map[string]string `json:"yahoo_overrides,omitempty"`
}

// BatchQuotesResponse is the response for batch quotes
type BatchQuotesResponse struct {
	Quotes map[string]float64 `json:"quotes"`
}

// GetBatchQuotes fetches current prices for multiple symbols efficiently
func (c *MicroserviceClient) GetBatchQuotes(
	symbolOverrides map[string]*string,
) (map[string]*float64, error) {
	// Convert to request format
	symbols := make([]string, 0, len(symbolOverrides))
	yahooOverrides := make(map[string]string)

	for symbol, yahooOverride := range symbolOverrides {
		symbols = append(symbols, symbol)
		if yahooOverride != nil && *yahooOverride != "" {
			yahooOverrides[symbol] = *yahooOverride
		}
	}

	req := BatchQuotesRequest{
		Symbols:        symbols,
		YahooOverrides: yahooOverrides,
	}

	resp, err := c.post("/api/quotes/batch", req)
	if err != nil {
		return nil, err
	}

	var result BatchQuotesResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse quotes: %w", err)
	}

	// Convert to map[string]*float64
	quotes := make(map[string]*float64)
	for symbol, price := range result.Quotes {
		p := price
		quotes[symbol] = &p
	}

	return quotes, nil
}

// GetCurrentPrice gets the current price for a symbol
func (c *MicroserviceClient) GetCurrentPrice(
	symbol string,
	yahooSymbolOverride *string,
	maxRetries int,
) (*float64, error) {
	if maxRetries == 0 {
		maxRetries = 3 // default
	}

	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		url := fmt.Sprintf("/api/quotes/%s", symbol)
		if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
			url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
		}

		resp, err := c.get(url)
		if err != nil {
			lastErr = err
			if attempt < maxRetries-1 {
				waitTime := time.Duration(1<<uint(attempt)) * time.Second
				c.log.Warn().Err(err).
					Str("symbol", symbol).
					Int("attempt", attempt+1).
					Dur("wait", waitTime).
					Msg("Failed to get price, retrying")
				time.Sleep(waitTime)
				continue
			}
			break
		}

		// Parse response
		var quoteData struct {
			Symbol string  `json:"symbol"`
			Price  float64 `json:"price"`
		}
		if err := json.Unmarshal(resp.Data, &quoteData); err != nil {
			lastErr = fmt.Errorf("failed to parse quote data: %w", err)
			if attempt < maxRetries-1 {
				waitTime := time.Duration(1<<uint(attempt)) * time.Second
				time.Sleep(waitTime)
				continue
			}
			break
		}

		if quoteData.Price > 0 {
			return &quoteData.Price, nil
		}

		// Price was 0 or invalid, retry
		if attempt < maxRetries-1 {
			waitTime := time.Duration(1<<uint(attempt)) * time.Second
			c.log.Warn().
				Str("symbol", symbol).
				Int("attempt", attempt+1).
				Dur("wait", waitTime).
				Msg("Price was invalid, retrying")
			time.Sleep(waitTime)
		}
	}

	if lastErr != nil {
		return nil, fmt.Errorf("failed after %d attempts: %w", maxRetries, lastErr)
	}

	return nil, fmt.Errorf("failed to get valid price after %d attempts", maxRetries)
}

// HistoricalPricesResponse is the response for historical prices
type HistoricalPricesResponse struct {
	Symbol string           `json:"symbol"`
	Prices []HistoricalPrice `json:"prices"`
}

// GetHistoricalPrices fetches historical OHLCV data
func (c *MicroserviceClient) GetHistoricalPrices(
	symbol string,
	yahooSymbolOverride *string,
	period string,
) ([]HistoricalPrice, error) {
	url := fmt.Sprintf("/api/historical/%s?period=%s&interval=1d", symbol, period)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("&yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result HistoricalPricesResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse historical prices: %w", err)
	}

	return result.Prices, nil
}


// GetFundamentalData fetches fundamental analysis data
func (c *MicroserviceClient) GetFundamentalData(
	symbol string,
	yahooSymbolOverride *string,
) (*FundamentalData, error) {
	url := fmt.Sprintf("/api/fundamentals/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result FundamentalData
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse fundamental data: %w", err)
	}

	return &result, nil
}


// GetAnalystData fetches analyst recommendations and price targets
func (c *MicroserviceClient) GetAnalystData(
	symbol string,
	yahooSymbolOverride *string,
) (*AnalystData, error) {
	url := fmt.Sprintf("/api/analyst/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result AnalystData
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse analyst data: %w", err)
	}

	return &result, nil
}

// SecurityInfo represents security metadata
type SecurityInfo struct {
	Symbol            string  `json:"symbol"`
	Industry          *string `json:"industry"`
	Sector            *string `json:"sector"`
	Country           *string `json:"country"`
	FullExchangeName  *string `json:"full_exchange_name"`
	ProductType       *string `json:"product_type"`
	Name              *string `json:"name"`
}

// GetSecurityIndustry gets security industry/sector
// Returns just the industry string to match YahooClientInterface
func (c *MicroserviceClient) GetSecurityIndustry(
	symbol string,
	yahooSymbolOverride *string,
) (*string, error) {
	url := fmt.Sprintf("/api/security/industry/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result SecurityInfo
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse security industry: %w", err)
	}

	return result.Industry, nil
}

// GetSecurityCountryAndExchange gets security country and exchange
// Returns country and exchange strings to match YahooClientInterface
func (c *MicroserviceClient) GetSecurityCountryAndExchange(
	symbol string,
	yahooSymbolOverride *string,
) (*string, *string, error) {
	url := fmt.Sprintf("/api/security/country-exchange/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, nil, err
	}

	var result SecurityInfo
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, nil, fmt.Errorf("failed to parse security country/exchange: %w", err)
	}

	return result.Country, result.FullExchangeName, nil
}

// GetSecurityInfo gets comprehensive security information
func (c *MicroserviceClient) GetSecurityInfo(
	symbol string,
	yahooSymbolOverride *string,
) (*SecurityInfo, error) {
	url := fmt.Sprintf("/api/security/info/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	var result SecurityInfo
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse security info: %w", err)
	}

	return &result, nil
}

// HealthCheck checks the health of the Yahoo Finance microservice
func (c *MicroserviceClient) HealthCheck() (bool, error) {
	resp, err := c.get("/health")
	if err != nil {
		return false, err
	}
	return resp.Success, nil
}

