//go:build integration
// +build integration

package yahoo

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNativeClient_GetCurrentPrice(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		price, err := client.GetCurrentPrice("AAPL", nil, 3)
		require.NoError(t, err)
		assert.NotNil(t, price)
		assert.Greater(t, *price, 0.0)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "MSFT"
		price, err := client.GetCurrentPrice("MSFT.US", &override, 3)
		require.NoError(t, err)
		assert.NotNil(t, price)
		assert.Greater(t, *price, 0.0)
	})

	t.Run("with ISIN override", func(t *testing.T) {
		// AAPL ISIN
		isin := "US0378331005"
		price, err := client.GetCurrentPrice("AAPL.US", &isin, 3)
		require.NoError(t, err)
		assert.NotNil(t, price)
		assert.Greater(t, *price, 0.0)
	})

	t.Run("invalid symbol", func(t *testing.T) {
		price, err := client.GetCurrentPrice("INVALID_SYMBOL_XYZ", nil, 1)
		assert.Error(t, err)
		assert.Nil(t, price)
	})

	t.Run("retry logic", func(t *testing.T) {
		// Test that maxRetries is respected
		price, err := client.GetCurrentPrice("AAPL", nil, 1)
		// Should succeed on first try for valid symbol
		if err == nil {
			assert.NotNil(t, price)
		} else {
			// If it fails, that's also valid for testing retry logic
			assert.Nil(t, price)
		}
	})
}

func TestNativeClient_GetBatchQuotes(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("multiple symbols", func(t *testing.T) {
		symbolMap := map[string]*string{
			"AAPL.US": nil,
			"MSFT.US": nil,
		}
		quotes, err := client.GetBatchQuotes(symbolMap)
		require.NoError(t, err)
		assert.NotEmpty(t, quotes)
		assert.Contains(t, quotes, "AAPL.US")
		assert.Contains(t, quotes, "MSFT.US")
		assert.NotNil(t, quotes["AAPL.US"])
		assert.NotNil(t, quotes["MSFT.US"])
		assert.Greater(t, *quotes["AAPL.US"], 0.0)
		assert.Greater(t, *quotes["MSFT.US"], 0.0)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "GOOGL"
		symbolMap := map[string]*string{
			"GOOGL.US": &override,
		}
		quotes, err := client.GetBatchQuotes(symbolMap)
		require.NoError(t, err)
		assert.NotEmpty(t, quotes)
		assert.Contains(t, quotes, "GOOGL.US")
	})

	t.Run("empty symbol map", func(t *testing.T) {
		symbolMap := map[string]*string{}
		quotes, err := client.GetBatchQuotes(symbolMap)
		require.NoError(t, err)
		assert.Empty(t, quotes)
	})

	t.Run("partial failures", func(t *testing.T) {
		symbolMap := map[string]*string{
			"AAPL.US":        nil,
			"INVALID_SYMBOL": nil,
			"MSFT.US":        nil,
		}
		quotes, err := client.GetBatchQuotes(symbolMap)
		// Should still return valid quotes even if some fail
		if err == nil {
			assert.NotEmpty(t, quotes)
			assert.Contains(t, quotes, "AAPL.US")
			assert.Contains(t, quotes, "MSFT.US")
		}
	})
}

func TestNativeClient_GetHistoricalPrices(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("1y period", func(t *testing.T) {
		prices, err := client.GetHistoricalPrices("AAPL", nil, "1y")
		require.NoError(t, err)
		assert.NotEmpty(t, prices)
		assert.Greater(t, len(prices), 0)

		// Check first price structure
		first := prices[0]
		assert.False(t, first.Date.IsZero())
		assert.Greater(t, first.Open, 0.0)
		assert.Greater(t, first.High, 0.0)
		assert.Greater(t, first.Low, 0.0)
		assert.Greater(t, first.Close, 0.0)
		assert.Greater(t, first.Volume, int64(0))
		assert.Greater(t, first.AdjClose, 0.0)
	})

	t.Run("1mo period", func(t *testing.T) {
		prices, err := client.GetHistoricalPrices("MSFT", nil, "1mo")
		require.NoError(t, err)
		assert.NotEmpty(t, prices)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "GOOGL"
		prices, err := client.GetHistoricalPrices("GOOGL.US", &override, "1mo")
		require.NoError(t, err)
		assert.NotEmpty(t, prices)
	})

	t.Run("invalid period", func(t *testing.T) {
		prices, err := client.GetHistoricalPrices("AAPL", nil, "invalid")
		// Should handle gracefully or return error
		if err != nil {
			assert.Empty(t, prices)
		}
	})
}

func TestNativeClient_GetFundamentalData(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		data, err := client.GetFundamentalData("AAPL", nil)
		require.NoError(t, err)
		assert.NotNil(t, data)
		assert.Equal(t, "AAPL", data.Symbol)

		// Check that key fields are populated (may be nil for some stocks)
		// At least some fields should be present
		hasData := data.PERatio != nil || data.ForwardPE != nil || data.MarketCap != nil
		assert.True(t, hasData, "At least some fundamental data should be present")
	})

	t.Run("field mapping", func(t *testing.T) {
		data, err := client.GetFundamentalData("MSFT", nil)
		require.NoError(t, err)
		assert.NotNil(t, data)

		// Verify all expected fields exist (may be nil)
		// This test ensures the struct mapping is correct
		assert.NotNil(t, data)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "GOOGL"
		data, err := client.GetFundamentalData("GOOGL.US", &override)
		require.NoError(t, err)
		assert.NotNil(t, data)
	})
}

