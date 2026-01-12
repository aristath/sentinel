// Package openfigi provides a client for Bloomberg's OpenFIGI API.
// OpenFIGI is a free service for mapping securities identifiers like ISINs
// to exchange-specific ticker symbols.
package openfigi

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/aristath/sentinel/internal/clientdata"
	"github.com/rs/zerolog"
)

const (
	defaultBaseURL = "https://api.openfigi.com/v3"
	// Rate limits: 25 requests/minute without API key, 25,000 with key
	// (Actual rate limiting handled in the client implementation)
)

// MappingRequest represents a request to the OpenFIGI mapping API.
type MappingRequest struct {
	IDType    string `json:"idType"`
	IDValue   string `json:"idValue"`
	ExchCode  string `json:"exchCode,omitempty"`
	MarketSec string `json:"marketSecDes,omitempty"` // e.g., "Equity"
	SecType2  string `json:"securityType2,omitempty"`
	Currency  string `json:"currency,omitempty"`
}

// MappingResult represents a single result from the OpenFIGI API.
type MappingResult struct {
	FIGI            string `json:"figi"`
	Ticker          string `json:"ticker"`
	ExchCode        string `json:"exchCode"`        // Exchange code (e.g., "US", "LN", "GR", "GA")
	Name            string `json:"name"`            // Security name
	MarketSector    string `json:"marketSector"`    // e.g., "Equity"
	SecurityType    string `json:"securityType"`    // e.g., "Common Stock"
	CompositeFIGI   string `json:"compositeFIGI"`   // Composite FIGI
	ShareClassFIGI  string `json:"shareClassFIGI"`  // Share class FIGI
	UniqueID        string `json:"uniqueID"`        // Unique identifier
	SecurityType2   string `json:"securityType2"`   // Secondary security type
	MarketSectorDes string `json:"marketSectorDes"` // Market sector description
}

// MappingResponse represents a response item from the OpenFIGI API.
type MappingResponse struct {
	Data    []MappingResult `json:"data,omitempty"`
	Error   string          `json:"error,omitempty"`
	Warning string          `json:"warning,omitempty"`
}

// Client is the OpenFIGI API client.
type Client struct {
	baseURL    string
	apiKey     string // Optional - increases rate limits
	httpClient *http.Client
	log        zerolog.Logger
	cacheRepo  *clientdata.Repository
}

// NewClient creates a new OpenFIGI client.
// apiKey is optional but recommended for higher rate limits.
// cacheRepo is optional - if nil, caching is disabled.
func NewClient(apiKey string, cacheRepo *clientdata.Repository, log zerolog.Logger) *Client {
	return &Client{
		baseURL: defaultBaseURL,
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log:       log.With().Str("component", "openfigi").Logger(),
		cacheRepo: cacheRepo,
	}
}

// LookupISIN maps an ISIN to ticker symbol(s).
// Returns multiple results if the security trades on multiple exchanges.
// If the API fails, returns stale cached data if available (stale data > no data).
func (c *Client) LookupISIN(isin string) ([]MappingResult, error) {
	// Check persistent cache for fresh data
	if results, ok := c.getFromCache(isin); ok {
		c.log.Debug().Str("isin", isin).Msg("OpenFIGI cache hit")
		return results, nil
	}

	// Make request
	requests := []MappingRequest{
		{
			IDType:  "ID_ISIN",
			IDValue: isin,
		},
	}

	responses, err := c.doRequest(requests)
	if err != nil {
		// API failed - try to get stale cached data as fallback
		if staleResults, ok := c.getStaleFromCache(isin); ok {
			c.log.Warn().
				Err(err).
				Str("isin", isin).
				Msg("API failed, using stale cached data")
			return staleResults, nil
		}
		return nil, err
	}

	if len(responses) == 0 {
		return nil, nil
	}

	results := responses[0].Data

	// Cache results persistently
	c.setCache(isin, results)

	return results, nil
}

