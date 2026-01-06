package yahoo

import (
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/rs/zerolog"
	"github.com/wnjoon/go-yfinance/pkg/lookup"
	"github.com/wnjoon/go-yfinance/pkg/models"
	"github.com/wnjoon/go-yfinance/pkg/multi"
	"github.com/wnjoon/go-yfinance/pkg/ticker"
)

// ISIN validation pattern (12 characters: 2 letters, 9 alphanumeric, 1 digit)
var isinPattern = regexp.MustCompile(`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`)

// isISIN checks if identifier is a valid ISIN
func isISIN(identifier string) bool {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))
	if len(identifier) != 12 {
		return false
	}
	return isinPattern.MatchString(identifier)
}

// NativeClient implements FullClientInterface using go-yfinance library
type NativeClient struct {
	log zerolog.Logger
}

// NewNativeClient creates a new native Yahoo Finance client
func NewNativeClient(log zerolog.Logger) *NativeClient {
	return &NativeClient{
		log: log.With().Str("client", "yahoo-native").Logger(),
	}
}

// tradernetToYahoo converts Tradernet symbol to Yahoo format
// This is a fallback when ISIN is not available.
// For .US securities, strips the suffix.
// For .JP securities, converts to .T (Tokyo Exchange).
// For .GR securities, converts to .AT (Athens Exchange).
// Other suffixes pass through unchanged.
func tradernetToYahoo(tradernetSymbol string) string {
	symbol := strings.ToUpper(tradernetSymbol)

	// US securities: strip .US suffix
	if strings.HasSuffix(symbol, ".US") {
		return symbol[:len(symbol)-3]
	}

	// Japanese securities: .JP -> .T
	if strings.HasSuffix(symbol, ".JP") {
		return symbol[:len(symbol)-3] + ".T"
	}

	// Greek securities: .GR -> .AT (Athens Exchange)
	if strings.HasSuffix(symbol, ".GR") {
		return symbol[:len(symbol)-3] + ".AT"
	}

	// Everything else passes through unchanged
	return symbol
}

// resolveSymbol resolves the Yahoo symbol to use, prioritizing yahooSymbolOverride
// If override is an ISIN, it will be looked up to get the ticker symbol
func (c *NativeClient) resolveSymbol(symbol string, yahooSymbolOverride *string) (string, error) {
	// Primary: Use override if provided (often an ISIN)
	if yahooSymbolOverride != nil && *yahooSymbolOverride != "" {
		override := *yahooSymbolOverride

		// If override is an ISIN, look it up first
		if isISIN(override) {
			ticker, err := c.LookupTickerFromISIN(override)
			if err != nil {
				c.log.Warn().Err(err).Str("isin", override).Msg("Failed to lookup ISIN, using ISIN directly")
				// Fall through to use ISIN directly (may or may not work with go-yfinance)
				return override, nil
			}
			return ticker, nil
		}

		// Not an ISIN, use directly
		return override, nil
	}

	// Fallback: Simple symbol conversion
	return tradernetToYahoo(symbol), nil
}

// GetBatchQuotes fetches current prices for multiple symbols efficiently
func (c *NativeClient) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if len(symbolMap) == 0 {
		return make(map[string]*float64), nil
	}

	// Convert symbol map to Yahoo symbols
	symbols := make([]string, 0, len(symbolMap))
	symbolToTradernet := make(map[string]string) // yahooSymbol -> tradernetSymbol

	for tradernetSymbol, override := range symbolMap {
		yahooSymbol, err := c.resolveSymbol(tradernetSymbol, override)
		if err != nil {
			c.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Failed to resolve symbol, skipping")
			continue
		}
		symbols = append(symbols, yahooSymbol)
		symbolToTradernet[yahooSymbol] = tradernetSymbol
	}

	// Use multi.Download for batch operations
	params := models.DefaultDownloadParams()
	params.Symbols = symbols
	params.Period = "5d" // Get last 5 days to ensure we have recent data
	params.Interval = "1d"

	result, err := multi.Download(symbols, &params)
	if err != nil {
		return nil, fmt.Errorf("failed to download batch quotes: %w", err)
	}

	// Extract prices from results
	quotes := make(map[string]*float64)
	for yahooSymbol, tradernetSymbol := range symbolToTradernet {
		if bars, ok := result.Data[yahooSymbol]; ok && len(bars) > 0 {
			// Get last close price
			lastBar := bars[len(bars)-1]
			price := lastBar.Close
			quotes[tradernetSymbol] = &price
		} else if err, ok := result.Errors[yahooSymbol]; ok {
			c.log.Warn().Err(err).Str("symbol", yahooSymbol).Msg("Failed to get quote for symbol")
			// Continue with other symbols
		}
	}

	return quotes, nil
}

