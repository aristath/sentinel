package alphavantage

import (
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestNewClient tests client creation.
func TestNewClient(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	assert.NotNil(t, client)
	assert.Equal(t, "test-key", client.apiKey)
	assert.Equal(t, 25, client.GetRemainingRequests())
}

// TestRateLimiting tests the rate limiting functionality.
func TestRateLimiting(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	// Simulate using all requests
	for i := 0; i < 25; i++ {
		remaining := client.GetRemainingRequests()
		assert.Equal(t, 25-i, remaining)
		err := client.checkRateLimit()
		require.NoError(t, err)
	}

	// 26th request should fail
	err := client.checkRateLimit()
	assert.Error(t, err)
	assert.IsType(t, ErrRateLimitExceeded{}, err)
}

// TestResetDailyCounter tests counter reset.
func TestResetDailyCounter(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	// Use some requests
	for i := 0; i < 10; i++ {
		_ = client.checkRateLimit()
	}
	assert.Equal(t, 15, client.GetRemainingRequests())

	// Reset
	client.ResetDailyCounter()
	assert.Equal(t, 25, client.GetRemainingRequests())
}

// TestCaching tests the cache functionality.
func TestCaching(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	// Set a cache entry
	testData := "test data"
	client.setCache("test-key", testData, time.Hour)

	// Retrieve it
	cached, ok := client.getFromCache("test-key")
	assert.True(t, ok)
	assert.Equal(t, testData, cached)

	// Non-existent key
	_, ok = client.getFromCache("non-existent")
	assert.False(t, ok)
}

// TestCacheExpiration tests cache expiration.
func TestCacheExpiration(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	// Set with very short TTL
	client.setCache("test-key", "test data", time.Millisecond)

	// Wait for expiration
	time.Sleep(5 * time.Millisecond)

	// Should be expired
	_, ok := client.getFromCache("test-key")
	assert.False(t, ok)
}

// TestClearCache tests cache clearing.
func TestClearCache(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	client.setCache("key1", "data1", time.Hour)
	client.setCache("key2", "data2", time.Hour)

	client.ClearCache()

	_, ok1 := client.getFromCache("key1")
	_, ok2 := client.getFromCache("key2")
	assert.False(t, ok1)
	assert.False(t, ok2)
}

// TestBuildCacheKey tests cache key generation.
func TestBuildCacheKey(t *testing.T) {
	tests := []struct {
		name     string
		function string
		params   map[string]string
	}{
		{
			name:     "Simple function",
			function: "OVERVIEW",
			params:   map[string]string{"symbol": "IBM"},
		},
		{
			name:     "Multiple params",
			function: "TIME_SERIES_DAILY",
			params: map[string]string{
				"symbol":     "AAPL",
				"outputsize": "full",
			},
		},
		{
			name:     "With apikey excluded",
			function: "SMA",
			params: map[string]string{
				"symbol": "MSFT",
				"apikey": "secret", // Should be excluded
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key := buildCacheKey(tt.function, tt.params)
			assert.Contains(t, key, tt.function)
			assert.NotContains(t, key, "apikey=")
		})
	}
}

// TestParseFloat64 tests float parsing.
func TestParseFloat64(t *testing.T) {
	tests := []struct {
		input    string
		expected float64
	}{
		{"123.45", 123.45},
		{"0", 0},
		{"None", 0},
		{"", 0},
		{"null", 0},
		{"-", 0},
		{"50.5%", 50.5},
		{"invalid", 0},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseFloat64(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestParseFloat64Ptr tests nullable float parsing.
func TestParseFloat64Ptr(t *testing.T) {
	tests := []struct {
		input    string
		isNil    bool
		expected float64
	}{
		{"123.45", false, 123.45},
		{"None", true, 0},
		{"", true, 0},
		{"null", true, 0},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseFloat64Ptr(tt.input)
			if tt.isNil {
				assert.Nil(t, result)
			} else {
				require.NotNil(t, result)
				assert.Equal(t, tt.expected, *result)
			}
		})
	}
}

// TestParseInt64 tests integer parsing.
func TestParseInt64(t *testing.T) {
	tests := []struct {
		input    string
		expected int64
	}{
		{"12345", 12345},
		{"0", 0},
		{"None", 0},
		{"", 0},
		{"1.5E10", 15000000000},
		{"123.45", 123},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseInt64(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestParseDate tests date parsing.
func TestParseDate(t *testing.T) {
	tests := []struct {
		input string
		year  int
		month time.Month
		day   int
	}{
		{"2024-01-15", 2024, time.January, 15},
		{"2023-12-31", 2023, time.December, 31},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseDate(tt.input)
			assert.Equal(t, tt.year, result.Year())
			assert.Equal(t, tt.month, result.Month())
			assert.Equal(t, tt.day, result.Day())
		})
	}
}

// TestParseDateTime tests datetime parsing.
func TestParseDateTime(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"2024-01-15 14:30:00", true},
		{"2024-01-15", true},
		{"", false},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := parseDateTime(tt.input)
			if tt.expected {
				assert.False(t, result.IsZero())
			} else {
				assert.True(t, result.IsZero())
			}
		})
	}
}