// LookupISINForExchange maps an ISIN to ticker for a specific exchange.
func (c *Client) LookupISINForExchange(isin string, exchCode string) (*MappingResult, error) {
	// For exchange-specific lookups, we first check the full ISIN lookup
	// to avoid duplicate API calls. Then filter by exchange.
	results, err := c.LookupISIN(isin)
	if err != nil {
		return nil, err
	}

	// Filter results by exchange code
	for i := range results {
		if results[i].ExchCode == exchCode {
			return &results[i], nil
		}
	}

	return nil, nil
}

// BatchLookup looks up multiple ISINs in a single request.
// Returns a map of ISIN -> []MappingResult.
// If the API fails, returns stale cached data for any ISINs that have it.
func (c *Client) BatchLookup(isins []string) (map[string][]MappingResult, error) {
	results := make(map[string][]MappingResult)

	// Check cache first
	uncachedISINs := make([]string, 0)
	for _, isin := range isins {
		if cached, ok := c.getFromCache(isin); ok {
			results[isin] = cached
		} else {
			uncachedISINs = append(uncachedISINs, isin)
		}
	}

	// If all were cached, return early
	if len(uncachedISINs) == 0 {
		c.log.Debug().Int("count", len(isins)).Msg("All ISINs found in cache")
		return results, nil
	}

	c.log.Debug().
		Int("total", len(isins)).
		Int("cached", len(isins)-len(uncachedISINs)).
		Int("to_fetch", len(uncachedISINs)).
		Msg("BatchLookup cache stats")

	// Build requests for uncached ISINs
	requests := make([]MappingRequest, len(uncachedISINs))
	for i, isin := range uncachedISINs {
		requests[i] = MappingRequest{
			IDType:  "ID_ISIN",
			IDValue: isin,
		}
	}

	responses, err := c.doRequest(requests)
	if err != nil {
		// API failed - try to get stale cached data as fallback for uncached ISINs
		staleCount := 0
		for _, isin := range uncachedISINs {
			if stale, ok := c.getStaleFromCache(isin); ok {
				results[isin] = stale
				staleCount++
			}
		}
		if staleCount > 0 {
			c.log.Warn().
				Err(err).
				Int("stale_count", staleCount).
				Int("missing", len(uncachedISINs)-staleCount).
				Msg("API failed, using stale cached data for some ISINs")
		}
		// If we have some results (fresh + stale), return them even though API failed
		if len(results) > 0 {
			return results, nil
		}
		return nil, err
	}

	// Map responses back to ISINs and cache them
	for i, resp := range responses {
		if i < len(uncachedISINs) {
			isin := uncachedISINs[i]
			results[isin] = resp.Data
			c.setCache(isin, resp.Data)
		}
	}

	return results, nil
}

// doRequest performs the HTTP request to the OpenFIGI API.
func (c *Client) doRequest(requests []MappingRequest) ([]MappingResponse, error) {
	body, err := json.Marshal(requests)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/mapping", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		req.Header.Set("X-OPENFIGI-APIKEY", c.apiKey)
	}

	c.log.Debug().Int("count", len(requests)).Msg("Making OpenFIGI request")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenFIGI API error: status %d, body: %s", resp.StatusCode, string(bodyBytes))
	}

	var responses []MappingResponse
	if err := json.NewDecoder(resp.Body).Decode(&responses); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return responses, nil
}

// getFromCache retrieves cached results if they exist and haven't expired.
func (c *Client) getFromCache(isin string) ([]MappingResult, bool) {
	if c.cacheRepo == nil {
		return nil, false
	}

	data, err := c.cacheRepo.GetIfFresh("openfigi", isin)
	if err != nil {
		c.log.Warn().Err(err).Str("isin", isin).Msg("Failed to get from cache")
		return nil, false
	}
	if data == nil {
		return nil, false
	}

	var results []MappingResult
	if err := json.Unmarshal(data, &results); err != nil {
		c.log.Warn().Err(err).Str("isin", isin).Msg("Failed to unmarshal cached data")
		return nil, false
	}

	return results, true
}