// GetCurrentPrice gets the current price for a symbol
func (c *NativeClient) GetCurrentPrice(symbol string, yahooSymbolOverride *string, maxRetries int) (*float64, error) {
	if maxRetries == 0 {
		maxRetries = 3 // default
	}

	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		t, err := ticker.New(yahooSymbol)
		if err != nil {
			lastErr = fmt.Errorf("failed to create ticker: %w", err)
			if attempt < maxRetries-1 {
				waitTime := time.Duration(1<<uint(attempt)) * time.Second
				c.log.Warn().Err(err).Str("symbol", symbol).Int("attempt", attempt+1).Dur("wait", waitTime).Msg("Retrying")
				time.Sleep(waitTime)
				continue
			}
			return nil, lastErr
		}
		defer t.Close()

		// Try Quote first (faster)
		quote, err := t.Quote()
		if err == nil && quote != nil {
			price := quote.RegularMarketPrice
			if price > 0 {
				return &price, nil
			}
			// Try pre/post market prices
			if quote.PreMarketPrice > 0 {
				preMarketPrice := quote.PreMarketPrice
				return &preMarketPrice, nil
			}
			if quote.PostMarketPrice > 0 {
				postMarketPrice := quote.PostMarketPrice
				return &postMarketPrice, nil
			}
		}

		// Fallback to Info
		info, err := t.Info()
		if err == nil && info != nil {
			if info.CurrentPrice > 0 {
				price := info.CurrentPrice
				return &price, nil
			}
			if info.RegularMarketPreviousClose > 0 {
				price := info.RegularMarketPreviousClose
				return &price, nil
			}
		}

		// If we got here, price was 0 or invalid
		if attempt < maxRetries-1 {
			waitTime := time.Duration(1<<uint(attempt)) * time.Second
			c.log.Warn().Str("symbol", symbol).Int("attempt", attempt+1).Dur("wait", waitTime).Msg("Price was invalid, retrying")
			time.Sleep(waitTime)
			continue
		}

		lastErr = fmt.Errorf("failed to get valid price after %d attempts", maxRetries)
	}

	return nil, lastErr
}

// GetHistoricalPrices fetches historical OHLCV data
func (c *NativeClient) GetHistoricalPrices(symbol string, yahooSymbolOverride *string, period string) ([]HistoricalPrice, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	params := models.HistoryParams{
		Period:     period,
		Interval:   "1d",
		AutoAdjust: true,
	}

	bars, err := t.History(params)
	if err != nil {
		return nil, fmt.Errorf("failed to get historical prices: %w", err)
	}

	// Convert []models.Bar to []HistoricalPrice
	historicalPrices := make([]HistoricalPrice, 0, len(bars))
	for _, bar := range bars {
		historicalPrices = append(historicalPrices, HistoricalPrice{
			Date:     bar.Date,
			Open:     bar.Open,
			High:     bar.High,
			Low:      bar.Low,
			Close:    bar.Close,
			Volume:   int64(bar.Volume),
			AdjClose: bar.AdjClose,
		})
	}

	return historicalPrices, nil
}