// TestParseDailyTimeSeries tests daily time series parsing.
func TestParseDailyTimeSeries(t *testing.T) {
	jsonData := `{
		"Meta Data": {
			"1. Information": "Daily Prices",
			"2. Symbol": "IBM"
		},
		"Time Series (Daily)": {
			"2024-01-15": {
				"1. open": "185.00",
				"2. high": "186.50",
				"3. low": "184.50",
				"4. close": "186.20",
				"5. volume": "3456789"
			},
			"2024-01-14": {
				"1. open": "184.50",
				"2. high": "185.50",
				"3. low": "184.00",
				"4. close": "185.00",
				"5. volume": "3214567"
			}
		}
	}`

	prices, err := parseDailyTimeSeries([]byte(jsonData))
	require.NoError(t, err)
	require.Len(t, prices, 2)

	// Should be sorted newest first
	assert.Equal(t, 2024, prices[0].Date.Year())
	assert.Equal(t, time.January, prices[0].Date.Month())
	assert.Equal(t, 15, prices[0].Date.Day())
	assert.Equal(t, 185.0, prices[0].Open)
	assert.Equal(t, 186.5, prices[0].High)
	assert.Equal(t, 184.5, prices[0].Low)
	assert.Equal(t, 186.2, prices[0].Close)
	assert.Equal(t, int64(3456789), prices[0].Volume)
}

// TestParseGlobalQuote tests global quote parsing.
func TestParseGlobalQuote(t *testing.T) {
	jsonData := `{
		"Global Quote": {
			"01. symbol": "IBM",
			"02. open": "185.00",
			"03. high": "186.50",
			"04. low": "184.50",
			"05. price": "186.20",
			"06. volume": "3456789",
			"07. latest trading day": "2024-01-15",
			"08. previous close": "185.00",
			"09. change": "1.20",
			"10. change percent": "0.65%"
		}
	}`

	quote, err := parseGlobalQuote([]byte(jsonData))
	require.NoError(t, err)

	assert.Equal(t, "IBM", quote.Symbol)
	assert.Equal(t, 185.0, quote.Open)
	assert.Equal(t, 186.5, quote.High)
	assert.Equal(t, 184.5, quote.Low)
	assert.Equal(t, 186.2, quote.Price)
	assert.Equal(t, int64(3456789), quote.Volume)
	assert.Equal(t, 185.0, quote.PreviousClose)
	assert.Equal(t, 1.2, quote.Change)
	assert.Equal(t, 0.65, quote.ChangePercent)
}

// TestParseSymbolSearch tests symbol search parsing.
func TestParseSymbolSearch(t *testing.T) {
	jsonData := `{
		"bestMatches": [
			{
				"1. symbol": "IBM",
				"2. name": "International Business Machines Corp",
				"3. type": "Equity",
				"4. region": "United States",
				"5. marketOpen": "09:30",
				"6. marketClose": "16:00",
				"7. timezone": "UTC-05",
				"8. currency": "USD",
				"9. matchScore": "1.0000"
			}
		]
	}`

	matches, err := parseSymbolSearch([]byte(jsonData))
	require.NoError(t, err)
	require.Len(t, matches, 1)

	assert.Equal(t, "IBM", matches[0].Symbol)
	assert.Equal(t, "International Business Machines Corp", matches[0].Name)
	assert.Equal(t, "Equity", matches[0].Type)
	assert.Equal(t, "USD", matches[0].Currency)
}

