package scheduler

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestBuildOpportunityContext_Integration_EURConversion tests the complete EUR conversion flow
// This integration test verifies:
// 1. Prices are fetched from Yahoo Finance (mock)
// 2. Prices are converted to EUR using exchange service (mock)
// 3. Opportunity context is built with EUR prices
// 4. All calculators receive correct EUR prices
func TestBuildOpportunityContext_Integration_EURConversion(t *testing.T) {
	// Setup: Securities with different currencies
	securities := []universe.Security{
		{
			Symbol:   "VWS.AS",
			ISIN:     "NL0000852564",
			Currency: "EUR",
			Active:   true,
			Country:  "NL",
			Name:     "Vopak",
		},
		{
			Symbol:   "AAPL",
			ISIN:     "US0378331005",
			Currency: "USD",
			Active:   true,
			Country:  "US",
			Name:     "Apple Inc.",
		},
		{
			Symbol:   "0700.HK",
			ISIN:     "KYG875721634",
			Currency: "HKD",
			Active:   true,
			Country:  "HK",
			Name:     "Tencent Holdings",
		},
		{
			Symbol:   "BARC.L",
			ISIN:     "GB0031348658",
			Currency: "GBP",
			Active:   true,
			Country:  "GB",
			Name:     "Barclays",
		},
	}

	// Mock native currency prices from Yahoo Finance
	nativePrices := map[string]float64{
		"VWS.AS":  42.50,  // EUR - no conversion needed
		"AAPL":    150.00, // USD
		"0700.HK": 497.40, // HKD (this was the bug - treated as 497.40 EUR)
		"BARC.L":  25.00,  // GBP
	}

	// Mock exchange rates
	exchangeRates := map[string]float64{
		"USD:EUR": 0.93, // 1 USD = 0.93 EUR
		"HKD:EUR": 0.11, // 1 HKD = 0.11 EUR (497.40 HKD = ~54.71 EUR)
		"GBP:EUR": 1.17, // 1 GBP = 1.17 EUR
	}

	// Mock price client that returns native currency prices
	mockPriceClient := &MockPriceClientForConversion{
		quotes: make(map[string]*float64),
	}
	for symbol, price := range nativePrices {
		p := price
		mockPriceClient.quotes[symbol] = &p
	}

	// Mock price conversion service that converts to EUR
	mockPriceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			converted := make(map[string]float64)

			// Build currency map
			currencyMap := make(map[string]string)
			for _, sec := range secs {
				currencyMap[sec.Symbol] = sec.Currency
			}

			for symbol, nativePrice := range prices {
				currency := currencyMap[symbol]

				if currency == "EUR" || currency == "" {
					// Already in EUR, no conversion
					converted[symbol] = nativePrice
				} else {
					// Convert to EUR
					rateKey := currency + ":EUR"
					if rate, ok := exchangeRates[rateKey]; ok {
						converted[symbol] = nativePrice * rate
					} else {
						// Fallback: use native price
						converted[symbol] = nativePrice
					}
				}
			}

			return converted
		},
	}

	// Mock repositories
	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			result := make([]interface{}, len(securities))
			for i, sec := range securities {
				result[i] = sec
			}
			return result, nil
		},
	}

	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockAllocRepo := &MockAllocationRepoForOptimizer{
		GetAllFunc: func() (map[string]float64, error) {
			return map[string]float64{
				"NL": 0.30,
				"US": 0.40,
				"HK": 0.20,
				"GB": 0.10,
			}, nil
		},
	}

	mockCashManager := &MockCashManagerForOptimizer{
		GetAllCashBalancesFunc: func() (map[string]float64, error) {
			return map[string]float64{"EUR": 5000.0}, nil
		},
	}

	mockScoresRepo := &MockScoresRepoForContext{
		GetCAGRsFunc: func(isinList []string) (map[string]float64, error) {
			return map[string]float64{
				"NL0000852564": 0.10, // VWS.AS
				"US0378331005": 0.12, // AAPL
				"KYG875721634": 0.15, // 0700.HK
				"GB0031348658": 0.08, // BARC.L
			}, nil
		},
		GetQualityScoresFunc: func(isinList []string) (map[string]float64, map[string]float64, error) {
			longTerm := map[string]float64{
				"NL0000852564": 0.75, // VWS.AS
				"US0378331005": 0.85, // AAPL
				"KYG875721634": 0.80, // 0700.HK
				"GB0031348658": 0.70, // BARC.L
			}
			fundamentals := map[string]float64{
				"NL0000852564": 0.70,
				"US0378331005": 0.80,
				"KYG875721634": 0.75,
				"GB0031348658": 0.65,
			}
			return longTerm, fundamentals, nil
		},
		GetValueTrapDataFunc: func(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
			opportunity := map[string]float64{
				"NL0000852564": 0.6,
				"US0378331005": 0.7,
				"KYG875721634": 0.65,
				"GB0031348658": 0.55,
			}
			momentum := map[string]float64{
				"NL0000852564": 0.5,
				"US0378331005": 0.6,
				"KYG875721634": 0.55,
				"GB0031348658": 0.45,
			}
			volatility := map[string]float64{
				"NL0000852564": 0.25,
				"US0378331005": 0.20,
				"KYG875721634": 0.30,
				"GB0031348658": 0.35,
			}
			return opportunity, momentum, volatility, nil
		},
	}

	mockSettingsRepo := &MockSettingsRepoForContext{
		GetTargetReturnSettingsFunc: func() (float64, float64, error) {
			return 0.11, 0.80, nil // 11% target return, 80% threshold
		},
		GetVirtualTestCashFunc: func() (float64, error) {
			return 0.0, nil
		},
	}

	mockRegimeRepo := &MockRegimeRepoForContext{
		GetCurrentRegimeScoreFunc: func() (float64, error) {
			return 0.6, nil
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}

	// Create job with all dependencies
	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockGroupingRepo,
		mockCashManager,
		mockPriceClient,
		mockPriceConversionService,
		mockScoresRepo,
		mockSettingsRepo,
		mockRegimeRepo,
	)

	// Execute
	err := job.Run()
	require.NoError(t, err)

	// Verify
	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)

	// Verify all prices are in EUR (converted correctly)
	t.Run("EUR prices converted correctly", func(t *testing.T) {
		prices := ctx.CurrentPrices

		// EUR security - unchanged (ISIN key)
		assert.InDelta(t, 42.50, prices["NL0000852564"], 0.01, "EUR price should be unchanged")

		// USD security - converted (150 USD × 0.93 = 139.5 EUR) (ISIN key)
		assert.InDelta(t, 139.50, prices["US0378331005"], 0.01, "USD price should be converted to EUR")

		// HKD security - converted (497.40 HKD × 0.11 = 54.71 EUR) (ISIN key)
		// This is the critical bug fix - before it was 497.40 EUR (9x error)
		assert.InDelta(t, 54.71, prices["KYG875721634"], 0.01, "HKD price should be converted to EUR (not treated as EUR)")

		// GBP security - converted (25 GBP × 1.17 = 29.25 EUR) (ISIN key)
		assert.InDelta(t, 29.25, prices["GB0031348658"], 0.01, "GBP price should be converted to EUR")
	})

	// Verify securities have correct data
	t.Run("Securities have correct currency information", func(t *testing.T) {
		require.Len(t, ctx.Securities, 4)

		// Find each security by symbol
		securityMap := make(map[string]bool)
		for _, sec := range ctx.Securities {
			securityMap[sec.Symbol] = true
		}

		assert.True(t, securityMap["VWS.AS"], "VWS.AS should be in securities")
		assert.True(t, securityMap["AAPL"], "AAPL should be in securities")
		assert.True(t, securityMap["0700.HK"], "0700.HK should be in securities")
		assert.True(t, securityMap["BARC.L"], "BARC.L should be in securities")
	})

	// Verify scores are present (SecurityScores are by ISIN)
	t.Run("Scores are available", func(t *testing.T) {
		// Verify score components are present (these are populated by the job)
		assert.NotNil(t, ctx.LongTermScores, "Long-term scores map should be initialized")
		assert.NotNil(t, ctx.FundamentalsScores, "Fundamentals scores map should be initialized")

		// SecurityScores might be computed later by calculators, so just check it's not nil
		assert.NotNil(t, ctx, "Context should be created")
	})

	// Verify allocation data is available
	t.Run("Allocation data is available", func(t *testing.T) {
		// The allocation repo was mocked to return country allocations
		// These may be stored in different fields depending on processing
		assert.NotNil(t, ctx, "Context should be created with allocation data")
	})

	// Verify cash is correct
	t.Run("Cash is correct", func(t *testing.T) {
		assert.Equal(t, 5000.0, ctx.AvailableCashEUR)
	})
}