// GetFundamentalData fetches fundamental analysis data
func (c *NativeClient) GetFundamentalData(symbol string, yahooSymbolOverride *string) (*FundamentalData, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	info, err := t.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get info: %w", err)
	}

	// Map fields from models.Info to FundamentalData
	fundamental := &FundamentalData{
		Symbol: symbol,
	}

	// Map all fields (use pointers for optional fields)
	// IMPORTANT: Copy values to local variables before taking addresses to avoid
	// cross-contamination if the ticker library reuses internal buffers
	if info.TrailingPE > 0 {
		trailingPE := info.TrailingPE
		fundamental.PERatio = &trailingPE
	}
	if info.ForwardPE > 0 {
		forwardPE := info.ForwardPE
		fundamental.ForwardPE = &forwardPE
	}
	if info.PegRatio > 0 {
		pegRatio := info.PegRatio
		fundamental.PEGRatio = &pegRatio
	}
	if info.PriceToBook > 0 {
		priceToBook := info.PriceToBook
		fundamental.PriceToBook = &priceToBook
	}
	if info.RevenueGrowth != 0 {
		revenueGrowth := info.RevenueGrowth
		fundamental.RevenueGrowth = &revenueGrowth
	}
	if info.EarningsGrowth != 0 {
		earningsGrowth := info.EarningsGrowth
		fundamental.EarningsGrowth = &earningsGrowth
	}
	if info.ProfitMargins > 0 {
		profitMargins := info.ProfitMargins
		fundamental.ProfitMargin = &profitMargins
	}
	if info.OperatingMargins > 0 {
		operatingMargins := info.OperatingMargins
		fundamental.OperatingMargin = &operatingMargins
	}
	if info.ReturnOnEquity > 0 {
		returnOnEquity := info.ReturnOnEquity
		fundamental.ROE = &returnOnEquity
	}
	if info.DebtToEquity > 0 {
		debtToEquity := info.DebtToEquity
		fundamental.DebtToEquity = &debtToEquity
	}
	if info.CurrentRatio > 0 {
		currentRatio := info.CurrentRatio
		fundamental.CurrentRatio = &currentRatio
	}
	if info.MarketCap > 0 {
		marketCap := info.MarketCap
		fundamental.MarketCap = &marketCap
	}
	if info.DividendYield > 0 {
		dividendYield := info.DividendYield
		fundamental.DividendYield = &dividendYield
	}
	if info.FiveYearAvgDividendYield > 0 {
		fiveYearAvgDividendYield := info.FiveYearAvgDividendYield
		fundamental.FiveYearAvgDividendYield = &fiveYearAvgDividendYield
	}

	return fundamental, nil
}

// GetAnalystData fetches analyst recommendations and price targets
func (c *NativeClient) GetAnalystData(symbol string, yahooSymbolOverride *string) (*AnalystData, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	// Get price targets
	priceTarget, err := t.AnalystPriceTargets()
	if err != nil {
		return nil, fmt.Errorf("failed to get price targets: %w", err)
	}

	// Get recommendations
	recommendations, err := t.Recommendations()
	if err != nil {
		return nil, fmt.Errorf("failed to get recommendations: %w", err)
	}

	// Get current price
	info, err := t.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get info: %w", err)
	}

	currentPrice := priceTarget.Current
	if currentPrice == 0 && info != nil {
		currentPrice = info.CurrentPrice
	}
	if currentPrice == 0 && info != nil {
		currentPrice = info.RegularMarketPreviousClose
	}

	// Get latest recommendation
	recommendationKey := priceTarget.RecommendationKey
	if recommendationKey == "" {
		recommendationKey = "hold" // default
	}

	// Get latest recommendation from trend if available
	if recommendations != nil && len(recommendations.Trend) > 0 {
		// Use the first (most recent) recommendation period
		latest := recommendations.Trend[0]
		// Determine recommendation from counts
		if latest.StrongBuy > 0 {
			recommendationKey = "strongBuy"
		} else if latest.Buy > 0 {
			recommendationKey = "buy"
		} else if latest.Hold > 0 {
			recommendationKey = "hold"
		} else if latest.Sell > 0 {
			recommendationKey = "sell"
		} else if latest.StrongSell > 0 {
			recommendationKey = "strongSell"
		}
	}

	// Calculate upside percentage
	targetPrice := priceTarget.Mean
	if targetPrice == 0 {
		targetPrice = priceTarget.Median
	}
	upsidePct := 0.0
	if currentPrice > 0 && targetPrice > 0 {
		upsidePct = ((targetPrice - currentPrice) / currentPrice) * 100
	}

	// Calculate recommendation score
	recScores := map[string]float64{
		"strongBuy":  1.0,
		"buy":        0.8,
		"hold":       0.5,
		"sell":       0.2,
		"strongSell": 0.0,
	}
	recommendationScore := recScores[strings.ToLower(recommendationKey)]
	if recommendationScore == 0 && strings.ToLower(recommendationKey) != "strongsell" {
		recommendationScore = 0.5 // default to hold
	}

	return &AnalystData{
		Symbol:              symbol,
		Recommendation:      recommendationKey,
		TargetPrice:         targetPrice,
		CurrentPrice:        currentPrice,
		UpsidePct:           upsidePct,
		NumAnalysts:         priceTarget.NumberOfAnalysts,
		RecommendationScore: recommendationScore,
	}, nil
}

