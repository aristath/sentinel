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
// It automatically falls back to direct client if microservice is unavailable
type MicroserviceClient struct {
	baseURL      string
	client       *http.Client
	log          zerolog.Logger
	directClient *Client // Fallback direct client
	useDirect    bool    // Flag to use direct client if microservice fails
}

// ServiceResponse is the standard response format from the microservice
type ServiceResponse struct {
	Success   bool            `json:"success"`
	Data      json.RawMessage `json:"data"`
	Error     *string         `json:"error"`
	Timestamp string          `json:"timestamp"`
}

// NewMicroserviceClient creates a new Yahoo Finance microservice client
// Automatically falls back to direct client if microservice is unavailable
func NewMicroserviceClient(baseURL string, log zerolog.Logger) *MicroserviceClient {
	// Create fallback direct client
	directClient := NewClient(log)
	
	return &MicroserviceClient{
		baseURL:      baseURL,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		log:          log.With().Str("client", "yahoo-microservice").Logger(),
		directClient: directClient,
		useDirect:    false, // Start with microservice, fall back if needed
	}
}

// checkMicroserviceHealth checks if the microservice is available
func (c *MicroserviceClient) checkMicroserviceHealth() bool {
	if c.useDirect {
		return false // Already using direct client
	}
	
	resp, err := c.get("/health")
	if err != nil {
		c.log.Warn().Err(err).Msg("Yahoo Finance microservice unavailable, falling back to direct client")
		c.useDirect = true
		return false
	}
	
	return resp.Success
}

// getClient returns the appropriate client (microservice or direct)
func (c *MicroserviceClient) getClient() FullClientInterface {
	if c.useDirect {
		return c.directClient
	}
	
	// Check health periodically (every 10 requests or on first use)
	// For simplicity, we'll check on first failure instead
	return c
}