// getStaleFromCache retrieves cached results even if expired.
// Use this as a fallback when API calls fail - stale data is better than no data.
func (c *Client) getStaleFromCache(isin string) ([]MappingResult, bool) {
	if c.cacheRepo == nil {
		return nil, false
	}

	data, err := c.cacheRepo.Get("openfigi", isin)
	if err != nil {
		c.log.Warn().Err(err).Str("isin", isin).Msg("Failed to get stale data from cache")
		return nil, false
	}
	if data == nil {
		return nil, false
	}

	var results []MappingResult
	if err := json.Unmarshal(data, &results); err != nil {
		c.log.Warn().Err(err).Str("isin", isin).Msg("Failed to unmarshal stale cached data")
		return nil, false
	}

	return results, true
}

// setCache stores results in the persistent cache.
func (c *Client) setCache(isin string, results []MappingResult) {
	if c.cacheRepo == nil {
		return
	}

	if err := c.cacheRepo.Store("openfigi", isin, results, clientdata.TTLOpenFIGI); err != nil {
		c.log.Warn().Err(err).Str("isin", isin).Msg("Failed to cache OpenFIGI results")
	}
}

// ExchangeCodeMappings maps OpenFIGI exchange codes to internal exchange codes.
// OpenFIGI uses Bloomberg exchange codes.
var ExchangeCodeMappings = map[string]string{
	// Americas
	"US": "NYSE", // United States (can be NYSE or NASDAQ)
	"CT": "TSX",  // Canada - Toronto
	"BZ": "B3",   // Brazil
	"MX": "BMV",  // Mexico

	// Europe
	"LN": "LSE",   // London
	"GR": "XETRA", // Germany (Xetra)
	"FP": "PAR",   // France (Paris)
	"NA": "AMS",   // Netherlands (Amsterdam)
	"IM": "MIL",   // Italy (Milan)
	"SM": "BME",   // Spain (Madrid)
	"SW": "SIX",   // Switzerland
	"GA": "ATH",   // Greece (Athens)

	// Asia-Pacific
	"HK": "HKG",  // Hong Kong
	"JT": "TYO",  // Japan (Tokyo)
	"SP": "SGX",  // Singapore
	"AU": "ASX",  // Australia
	"KS": "KRX",  // South Korea
	"TT": "TWSE", // Taiwan
	"IB": "BSE",  // India - Bombay
	"IN": "NSE",  // India - NSE
}

// GetInternalExchangeCode converts an OpenFIGI exchange code to an internal code.
func GetInternalExchangeCode(figiCode string) string {
	if internal, ok := ExchangeCodeMappings[figiCode]; ok {
		return internal
	}
	return figiCode
}

// TickerLookupResult represents a result from ticker lookup including the ISIN.
type TickerLookupResult struct {
	Ticker   string
	ExchCode string
	Name     string
	ISIN     string // Populated from compositeFIGI or direct lookup
}

// LookupByTicker attempts to find security information by ticker symbol.
// exchCode is optional (e.g., "US", "LN", "GA").
// Note: OpenFIGI doesn't directly return ISIN, but we can get it from the compositeFIGI.
// Note: Ticker lookups are NOT cached as they don't have a stable key (ISIN).
func (c *Client) LookupByTicker(ticker string, exchCode string) (*TickerLookupResult, error) {
	// Make request using TICKER id type
	req := MappingRequest{
		IDType:  "TICKER",
		IDValue: ticker,
	}
	if exchCode != "" {
		req.ExchCode = exchCode
	}

	responses, err := c.doRequest([]MappingRequest{req})
	if err != nil {
		return nil, err
	}

	if len(responses) == 0 || len(responses[0].Data) == 0 {
		return nil, nil
	}

	result := responses[0].Data[0]

	// Note: OpenFIGI returns FIGI identifiers, not ISINs directly
	// The compositeFIGI can potentially be used to look up the ISIN
	// but this requires additional mapping
	return &TickerLookupResult{
		Ticker:   result.Ticker,
		ExchCode: result.ExchCode,
		Name:     result.Name,
		ISIN:     "", // OpenFIGI doesn't provide ISIN in ticker lookup
	}, nil
}