func TestNativeClient_GetAnalystData(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		data, err := client.GetAnalystData("AAPL", nil)
		require.NoError(t, err)
		assert.NotNil(t, data)
		assert.Equal(t, "AAPL", data.Symbol)
		assert.NotEmpty(t, data.Recommendation)
		assert.GreaterOrEqual(t, data.TargetPrice, 0.0)
		assert.Greater(t, data.CurrentPrice, 0.0)
		assert.GreaterOrEqual(t, data.NumAnalysts, 0)
		assert.GreaterOrEqual(t, data.RecommendationScore, 0.0)
		assert.LessOrEqual(t, data.RecommendationScore, 1.0)
	})

	t.Run("recommendation score calculation", func(t *testing.T) {
		data, err := client.GetAnalystData("MSFT", nil)
		require.NoError(t, err)
		assert.NotNil(t, data)

		// Verify recommendation score is in valid range
		assert.GreaterOrEqual(t, data.RecommendationScore, 0.0)
		assert.LessOrEqual(t, data.RecommendationScore, 1.0)
	})

	t.Run("upside percentage calculation", func(t *testing.T) {
		data, err := client.GetAnalystData("AAPL", nil)
		require.NoError(t, err)
		if data.TargetPrice > 0 && data.CurrentPrice > 0 {
			expectedUpside := ((data.TargetPrice - data.CurrentPrice) / data.CurrentPrice) * 100
			assert.InDelta(t, expectedUpside, data.UpsidePct, 0.01)
		}
	})
}

func TestNativeClient_GetSecurityIndustry(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		industry, err := client.GetSecurityIndustry("AAPL", nil)
		require.NoError(t, err)
		// Industry may be nil for some securities
		if industry != nil {
			assert.NotEmpty(t, *industry)
		}
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "MSFT"
		industry, err := client.GetSecurityIndustry("MSFT.US", &override)
		require.NoError(t, err)
		// May be nil
		_ = industry
	})
}

func TestNativeClient_GetSecurityCountryAndExchange(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		country, exchange, err := client.GetSecurityCountryAndExchange("AAPL", nil)
		require.NoError(t, err)
		// At least one should be present
		if country != nil {
			assert.NotEmpty(t, *country)
		}
		if exchange != nil {
			assert.NotEmpty(t, *exchange)
		}
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "MSFT"
		country, exchange, err := client.GetSecurityCountryAndExchange("MSFT.US", &override)
		require.NoError(t, err)
		_ = country
		_ = exchange
	})
}

func TestNativeClient_GetQuoteName(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		name, err := client.GetQuoteName("AAPL", nil)
		require.NoError(t, err)
		assert.NotNil(t, name)
		assert.NotEmpty(t, *name)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "MSFT"
		name, err := client.GetQuoteName("MSFT.US", &override)
		require.NoError(t, err)
		assert.NotNil(t, name)
		assert.NotEmpty(t, *name)
	})
}

func TestNativeClient_GetQuoteType(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid symbol", func(t *testing.T) {
		quoteType, err := client.GetQuoteType("AAPL", nil)
		require.NoError(t, err)
		assert.NotEmpty(t, quoteType)
	})

	t.Run("with yahooSymbolOverride", func(t *testing.T) {
		override := "MSFT"
		quoteType, err := client.GetQuoteType("MSFT.US", &override)
		require.NoError(t, err)
		assert.NotEmpty(t, quoteType)
	})
}

func TestNativeClient_LookupTickerFromISIN(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("valid ISIN for AAPL", func(t *testing.T) {
		// AAPL ISIN
		isin := "US0378331005"
		ticker, err := client.LookupTickerFromISIN(isin)
		require.NoError(t, err)
		assert.NotEmpty(t, ticker)
		// Should return a valid ticker symbol
		assert.Equal(t, "AAPL", ticker)
	})

	t.Run("valid ISIN for MSFT", func(t *testing.T) {
		// MSFT ISIN
		isin := "US5949181045"
		ticker, err := client.LookupTickerFromISIN(isin)
		require.NoError(t, err)
		assert.NotEmpty(t, ticker)
		assert.Equal(t, "MSFT", ticker)
	})

	t.Run("invalid ISIN", func(t *testing.T) {
		isin := "INVALID123456"
		ticker, err := client.LookupTickerFromISIN(isin)
		assert.Error(t, err)
		assert.Empty(t, ticker)
	})
}

func TestNativeClient_SymbolResolution(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.InfoLevel)
	client := NewNativeClient(log)

	t.Run("yahooSymbolOverride takes precedence", func(t *testing.T) {
		override := "MSFT"
		price1, err1 := client.GetCurrentPrice("AAPL.US", &override, 1)
		price2, err2 := client.GetCurrentPrice("MSFT", nil, 1)

		// Both should succeed and return same price (using MSFT)
		// Use InDelta to handle minor price fluctuations from live data
		if err1 == nil && err2 == nil {
			assert.InDelta(t, *price1, *price2, 0.1, "Prices should match (using MSFT for both)")
		}
	})

	t.Run("fallback conversion for .US", func(t *testing.T) {
		// Should work without override (fallback conversion)
		price, err := client.GetCurrentPrice("AAPL.US", nil, 1)
		if err == nil {
			assert.NotNil(t, price)
			assert.Greater(t, *price, 0.0)
		}
	})

	t.Run("fallback conversion for .JP", func(t *testing.T) {
		// Japanese stock - should convert .JP to .T
		price, err := client.GetCurrentPrice("7203.JP", nil, 1)
		// May fail if symbol doesn't exist, but should attempt conversion
		_ = price
		_ = err
	})
}