// post makes a POST request to the microservice
func (c *MicroserviceClient) post(endpoint string, request interface{}) (*ServiceResponse, error) {
	if c.useDirect {
		// Delegate to direct client - but direct client doesn't have post method
		// So we'll handle this in individual methods
		return nil, fmt.Errorf("microservice unavailable, using direct client")
	}
	
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
		// Microservice unavailable, switch to direct client
		c.log.Warn().Err(err).Msg("Yahoo Finance microservice request failed, falling back to direct client")
		c.useDirect = true
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		// Non-200 response, might indicate microservice issue
		bodyBytes, _ := io.ReadAll(resp.Body)
		c.log.Warn().
			Int("status", resp.StatusCode).
			Str("body", string(bodyBytes)).
			Msg("Yahoo Finance microservice returned error, falling back to direct client")
		c.useDirect = true
		return nil, fmt.Errorf("microservice returned status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	return c.parseResponse(resp)
}

// get makes a GET request to the microservice
func (c *MicroserviceClient) get(endpoint string) (*ServiceResponse, error) {
	if c.useDirect {
		// Delegate to direct client - but direct client doesn't have get method
		// So we'll handle this in individual methods
		return nil, fmt.Errorf("microservice unavailable, using direct client")
	}
	
	url := c.baseURL + endpoint
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		// Microservice unavailable, switch to direct client
		c.log.Warn().Err(err).Msg("Yahoo Finance microservice request failed, falling back to direct client")
		c.useDirect = true
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		// Non-200 response, might indicate microservice issue
		bodyBytes, _ := io.ReadAll(resp.Body)
		c.log.Warn().
			Int("status", resp.StatusCode).
			Str("body", string(bodyBytes)).
			Msg("Yahoo Finance microservice returned error, falling back to direct client")
		c.useDirect = true
		return nil, fmt.Errorf("microservice returned status %d: %s", resp.StatusCode, string(bodyBytes))
	}

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
	if c.useDirect {
		return c.directClient.GetBatchQuotes(symbolOverrides)
	}
	
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
		// Fallback to direct client
		return c.directClient.GetBatchQuotes(symbolOverrides)
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
	if c.useDirect {
		return c.directClient.GetCurrentPrice(symbol, yahooSymbolOverride, maxRetries)
	}
	
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
			// Fallback to direct client on final failure
			return c.directClient.GetCurrentPrice(symbol, yahooSymbolOverride, maxRetries)
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
			// Fallback to direct client on final failure
			return c.directClient.GetCurrentPrice(symbol, yahooSymbolOverride, maxRetries)
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
		// Fallback to direct client
		return c.directClient.GetCurrentPrice(symbol, yahooSymbolOverride, maxRetries)
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
	if c.useDirect {
		return c.directClient.GetHistoricalPrices(symbol, yahooSymbolOverride, period)
	}
	
	url := fmt.Sprintf("/api/historical/%s?period=%s&interval=1d", symbol, period)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("&yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetHistoricalPrices(symbol, yahooSymbolOverride, period)
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
	if c.useDirect {
		return c.directClient.GetFundamentalData(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/fundamentals/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetFundamentalData(symbol, yahooSymbolOverride)
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
	if c.useDirect {
		return c.directClient.GetAnalystData(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/analyst/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetAnalystData(symbol, yahooSymbolOverride)
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
	if c.useDirect {
		return c.directClient.GetSecurityIndustry(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/security/industry/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetSecurityIndustry(symbol, yahooSymbolOverride)
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
	if c.useDirect {
		return c.directClient.GetSecurityCountryAndExchange(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/security/country-exchange/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetSecurityCountryAndExchange(symbol, yahooSymbolOverride)
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
	if c.useDirect {
		// Direct client doesn't have GetSecurityInfo, so we'll construct it from other methods
		industry, _ := c.directClient.GetSecurityIndustry(symbol, yahooSymbolOverride)
		country, exchange, _ := c.directClient.GetSecurityCountryAndExchange(symbol, yahooSymbolOverride)
		quoteType, _ := c.directClient.GetQuoteType(symbol, yahooSymbolOverride)
		
		var productType *string
		if quoteType != "" {
			qt := quoteType
			productType = &qt
		}
		
		return &SecurityInfo{
			Symbol:           symbol,
			Industry:         industry,
			Country:          country,
			FullExchangeName: exchange,
			ProductType:      productType,
		}, nil
	}
	
	url := fmt.Sprintf("/api/security/info/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}

	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client - construct SecurityInfo from direct client methods
		industry, _ := c.directClient.GetSecurityIndustry(symbol, yahooSymbolOverride)
		country, exchange, _ := c.directClient.GetSecurityCountryAndExchange(symbol, yahooSymbolOverride)
		quoteType, _ := c.directClient.GetQuoteType(symbol, yahooSymbolOverride)
		name, _ := c.directClient.GetQuoteName(symbol, yahooSymbolOverride)
		
		var productType *string
		if quoteType != "" {
			qt := quoteType
			productType = &qt
		}
		
		return &SecurityInfo{
			Symbol:           symbol,
			Industry:         industry,
			Country:          country,
			FullExchangeName: exchange,
			ProductType:      productType,
			Name:             name,
		}, nil
	}

	var result SecurityInfo
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse security info: %w", err)
	}

	return &result, nil
}

// LookupTickerFromISIN searches Yahoo Finance for a ticker symbol using an ISIN
func (c *MicroserviceClient) LookupTickerFromISIN(isin string) (string, error) {
	if c.useDirect {
		return c.directClient.LookupTickerFromISIN(isin)
	}
	
	url := fmt.Sprintf("/api/security/lookup-ticker/%s", isin)
	
	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.LookupTickerFromISIN(isin)
	}
	
	var result struct {
		ISIN   string `json:"isin"`
		Ticker string `json:"ticker"`
	}
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return "", fmt.Errorf("failed to parse lookup result: %w", err)
	}
	
	if result.Ticker == "" {
		return "", fmt.Errorf("no ticker found for ISIN: %s", isin)
	}
	
	return result.Ticker, nil
}

// GetQuoteName gets security name (longName or shortName) from Yahoo Finance
func (c *MicroserviceClient) GetQuoteName(
	symbol string,
	yahooSymbolOverride *string,
) (*string, error) {
	if c.useDirect {
		return c.directClient.GetQuoteName(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/security/quote-name/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}
	
	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetQuoteName(symbol, yahooSymbolOverride)
	}
	
	var result struct {
		Symbol string `json:"symbol"`
		Name   string `json:"name"`
	}
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse quote name: %w", err)
	}
	
	if result.Name == "" {
		return nil, nil
	}
	
	return &result.Name, nil
}

// GetQuoteType gets quote type from Yahoo Finance
func (c *MicroserviceClient) GetQuoteType(
	symbol string,
	yahooSymbolOverride *string,
) (string, error) {
	if c.useDirect {
		return c.directClient.GetQuoteType(symbol, yahooSymbolOverride)
	}
	
	url := fmt.Sprintf("/api/security/quote-type/%s", symbol)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		url += fmt.Sprintf("?yahoo_symbol=%s", *yahooSymbolOverride)
	}
	
	resp, err := c.get(url)
	if err != nil {
		// Fallback to direct client
		return c.directClient.GetQuoteType(symbol, yahooSymbolOverride)
	}
	
	var result struct {
		Symbol    string `json:"symbol"`
		QuoteType string `json:"quote_type"`
	}
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return "", fmt.Errorf("failed to parse quote type: %w", err)
	}
	
	return result.QuoteType, nil
}

// HealthCheck checks the health of the Yahoo Finance microservice
func (c *MicroserviceClient) HealthCheck() (bool, error) {
	if c.useDirect {
		return false, fmt.Errorf("using direct client, microservice unavailable")
	}
	
	resp, err := c.get("/health")
	if err != nil {
		return false, err
	}
	return resp.Success, nil
}