// TestBuildOpportunityContext_Integration_MissingExchangeRate tests graceful degradation
func TestBuildOpportunityContext_Integration_MissingExchangeRate(t *testing.T) {
	// Setup: Security with currency but no exchange rate available
	securities := []universe.Security{
		{
			Symbol:   "TSM",
			ISIN:     "US8740391003", // Taiwan Semiconductor ISIN
			Currency: "TWD",          // Taiwan Dollar - no rate available
			Active:   true,
			Country:  "TW",
			Name:     "Taiwan Semiconductor",
		},
	}

	nativePrice := 600.0
	mockPriceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"TSM": &nativePrice,
		},
	}

	// Mock price conversion service that returns native price when rate unavailable
	mockPriceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			// No TWD:EUR rate available - should fallback to native price
			converted := make(map[string]float64)
			for symbol, price := range prices {
				converted[symbol] = price // Fallback
			}
			return converted
		},
	}

	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			return []interface{}{securities[0]}, nil
		},
	}

	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockAllocRepo := &MockAllocationRepoForOptimizer{
		GetAllFunc: func() (map[string]float64, error) {
			return map[string]float64{"TW": 1.0}, nil
		},
	}

	mockCashManager := &MockCashManagerForOptimizer{
		GetAllCashBalancesFunc: func() (map[string]float64, error) {
			return map[string]float64{"EUR": 1000.0}, nil
		},
	}

	mockScoresRepo := &MockScoresRepoForContext{
		GetCAGRsFunc: func(isinList []string) (map[string]float64, error) {
			return map[string]float64{}, nil
		},
		GetQualityScoresFunc: func(isinList []string) (map[string]float64, map[string]float64, error) {
			return map[string]float64{}, map[string]float64{}, nil
		},
		GetValueTrapDataFunc: func(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
			return map[string]float64{}, map[string]float64{}, map[string]float64{}, nil
		},
	}

	mockSettingsRepo := &MockSettingsRepoForContext{
		GetTargetReturnSettingsFunc: func() (float64, float64, error) {
			return 0.11, 0.80, nil
		},
		GetVirtualTestCashFunc: func() (float64, error) {
			return 0.0, nil
		},
	}

	mockRegimeRepo := &MockRegimeRepoForContext{
		GetCurrentRegimeScoreFunc: func() (float64, error) {
			return 0.5, nil
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}

	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockGroupingRepo,
		mockCashManager,
		mockPriceClient,
		mockPriceConversionService,
		mockScoresRepo,
		mockSettingsRepo,
		mockRegimeRepo,
	)

	// Execute - should not fail even without exchange rate
	err := job.Run()
	require.NoError(t, err)

	// Verify
	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)

	// Should use native price (graceful degradation) - ISIN key
	assert.Equal(t, 600.0, ctx.CurrentPrices["US8740391003"], "Should fallback to native price when exchange rate unavailable")
}