// TestParseCompanyOverview tests company overview parsing.
func TestParseCompanyOverview(t *testing.T) {
	jsonData := `{
		"Symbol": "IBM",
		"AssetType": "Common Stock",
		"Name": "International Business Machines",
		"Description": "IBM is a technology company.",
		"Exchange": "NYSE",
		"Currency": "USD",
		"Country": "USA",
		"Sector": "Technology",
		"Industry": "Information Technology Services",
		"MarketCapitalization": "125000000000",
		"PERatio": "20.5",
		"EPS": "9.05",
		"DividendYield": "0.0485",
		"52WeekHigh": "200.00",
		"52WeekLow": "120.00",
		"Beta": "0.95"
	}`

	overview, err := parseCompanyOverview([]byte(jsonData))
	require.NoError(t, err)

	assert.Equal(t, "IBM", overview.Symbol)
	assert.Equal(t, "Common Stock", overview.AssetType)
	assert.Equal(t, "International Business Machines", overview.Name)
	assert.Equal(t, "NYSE", overview.Exchange)
	assert.Equal(t, "USD", overview.Currency)
	assert.Equal(t, "Technology", overview.Sector)
	assert.Equal(t, int64(125000000000), overview.MarketCapitalization)
	require.NotNil(t, overview.PERatio)
	assert.Equal(t, 20.5, *overview.PERatio)
	require.NotNil(t, overview.EPS)
	assert.Equal(t, 9.05, *overview.EPS)
	require.NotNil(t, overview.FiftyTwoWeekHigh)
	assert.Equal(t, 200.0, *overview.FiftyTwoWeekHigh)
}

// TestParseIncomeStatement tests income statement parsing.
func TestParseIncomeStatement(t *testing.T) {
	jsonData := `{
		"symbol": "IBM",
		"annualReports": [
			{
				"fiscalDateEnding": "2023-12-31",
				"reportedCurrency": "USD",
				"totalRevenue": "60000000000",
				"grossProfit": "30000000000",
				"operatingIncome": "9000000000",
				"netIncome": "7200000000"
			}
		],
		"quarterlyReports": []
	}`

	stmt, err := parseIncomeStatement([]byte(jsonData))
	require.NoError(t, err)

	assert.Equal(t, "IBM", stmt.Symbol)
	require.Len(t, stmt.AnnualReports, 1)
	assert.Equal(t, "2023-12-31", stmt.AnnualReports[0].FiscalDateEnding)
	assert.Equal(t, int64(60000000000), stmt.AnnualReports[0].TotalRevenue)
	assert.Equal(t, int64(7200000000), stmt.AnnualReports[0].NetIncome)
}

// TestParseMACD tests MACD parsing.
func TestParseMACD(t *testing.T) {
	jsonData := `{
		"Meta Data": {
			"1. Symbol": "IBM"
		},
		"Technical Analysis: MACD": {
			"2024-01-15": {
				"MACD": "1.5",
				"MACD_Signal": "1.2",
				"MACD_Hist": "0.3"
			}
		}
	}`

	data, err := parseMACD([]byte(jsonData))
	require.NoError(t, err)
	require.Len(t, data.Values, 1)

	assert.Equal(t, 1.5, data.Values[0].MACD)
	assert.Equal(t, 1.2, data.Values[0].Signal)
	assert.Equal(t, 0.3, data.Values[0].Histogram)
}