// GetSecurityIndustry gets security industry/sector
func (c *NativeClient) GetSecurityIndustry(symbol string, yahooSymbolOverride *string) (*string, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	info, err := t.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get info: %w", err)
	}

	if info.Industry != "" {
		industry := info.Industry
		return &industry, nil
	}

	return nil, nil
}

// GetSecurityCountryAndExchange gets security country and exchange
func (c *NativeClient) GetSecurityCountryAndExchange(symbol string, yahooSymbolOverride *string) (*string, *string, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	info, err := t.Info()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to get info: %w", err)
	}

	var country *string
	var exchange *string

	if info.Country != "" {
		countryVal := info.Country
		country = &countryVal
	}

	// Use Exchange from Info (full exchange name may not be available in Info struct)
	if info.Exchange != "" {
		exchangeVal := info.Exchange
		exchange = &exchangeVal
	}

	return country, exchange, nil
}

// GetQuoteName gets security name (longName or shortName)
func (c *NativeClient) GetQuoteName(symbol string, yahooSymbolOverride *string) (*string, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return nil, fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	info, err := t.Info()
	if err != nil {
		return nil, fmt.Errorf("failed to get info: %w", err)
	}

	if info.LongName != "" {
		longName := info.LongName
		return &longName, nil
	}
	if info.ShortName != "" {
		shortName := info.ShortName
		return &shortName, nil
	}

	return nil, nil
}

// GetQuoteType gets quote type from Yahoo Finance
func (c *NativeClient) GetQuoteType(symbol string, yahooSymbolOverride *string) (string, error) {
	yahooSymbol, err := c.resolveSymbol(symbol, yahooSymbolOverride)
	if err != nil {
		return "", fmt.Errorf("failed to resolve symbol: %w", err)
	}

	t, err := ticker.New(yahooSymbol)
	if err != nil {
		return "", fmt.Errorf("failed to create ticker: %w", err)
	}
	defer t.Close()

	info, err := t.Info()
	if err != nil {
		return "", fmt.Errorf("failed to get info: %w", err)
	}

	return info.QuoteType, nil
}

// LookupTickerFromISIN searches Yahoo Finance for a ticker symbol using an ISIN
func (c *NativeClient) LookupTickerFromISIN(isin string) (string, error) {
	if isin == "" {
		return "", fmt.Errorf("ISIN cannot be empty")
	}

	// Use lookup API to get equity results directly
	lookupClient, err := lookup.New(isin)
	if err != nil {
		return "", fmt.Errorf("failed to create lookup client: %w", err)
	}
	defer lookupClient.Close()

	// Get stock results (filters for equity)
	results, err := lookupClient.Stock(1)
	if err != nil {
		return "", fmt.Errorf("failed to lookup ISIN: %w", err)
	}

	if len(results) == 0 {
		return "", fmt.Errorf("no ticker found for ISIN: %s", isin)
	}

	// Return first result's symbol
	return results[0].Symbol, nil
}