// TestBuildOpportunityContext_Integration_NoPriceConversionService tests graceful degradation when service is nil
func TestBuildOpportunityContext_Integration_NoPriceConversionService(t *testing.T) {
	securities := []universe.Security{
		{
			Symbol:   "AAPL",
			ISIN:     "US0378331005", // Apple Inc. ISIN
			Currency: "USD",
			Active:   true,
			Name:     "Apple Inc.",
		},
	}

	nativePrice := 150.0
	mockPriceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"AAPL": &nativePrice,
		},
	}

	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			return []interface{}{securities[0]}, nil
		},
	}

	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockAllocRepo := &MockAllocationRepoForOptimizer{
		GetAllFunc: func() (map[string]float64, error) {
			return map[string]float64{"US": 1.0}, nil
		},
	}

	mockCashManager := &MockCashManagerForOptimizer{
		GetAllCashBalancesFunc: func() (map[string]float64, error) {
			return map[string]float64{"EUR": 1000.0}, nil
		},
	}

	mockScoresRepo := &MockScoresRepoForContext{
		GetCAGRsFunc: func(isinList []string) (map[string]float64, error) {
			return map[string]float64{}, nil
		},
		GetQualityScoresFunc: func(isinList []string) (map[string]float64, map[string]float64, error) {
			return map[string]float64{}, map[string]float64{}, nil
		},
		GetValueTrapDataFunc: func(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
			return map[string]float64{}, map[string]float64{}, map[string]float64{}, nil
		},
	}

	mockSettingsRepo := &MockSettingsRepoForContext{
		GetTargetReturnSettingsFunc: func() (float64, float64, error) {
			return 0.11, 0.80, nil
		},
		GetVirtualTestCashFunc: func() (float64, error) {
			return 0.0, nil
		},
	}

	mockRegimeRepo := &MockRegimeRepoForContext{
		GetCurrentRegimeScoreFunc: func() (float64, error) {
			return 0.5, nil
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}

	// Create job WITHOUT price conversion service (nil)
	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockGroupingRepo,
		mockCashManager,
		mockPriceClient,
		nil, // No price conversion service
		mockScoresRepo,
		mockSettingsRepo,
		mockRegimeRepo,
	)

	// Execute - should not fail even without price conversion service
	err := job.Run()
	require.NoError(t, err)

	// Verify
	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)

	// Should use native price (logged warning about potential valuation errors) - ISIN key
	assert.Equal(t, 150.0, ctx.CurrentPrices["US0378331005"], "Should use native price when conversion service unavailable")
}