// TestParseBBANDS tests Bollinger Bands parsing.
func TestParseBBANDS(t *testing.T) {
	jsonData := `{
		"Meta Data": {
			"1. Symbol": "IBM"
		},
		"Technical Analysis: BBANDS": {
			"2024-01-15": {
				"Real Upper Band": "190.5",
				"Real Middle Band": "185.0",
				"Real Lower Band": "179.5"
			}
		}
	}`

	data, err := parseBBANDS([]byte(jsonData))
	require.NoError(t, err)
	require.Len(t, data.Values, 1)

	assert.Equal(t, 190.5, data.Values[0].UpperBand)
	assert.Equal(t, 185.0, data.Values[0].MiddleBand)
	assert.Equal(t, 179.5, data.Values[0].LowerBand)
}

// TestParseExchangeRate tests exchange rate parsing.
func TestParseExchangeRate(t *testing.T) {
	jsonData := `{
		"Realtime Currency Exchange Rate": {
			"1. From_Currency Code": "USD",
			"2. From_Currency Name": "United States Dollar",
			"3. To_Currency Code": "EUR",
			"4. To_Currency Name": "Euro",
			"5. Exchange Rate": "0.9250",
			"6. Last Refreshed": "2024-01-15 14:30:00",
			"7. Time Zone": "UTC",
			"8. Bid Price": "0.9248",
			"9. Ask Price": "0.9252"
		}
	}`

	rate, err := parseExchangeRate([]byte(jsonData))
	require.NoError(t, err)

	assert.Equal(t, "USD", rate.FromCurrency)
	assert.Equal(t, "EUR", rate.ToCurrency)
	assert.Equal(t, 0.925, rate.ExchangeRate)
	assert.Equal(t, 0.9248, rate.BidPrice)
	assert.Equal(t, 0.9252, rate.AskPrice)
}

// TestParseCommodityData tests commodity data parsing.
func TestParseCommodityData(t *testing.T) {
	jsonData := `{
		"name": "WTI",
		"interval": "daily",
		"unit": "dollars per barrel",
		"data": [
			{"date": "2024-01-15", "value": "75.50"},
			{"date": "2024-01-14", "value": "74.80"},
			{"date": "2024-01-13", "value": "."}
		]
	}`

	prices, err := parseCommodityData([]byte(jsonData))
	require.NoError(t, err)
	require.Len(t, prices, 2) // One entry with "." should be skipped

	assert.Equal(t, 75.5, prices[0].Value)
	assert.Equal(t, 74.8, prices[1].Value)
}

// TestParseEconomicData tests economic indicator parsing.
func TestParseEconomicData(t *testing.T) {
	jsonData := `{
		"name": "Real GDP",
		"interval": "quarterly",
		"unit": "billions of dollars",
		"data": [
			{"date": "2023-12-31", "value": "25000.5"},
			{"date": "2023-09-30", "value": "24500.2"}
		]
	}`

	data, err := parseEconomicData([]byte(jsonData))
	require.NoError(t, err)

	assert.Equal(t, "Real GDP", data.Name)
	assert.Equal(t, "quarterly", data.Interval)
	require.Len(t, data.Data, 2)
	assert.Equal(t, 25000.5, data.Data[0].Value)
}

// TestParseMarketMovers tests market movers parsing.
func TestParseMarketMovers(t *testing.T) {
	jsonData := `{
		"metadata": {
			"last_updated": "2024-01-15 16:00:00"
		},
		"top_gainers": [
			{
				"ticker": "AAPL",
				"price": "185.50",
				"change_amount": "5.50",
				"change_percentage": "3.05%",
				"volume": "50000000"
			}
		],
		"top_losers": [
			{
				"ticker": "MSFT",
				"price": "380.00",
				"change_amount": "-10.00",
				"change_percentage": "-2.56%",
				"volume": "30000000"
			}
		],
		"most_actively_traded": []
	}`

	movers, err := parseMarketMovers([]byte(jsonData))
	require.NoError(t, err)

	require.Len(t, movers.TopGainers, 1)
	assert.Equal(t, "AAPL", movers.TopGainers[0].Ticker)
	assert.Equal(t, 185.5, movers.TopGainers[0].Price)
	assert.Equal(t, 3.05, movers.TopGainers[0].ChangePercent)

	require.Len(t, movers.TopLosers, 1)
	assert.Equal(t, "MSFT", movers.TopLosers[0].Ticker)
}

