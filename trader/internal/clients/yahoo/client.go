package yahoo

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// Client is a Yahoo Finance API client
type Client struct {
	client *http.Client
	log    zerolog.Logger
}

// NewClient creates a new Yahoo Finance client
func NewClient(log zerolog.Logger) *Client {
	return &Client{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log.With().Str("client", "yahoo").Logger(),
	}
}

// GetYahooSymbol converts a Tradernet symbol to Yahoo Finance symbol
// Faithful translation from Python: app/infrastructure/external/yahoo/symbol_converter.py
func GetYahooSymbol(symbol string, yahooSymbolOverride *string) string {
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		return *yahooSymbolOverride
	}

	// Convert Tradernet format to Yahoo format
	// Examples:
	// AAPL.US -> AAPL
	// GOOGL.US -> GOOGL
	// BASF.DE -> BASF.DE
	// 7203.JP -> 7203.T (Toyota)

	if strings.HasSuffix(symbol, ".US") {
		return strings.TrimSuffix(symbol, ".US")
	}

	if strings.HasSuffix(symbol, ".JP") {
		// Japanese stocks use .T suffix on Yahoo
		base := strings.TrimSuffix(symbol, ".JP")
		return base + ".T"
	}

	// Default: use as-is for European stocks
	return symbol
}

// yahooQuoteResponse represents the response from Yahoo Finance quote API
type yahooQuoteResponse struct {
	QuoteResponse struct {
		Result []map[string]interface{} `json:"result"`
		Error  interface{}              `json:"error"`
	} `json:"quoteResponse"`
}

// GetFundamentalData fetches fundamental analysis data
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_fundamental_data
func (c *Client) GetFundamentalData(symbol string, yahooSymbolOverride *string) (*FundamentalData, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote info: %w", err)
	}

	return &FundamentalData{
		Symbol:                   symbol,
		PERatio:                  getFloat64(info, "trailingPE"),
		ForwardPE:                getFloat64(info, "forwardPE"),
		PEGRatio:                 getFloat64(info, "pegRatio"),
		PriceToBook:              getFloat64(info, "priceToBook"),
		RevenueGrowth:            getFloat64(info, "revenueGrowth"),
		EarningsGrowth:           getFloat64(info, "earningsGrowth"),
		ProfitMargin:             getFloat64(info, "profitMargins"),
		OperatingMargin:          getFloat64(info, "operatingMargins"),
		ROE:                      getFloat64(info, "returnOnEquity"),
		DebtToEquity:             getFloat64(info, "debtToEquity"),
		CurrentRatio:             getFloat64(info, "currentRatio"),
		MarketCap:                getInt64(info, "marketCap"),
		DividendYield:            getFloat64(info, "dividendYield"),
		FiveYearAvgDividendYield: getFloat64(info, "fiveYearAvgDividendYield"),
	}, nil
}

// GetAnalystData fetches analyst recommendations and price targets
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_analyst_data
func (c *Client) GetAnalystData(symbol string, yahooSymbolOverride *string) (*AnalystData, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote info: %w", err)
	}

	// Get recommendation
	recommendation := getString(info, "recommendationKey", "hold")

	// Get price targets
	targetPrice := getFloat64OrZero(info, "targetMeanPrice")
	currentPrice := getFloat64OrZero(info, "currentPrice")
	if currentPrice == 0 {
		currentPrice = getFloat64OrZero(info, "regularMarketPrice")
	}

	// Calculate upside
	upsidePct := 0.0
	if currentPrice > 0 && targetPrice > 0 {
		upsidePct = ((targetPrice - currentPrice) / currentPrice) * 100
	}

	// Number of analysts
	numAnalysts := getIntOrZero(info, "numberOfAnalystOpinions")

	// Convert recommendation to score (0-1)
	recScores := map[string]float64{
		"strongBuy":  1.0,
		"buy":        0.8,
		"hold":       0.5,
		"sell":       0.2,
		"strongSell": 0.0,
	}
	recommendationScore := recScores[recommendation]
	if recommendationScore == 0 && recommendation != "strongSell" {
		recommendationScore = 0.5 // default to hold
	}

	return &AnalystData{
		Symbol:              symbol,
		Recommendation:      recommendation,
		TargetPrice:         targetPrice,
		CurrentPrice:        currentPrice,
		UpsidePct:           upsidePct,
		NumAnalysts:         numAnalysts,
		RecommendationScore: recommendationScore,
	}, nil
}

// GetSecurityIndustry gets security industry/sector from Yahoo Finance
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_security_industry
func (c *Client) GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote info: %w", err)
	}

	// Try industry first, then sector
	if industry := getString(info, "industry", ""); industry != "" {
		return &industry, nil
	}

	if sector := getString(info, "sector", ""); sector != "" {
		return &sector, nil
	}

	return nil, nil
}

// GetSecurityCountryAndExchange gets security country and exchange from Yahoo Finance
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_security_country_and_exchange
func (c *Client) GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get quote info: %w", err)
	}

	country := getStringPtr(info, "country")
	fullExchangeName := getStringPtr(info, "fullExchangeName")

	return country, fullExchangeName, nil
}

// GetQuoteName gets security name (longName or shortName) from Yahoo Finance
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_product_type()
// (which extracts name from ticker.info.get("longName", info.get("shortName", "")))
func (c *Client) GetQuoteName(symbol string, yahooSymbolOverride *string) (*string, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote info: %w", err)
	}

	// Try longName first, then shortName (matching Python: info.get("longName", info.get("shortName", "")))
	if longName := getStringPtr(info, "longName"); longName != nil {
		return longName, nil
	}

	if shortName := getStringPtr(info, "shortName"); shortName != nil {
		return shortName, nil
	}

	return nil, nil
}

// GetQuoteType gets quote type from Yahoo Finance
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_product_type()
// (which extracts quoteType from ticker.info.get("quoteType", ""))
func (c *Client) GetQuoteType(symbol string, yahooSymbolOverride *string) (string, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	info, err := c.getQuoteInfo(yfSymbol)
	if err != nil {
		return "", fmt.Errorf("failed to get quote info: %w", err)
	}

	quoteType := getString(info, "quoteType", "")
	return quoteType, nil
}