// TestErrorTypes tests error type implementations.
func TestErrorTypes(t *testing.T) {
	t.Run("ErrRateLimitExceeded", func(t *testing.T) {
		err := ErrRateLimitExceeded{}
		assert.Contains(t, err.Error(), "rate limit")
	})

	t.Run("ErrInvalidAPIKey", func(t *testing.T) {
		err := ErrInvalidAPIKey{}
		assert.Contains(t, err.Error(), "invalid")
	})

	t.Run("ErrSymbolNotFound", func(t *testing.T) {
		err := ErrSymbolNotFound{Symbol: "XYZ"}
		assert.Contains(t, err.Error(), "XYZ")
	})
}

// TestSetCacheTTL tests custom cache TTL configuration.
func TestSetCacheTTL(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	customTTL := CacheTTL{
		Fundamentals:        48 * time.Hour,
		TechnicalIndicators: 2 * time.Hour,
		PriceData:           30 * time.Minute,
		EconomicIndicators:  48 * time.Hour,
		Commodities:         2 * time.Hour,
		ExchangeRates:       30 * time.Minute,
	}

	client.SetCacheTTL(customTTL)

	assert.Equal(t, 48*time.Hour, client.cacheTTL.Fundamentals)
	assert.Equal(t, 2*time.Hour, client.cacheTTL.TechnicalIndicators)
}

// TestDefaultCacheTTL tests default TTL values.
func TestDefaultCacheTTL(t *testing.T) {
	ttl := DefaultCacheTTL()

	assert.Equal(t, 24*time.Hour, ttl.Fundamentals)
	assert.Equal(t, 1*time.Hour, ttl.TechnicalIndicators)
	assert.Equal(t, 15*time.Minute, ttl.PriceData)
	assert.Equal(t, 24*time.Hour, ttl.EconomicIndicators)
	assert.Equal(t, 1*time.Hour, ttl.Commodities)
	assert.Equal(t, 15*time.Minute, ttl.ExchangeRates)
}

// TestAPIErrorDetection tests detection of API error responses.
func TestAPIErrorDetection(t *testing.T) {
	client := NewClient("test-key", zerolog.Nop())

	tests := []struct {
		name        string
		body        string
		expectError bool
		errorType   error
	}{
		{
			name:        "Rate limit message",
			body:        `{"Note": "API call frequency is limited"}`,
			expectError: true,
			errorType:   ErrRateLimitExceeded{},
		},
		{
			name:        "Error message",
			body:        `{"Error Message": "Invalid symbol"}`,
			expectError: true,
		},
		{
			name:        "Thank you message",
			body:        `Thank you for using Alpha Vantage!`,
			expectError: true,
			errorType:   ErrRateLimitExceeded{},
		},
		{
			name:        "Valid response",
			body:        `{"data": "valid"}`,
			expectError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := client.checkAPIError([]byte(tt.body))
			if tt.expectError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

// TestNextMidnightUTC tests the midnight calculation.
func TestNextMidnightUTC(t *testing.T) {
	midnight := nextMidnightUTC()

	now := time.Now().UTC()
	assert.True(t, midnight.After(now))
	assert.Equal(t, 0, midnight.Hour())
	assert.Equal(t, 0, midnight.Minute())
	assert.Equal(t, 0, midnight.Second())
}

// BenchmarkParseFloat64 benchmarks float parsing.
func BenchmarkParseFloat64(b *testing.B) {
	for i := 0; i < b.N; i++ {
		parseFloat64("123.456789")
	}
}

// BenchmarkCacheOperations benchmarks cache read/write.
func BenchmarkCacheOperations(b *testing.B) {
	client := NewClient("test-key", zerolog.Nop())

	b.Run("Set", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			client.setCache("key", "value", time.Hour)
		}
	})

	b.Run("Get", func(b *testing.B) {
		client.setCache("key", "value", time.Hour)
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			_, _ = client.getFromCache("key")
		}
	})
}

// TestInterfaceImplementation verifies Client implements ClientInterface.
func TestInterfaceImplementation(t *testing.T) {
	var _ ClientInterface = (*Client)(nil)
}