// GetCurrentPrice gets current security price with retry logic
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_current_price
func (c *Client) GetCurrentPrice(symbol string, yahooSymbolOverride *string, maxRetries int) (*float64, error) {
	if maxRetries == 0 {
		maxRetries = 3 // default
	}

	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		info, err := c.getQuoteInfo(yfSymbol)
		if err != nil {
			lastErr = err
			if attempt < maxRetries-1 {
				waitTime := time.Duration(1<<uint(attempt)) * time.Second // exponential backoff
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

		// Try currentPrice first, then regularMarketPrice
		if price := getFloat64(info, "currentPrice"); price != nil && *price > 0 {
			return price, nil
		}

		if price := getFloat64(info, "regularMarketPrice"); price != nil && *price > 0 {
			return price, nil
		}

		// Price was 0 or nil, retry
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

// GetBatchQuotes fetches current prices for multiple symbols efficiently
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_batch_quotes()
func (c *Client) GetBatchQuotes(symbolOverrides map[string]*string) (map[string]*float64, error) {
	if len(symbolOverrides) == 0 {
		return map[string]*float64{}, nil
	}

	// Build lists: yahoo symbols and mapping
	yahooSymbols := make([]string, 0, len(symbolOverrides))
	symbolMap := make(map[string]string) // yahoo -> tradernet

	for tradernetSymbol, yahooOverride := range symbolOverrides {
		yahooSymbol := GetYahooSymbol(tradernetSymbol, yahooOverride)
		yahooSymbols = append(yahooSymbols, yahooSymbol)
		symbolMap[yahooSymbol] = tradernetSymbol
	}

	// Batch symbols (Yahoo API limit: ~100 symbols per request)
	const batchSize = 100
	result := make(map[string]*float64)

	for i := 0; i < len(yahooSymbols); i += batchSize {
		end := i + batchSize
		if end > len(yahooSymbols) {
			end = len(yahooSymbols)
		}

		batch := yahooSymbols[i:end]
		batchQuotes, err := c.getBatchQuoteInfo(batch)
		if err != nil {
			c.log.Warn().Err(err).Int("batch_size", len(batch)).Msg("Failed to fetch batch quotes")
			// Don't fail the whole operation - continue with partial results
			continue
		}

		// Extract prices and map back to tradernet symbols
		for yahooSymbol, info := range batchQuotes {
			tradernetSymbol := symbolMap[yahooSymbol]

			// Try currentPrice first, then regularMarketPrice
			var price *float64
			if p := getFloat64(info, "currentPrice"); p != nil && *p > 0 {
				price = p
			} else if p := getFloat64(info, "regularMarketPrice"); p != nil && *p > 0 {
				price = p
			}

			if price != nil {
				result[tradernetSymbol] = price
			} else {
				c.log.Debug().
					Str("symbol", tradernetSymbol).
					Str("yahoo_symbol", yahooSymbol).
					Msg("No valid price data in batch response")
			}
		}
	}

	c.log.Info().
		Int("requested", len(symbolOverrides)).
		Int("fetched", len(result)).
		Msg("Batch quote fetch complete")

	return result, nil
}

// getBatchQuoteInfo fetches quote information for multiple symbols
func (c *Client) getBatchQuoteInfo(symbols []string) (map[string]map[string]interface{}, error) {
	if len(symbols) == 0 {
		return map[string]map[string]interface{}{}, nil
	}

	// Yahoo Finance query API endpoint
	baseURL := "https://query1.finance.yahoo.com/v7/finance/quote"

	// Join symbols with commas
	symbolsParam := strings.Join(symbols, ",")

	params := url.Values{}
	params.Add("symbols", symbolsParam)
	params.Add("fields", "symbol,regularMarketPrice,currentPrice")

	reqURL := baseURL + "?" + params.Encode()

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers to mimic browser
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	// Retry logic with exponential backoff
	var resp *http.Response
	var lastErr error
	maxRetries := 3

	for attempt := 0; attempt < maxRetries; attempt++ {
		resp, err = c.client.Do(req)
		if err == nil && resp.StatusCode == http.StatusOK {
			break
		}

		// Close failed response bodies to prevent resource leaks
		if resp != nil {
			resp.Body.Close()
		}

		lastErr = err
		if resp != nil && resp.StatusCode != http.StatusOK {
			lastErr = fmt.Errorf("status %d", resp.StatusCode)
		}

		if attempt < maxRetries-1 {
			waitTime := time.Duration(1<<uint(attempt)) * time.Second
			c.log.Warn().
				Err(lastErr).
				Int("attempt", attempt+1).
				Dur("wait", waitTime).
				Msg("Batch quote request failed, retrying")
			time.Sleep(waitTime)
		}
	}

	// Check if we got a successful response
	if resp == nil || resp.StatusCode != http.StatusOK {
		if lastErr != nil {
			return nil, fmt.Errorf("failed after %d attempts: %w", maxRetries, lastErr)
		}
		return nil, fmt.Errorf("failed after %d attempts with no error details", maxRetries)
	}

	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	var result yahooQuoteResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if result.QuoteResponse.Error != nil {
		return nil, fmt.Errorf("Yahoo Finance API error: %v", result.QuoteResponse.Error)
	}

	// Build map of symbol -> quote info
	quotes := make(map[string]map[string]interface{})
	for _, quote := range result.QuoteResponse.Result {
		if symbol, ok := quote["symbol"].(string); ok {
			quotes[symbol] = quote
		}
	}

	return quotes, nil
}

// getQuoteInfo fetches quote information from Yahoo Finance API
func (c *Client) getQuoteInfo(symbol string) (map[string]interface{}, error) {
	// Yahoo Finance query API endpoint
	baseURL := "https://query1.finance.yahoo.com/v7/finance/quote"

	params := url.Values{}
	params.Add("symbols", symbol)
	params.Add("fields", "symbol,regularMarketPrice,currentPrice,country,fullExchangeName,industry,sector,"+
		"trailingPE,forwardPE,pegRatio,priceToBook,revenueGrowth,earningsGrowth,profitMargins,"+
		"operatingMargins,returnOnEquity,debtToEquity,currentRatio,marketCap,dividendYield,"+
		"fiveYearAvgDividendYield,recommendationKey,targetMeanPrice,numberOfAnalystOpinions,"+
		"quoteType,longName,shortName")

	reqURL := baseURL + "?" + params.Encode()

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers to mimic browser
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch quote: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Yahoo Finance API returned status %d: %s", resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	var result yahooQuoteResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if result.QuoteResponse.Error != nil {
		return nil, fmt.Errorf("Yahoo Finance API error: %v", result.QuoteResponse.Error)
	}

	if len(result.QuoteResponse.Result) == 0 {
		return nil, fmt.Errorf("no quote data returned for symbol %s", symbol)
	}

	return result.QuoteResponse.Result[0], nil
}

// Helper functions to safely extract values from map

func getFloat64(m map[string]interface{}, key string) *float64 {
	if val, ok := m[key]; ok && val != nil {
		switch v := val.(type) {
		case float64:
			return &v
		case int:
			f := float64(v)
			return &f
		case int64:
			f := float64(v)
			return &f
		}
	}
	return nil
}

func getFloat64OrZero(m map[string]interface{}, key string) float64 {
	if val := getFloat64(m, key); val != nil {
		return *val
	}
	return 0
}

func getInt64(m map[string]interface{}, key string) *int64 {
	if val, ok := m[key]; ok && val != nil {
		switch v := val.(type) {
		case float64:
			i := int64(v)
			return &i
		case int:
			i := int64(v)
			return &i
		case int64:
			return &v
		}
	}
	return nil
}

func getIntOrZero(m map[string]interface{}, key string) int {
	if val, ok := m[key]; ok && val != nil {
		switch v := val.(type) {
		case float64:
			return int(v)
		case int:
			return v
		case int64:
			return int(v)
		}
	}
	return 0
}

func getString(m map[string]interface{}, key string, defaultVal string) string {
	if val, ok := m[key]; ok && val != nil {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return defaultVal
}

func getStringPtr(m map[string]interface{}, key string) *string {
	if val, ok := m[key]; ok && val != nil {
		if s, ok := val.(string); ok && s != "" {
			return &s
		}
	}
	return nil
}

// GetHistoricalPrices fetches historical OHLCV data from Yahoo Finance
// Faithful translation from Python: app/infrastructure/external/yahoo/data_fetchers.py -> get_historical_prices()
//
// Supports periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
func (c *Client) GetHistoricalPrices(symbol string, yahooSymbolOverride *string, period string) ([]HistoricalPrice, error) {
	yfSymbol := GetYahooSymbol(symbol, yahooSymbolOverride)

	// Yahoo Finance historical data endpoint
	// Uses chart API which returns JSON (more reliable than CSV download)
	baseURL := "https://query1.finance.yahoo.com/v8/finance/chart/" + url.QueryEscape(yfSymbol)

	// Convert period to interval and range
	// For daily data, use 1d interval
	params := url.Values{}
	params.Add("interval", "1d")
	params.Add("range", period)

	reqURL := baseURL + "?" + params.Encode()

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers to mimic browser
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch historical data: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Yahoo Finance API returned status %d: %s", resp.StatusCode, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// Parse response
	var result struct {
		Chart struct {
			Result []struct {
				Timestamp  []int64 `json:"timestamp"`
				Indicators struct {
					Quote []struct {
						Open   []float64 `json:"open"`
						High   []float64 `json:"high"`
						Low    []float64 `json:"low"`
						Close  []float64 `json:"close"`
						Volume []int64   `json:"volume"`
					} `json:"quote"`
					AdjClose []struct {
						AdjClose []float64 `json:"adjclose"`
					} `json:"adjclose"`
				} `json:"indicators"`
			} `json:"result"`
			Error interface{} `json:"error"`
		} `json:"chart"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if result.Chart.Error != nil {
		return nil, fmt.Errorf("Yahoo Finance API error: %v", result.Chart.Error)
	}

	if len(result.Chart.Result) == 0 {
		c.log.Warn().Str("symbol", symbol).Msg("No historical data returned")
		return []HistoricalPrice{}, nil
	}

	chartData := result.Chart.Result[0]
	timestamps := chartData.Timestamp
	if len(chartData.Indicators.Quote) == 0 {
		c.log.Warn().Str("symbol", symbol).Msg("No quote data in response")
		return []HistoricalPrice{}, nil
	}

	quote := chartData.Indicators.Quote[0]

	// Extract adj close if available
	var adjCloseData []float64
	if len(chartData.Indicators.AdjClose) > 0 {
		adjCloseData = chartData.Indicators.AdjClose[0].AdjClose
	}

	// Build price array
	var prices []HistoricalPrice
	for i := range timestamps {
		// Skip null values
		if i >= len(quote.Open) || i >= len(quote.High) || i >= len(quote.Low) || i >= len(quote.Close) {
			continue
		}

		// Yahoo sometimes returns null values
		if quote.Open[i] == 0 && quote.High[i] == 0 && quote.Low[i] == 0 && quote.Close[i] == 0 {
			continue
		}

		adjClose := quote.Close[i] // default to close
		if i < len(adjCloseData) && adjCloseData[i] != 0 {
			adjClose = adjCloseData[i]
		}

		volume := int64(0)
		if i < len(quote.Volume) {
			volume = quote.Volume[i]
		}

		prices = append(prices, HistoricalPrice{
			Date:     time.Unix(timestamps[i], 0),
			Open:     quote.Open[i],
			High:     quote.High[i],
			Low:      quote.Low[i],
			Close:    quote.Close[i],
			Volume:   volume,
			AdjClose: adjClose,
		})
	}

	c.log.Info().
		Str("symbol", symbol).
		Str("period", period).
		Int("count", len(prices)).
		Msg("Fetched historical prices")

	return prices, nil
}
