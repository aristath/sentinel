package scheduler

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockScoresRepoForContext is a mock implementation of ScoresRepositoryInterface
type MockScoresRepoForContext struct {
	GetCAGRsFunc         func(isinList []string) (map[string]float64, error)
	GetQualityScoresFunc func(isinList []string) (map[string]float64, map[string]float64, error)
	GetValueTrapDataFunc func(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error)
	GetTotalScoresFunc   func(isinList []string) (map[string]float64, error)
}

func (m *MockScoresRepoForContext) GetCAGRs(isinList []string) (map[string]float64, error) {
	if m.GetCAGRsFunc != nil {
		return m.GetCAGRsFunc(isinList)
	}
	return map[string]float64{}, nil
}

func (m *MockScoresRepoForContext) GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error) {
	if m.GetQualityScoresFunc != nil {
		return m.GetQualityScoresFunc(isinList)
	}
	return map[string]float64{}, map[string]float64{}, nil
}

func (m *MockScoresRepoForContext) GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
	if m.GetValueTrapDataFunc != nil {
		return m.GetValueTrapDataFunc(isinList)
	}
	return map[string]float64{}, map[string]float64{}, map[string]float64{}, nil
}

func (m *MockScoresRepoForContext) GetTotalScores(isinList []string) (map[string]float64, error) {
	if m.GetTotalScoresFunc != nil {
		return m.GetTotalScoresFunc(isinList)
	}
	return map[string]float64{}, nil
}

// MockSettingsRepoForContext is a mock implementation of SettingsRepositoryInterface
type MockSettingsRepoForContext struct {
	GetTargetReturnSettingsFunc func() (float64, float64, error)
	GetVirtualTestCashFunc      func() (float64, error)
}

func (m *MockSettingsRepoForContext) GetTargetReturnSettings() (float64, float64, error) {
	if m.GetTargetReturnSettingsFunc != nil {
		return m.GetTargetReturnSettingsFunc()
	}
	return 0.11, 0.80, nil
}

func (m *MockSettingsRepoForContext) GetVirtualTestCash() (float64, error) {
	if m.GetVirtualTestCashFunc != nil {
		return m.GetVirtualTestCashFunc()
	}
	return 0.0, nil
}

// MockRegimeRepoForContext is a mock implementation of RegimeRepositoryInterface
type MockRegimeRepoForContext struct {
	GetCurrentRegimeScoreFunc func() (float64, error)
}

func (m *MockRegimeRepoForContext) GetCurrentRegimeScore() (float64, error) {
	if m.GetCurrentRegimeScoreFunc != nil {
		return m.GetCurrentRegimeScoreFunc()
	}
	return 0.0, nil
}

// MockGroupingRepoForContext is a mock implementation of GroupingRepositoryInterface
type MockGroupingRepoForContext struct {
	GetCountryGroupsFunc  func() (map[string][]string, error)
	GetIndustryGroupsFunc func() (map[string][]string, error)
}

func (m *MockGroupingRepoForContext) GetCountryGroups() (map[string][]string, error) {
	if m.GetCountryGroupsFunc != nil {
		return m.GetCountryGroupsFunc()
	}
	return map[string][]string{}, nil
}

func (m *MockGroupingRepoForContext) GetIndustryGroups() (map[string][]string, error) {
	if m.GetIndustryGroupsFunc != nil {
		return m.GetIndustryGroupsFunc()
	}
	return map[string][]string{}, nil
}

func TestBuildOpportunityContextJob_Name(t *testing.T) {
	job := NewBuildOpportunityContextJob(nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	assert.Equal(t, "build_opportunity_context", job.Name())
}

func TestBuildOpportunityContextJob_Run_Success(t *testing.T) {
	// Mock position repo
	positions := []portfolio.Position{
		{Symbol: "AAPL", Quantity: 10, Currency: "USD", AvgPrice: 150.0},
	}
	positionsInterface := make([]interface{}, len(positions))
	for i := range positions {
		positionsInterface[i] = positions[i]
	}

	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return positionsInterface, nil
		},
	}

	// Mock security repo
	securities := []universe.Security{
		{Symbol: "AAPL", ISIN: "US0378331005", YahooSymbol: "AAPL", Country: "US", Industry: "Technology", Active: true, Name: "Apple Inc."},
	}
	securitiesInterface := make([]interface{}, len(securities))
	for i := range securities {
		securitiesInterface[i] = securities[i]
	}

	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			return securitiesInterface, nil
		},
	}

	// Mock allocation repo
	mockAllocRepo := &MockAllocationRepoForOptimizer{
		GetAllFunc: func() (map[string]float64, error) {
			return map[string]float64{
				"country_group:US":          0.5,
				"industry_group:Technology": 0.3,
			}, nil
		},
	}

	// Mock cash manager
	mockCashManager := &MockCashManagerForOptimizer{
		GetAllCashBalancesFunc: func() (map[string]float64, error) {
			return map[string]float64{"EUR": 1000.0}, nil
		},
	}

	// Mock price client
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return map[string]*float64{
				"AAPL": floatPtr(150.0),
			}, nil
		},
	}

	// Mock scores repo
	mockScoresRepo := &MockScoresRepoForContext{
		GetCAGRsFunc: func(isinList []string) (map[string]float64, error) {
			return map[string]float64{
				"US0378331005": 0.12,
				"AAPL":         0.12,
			}, nil
		},
		GetQualityScoresFunc: func(isinList []string) (map[string]float64, map[string]float64, error) {
			return map[string]float64{
					"US0378331005": 0.8,
					"AAPL":         0.8,
				}, map[string]float64{
					"US0378331005": 0.75,
					"AAPL":         0.75,
				}, nil
		},
		GetValueTrapDataFunc: func(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
			return map[string]float64{
					"US0378331005": 0.7,
					"AAPL":         0.7,
				}, map[string]float64{
					"US0378331005": 0.5,
					"AAPL":         0.5,
				}, map[string]float64{
					"US0378331005": 0.25,
					"AAPL":         0.25,
				}, nil
		},
	}

	// Mock settings repo
	mockSettingsRepo := &MockSettingsRepoForContext{
		GetTargetReturnSettingsFunc: func() (float64, float64, error) {
			return 0.11, 0.80, nil
		},
		GetVirtualTestCashFunc: func() (float64, error) {
			return 0.0, nil
		},
	}

	// Mock regime repo
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
		nil, // priceConversionService
		mockScoresRepo,
		mockSettingsRepo,
		mockRegimeRepo,
	)

	err := job.Run()
	require.NoError(t, err)

	ctx := job.GetOpportunityContext()
	require.NotNil(t, ctx)
	assert.Equal(t, 2500.0, ctx.TotalPortfolioValueEUR) // 1000 EUR + (10 * 150 USD)
	assert.Equal(t, 1000.0, ctx.AvailableCashEUR)
	assert.Equal(t, 1, len(ctx.Positions))
	assert.Equal(t, 1, len(ctx.Securities))
}

func TestBuildOpportunityContextJob_Run_PositionRepoError(t *testing.T) {
	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return nil, assert.AnError
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}
	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		nil,
		nil,
		mockGroupingRepo,
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get positions")
}

func TestBuildOpportunityContextJob_Run_SecurityRepoError(t *testing.T) {
	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			return nil, assert.AnError
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}
	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		nil,
		mockGroupingRepo,
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get securities")
}

func TestBuildOpportunityContextJob_Run_AllocationRepoError(t *testing.T) {
	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockSecurityRepo := &MockSecurityRepoForOptimizer{
		GetAllActiveFunc: func() ([]interface{}, error) {
			return []interface{}{}, nil
		},
	}

	mockAllocRepo := &MockAllocationRepoForOptimizer{
		GetAllFunc: func() (map[string]float64, error) {
			return nil, assert.AnError
		},
	}

	mockGroupingRepo := &MockGroupingRepoForContext{}
	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockGroupingRepo,
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get allocations")
}

// ============================================================================
// fetchCurrentPrices() EUR Conversion Tests
// ============================================================================

// MockPriceClientForConversion is a mock implementation for price fetching tests
type MockPriceClientForConversion struct {
	quotes map[string]*float64
	err    error
}

func (m *MockPriceClientForConversion) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if m.err != nil {
		return nil, m.err
	}
	return m.quotes, nil
}

// MockPriceConversionServiceForScheduler is a mock implementation of PriceConversionServiceInterface
type MockPriceConversionServiceForScheduler struct {
	convertFunc func(prices map[string]float64, securities []universe.Security) map[string]float64
}

func (m *MockPriceConversionServiceForScheduler) ConvertPricesToEUR(
	prices map[string]float64,
	securities []universe.Security,
) map[string]float64 {
	if m.convertFunc != nil {
		return m.convertFunc(prices, securities)
	}
	return prices
}

// TestFetchCurrentPrices_HKD_Conversion verifies HKD prices are converted to EUR
func TestFetchCurrentPrices_HKD_Conversion(t *testing.T) {
	// Setup: HKD security with price 497.4 HKD
	securities := []universe.Security{
		{Symbol: "CAT.3750.AS", Currency: "HKD"},
	}

	// Mock Yahoo returns 497.4 HKD
	hkdPrice := 497.4
	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"CAT.3750.AS": &hkdPrice,
		},
	}

	// Mock price conversion service: converts HKD to EUR (1 HKD = 0.11 EUR)
	priceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			converted := make(map[string]float64)
			for symbol, price := range prices {
				if symbol == "CAT.3750.AS" {
					converted[symbol] = price * 0.11 // Convert HKD to EUR
				} else {
					converted[symbol] = price
				}
			}
			return converted
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
	}

	// Execute
	prices := job.fetchCurrentPrices(securities)

	// Verify: Price converted to EUR
	eurPrice := prices["CAT.3750.AS"]
	expected := 497.4 * 0.11 // = 54.714
	assert.InDelta(t, expected, eurPrice, 0.01, "HKD price should be converted to EUR")
}

// TestFetchCurrentPrices_EUR_NoConversion verifies EUR prices are not converted
func TestFetchCurrentPrices_EUR_NoConversion(t *testing.T) {
	securities := []universe.Security{
		{Symbol: "VWS.AS", Currency: "EUR"},
	}

	eurPrice := 42.5
	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"VWS.AS": &eurPrice,
		},
	}

	// Mock conversion service that doesn't change EUR prices
	priceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			return prices // No conversion for EUR
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
	}

	prices := job.fetchCurrentPrices(securities)

	// Verify: EUR price unchanged
	assert.Equal(t, 42.5, prices["VWS.AS"], "EUR price should not be converted")
}

// TestFetchCurrentPrices_USD_Conversion verifies USD prices are converted to EUR
func TestFetchCurrentPrices_USD_Conversion(t *testing.T) {
	securities := []universe.Security{
		{Symbol: "AAPL", Currency: "USD"},
	}

	usdPrice := 150.0
	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"AAPL": &usdPrice,
		},
	}

	// Mock conversion: 1 USD = 0.93 EUR
	priceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			converted := make(map[string]float64)
			for symbol, price := range prices {
				if symbol == "AAPL" {
					converted[symbol] = price * 0.93 // Convert USD to EUR
				} else {
					converted[symbol] = price
				}
			}
			return converted
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
	}

	prices := job.fetchCurrentPrices(securities)

	expected := 150.0 * 0.93 // = 139.5 EUR
	assert.InDelta(t, expected, prices["AAPL"], 0.01, "USD price should be converted to EUR")
}

// TestFetchCurrentPrices_MissingRate_FallbackToNative verifies graceful fallback when rate unavailable
func TestFetchCurrentPrices_MissingRate_FallbackToNative(t *testing.T) {
	securities := []universe.Security{
		{Symbol: "0700.HK", Currency: "HKD"},
	}

	hkdPrice := 90.0
	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"0700.HK": &hkdPrice,
		},
	}

	// Mock conversion service that returns native price when conversion fails
	priceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			// Simulate missing rate - return native prices
			return prices
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
	}

	prices := job.fetchCurrentPrices(securities)

	// Should fallback to native price (logged warning in real implementation)
	assert.Equal(t, 90.0, prices["0700.HK"], "Should use native price when rate unavailable")
}

// TestFetchCurrentPrices_NilPriceConversionService verifies graceful handling of nil service
func TestFetchCurrentPrices_NilPriceConversionService(t *testing.T) {
	securities := []universe.Security{
		{Symbol: "CAT.3750.AS", Currency: "HKD"},
	}

	hkdPrice := 497.4
	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"CAT.3750.AS": &hkdPrice,
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: nil, // Not injected
	}

	prices := job.fetchCurrentPrices(securities)

	// Should use native price when conversion service is nil (logged warning in real implementation)
	assert.Equal(t, 497.4, prices["CAT.3750.AS"], "Should use native price when conversion service nil")
}

// TestFetchCurrentPrices_MultipleCurrencies verifies multiple currencies in single batch
func TestFetchCurrentPrices_MultipleCurrencies(t *testing.T) {
	securities := []universe.Security{
		{Symbol: "VWS.AS", Currency: "EUR"},
		{Symbol: "AAPL", Currency: "USD"},
		{Symbol: "0700.HK", Currency: "HKD"},
		{Symbol: "BARC.L", Currency: "GBP"},
	}

	eurPrice := 42.5
	usdPrice := 150.0
	hkdPrice := 90.0
	gbpPrice := 25.0

	priceClient := &MockPriceClientForConversion{
		quotes: map[string]*float64{
			"VWS.AS":  &eurPrice,
			"AAPL":    &usdPrice,
			"0700.HK": &hkdPrice,
			"BARC.L":  &gbpPrice,
		},
	}

	// Mock conversion with multiple rates
	priceConversionService := &MockPriceConversionServiceForScheduler{
		convertFunc: func(prices map[string]float64, secs []universe.Security) map[string]float64 {
			converted := make(map[string]float64)
			for symbol, price := range prices {
				switch symbol {
				case "VWS.AS":
					converted[symbol] = price // EUR unchanged
				case "AAPL":
					converted[symbol] = price * 0.93 // USD to EUR
				case "0700.HK":
					converted[symbol] = price * 0.11 // HKD to EUR
				case "BARC.L":
					converted[symbol] = price * 1.17 // GBP to EUR
				default:
					converted[symbol] = price
				}
			}
			return converted
		},
	}

	job := &BuildOpportunityContextJob{
		priceClient:            priceClient,
		priceConversionService: priceConversionService,
	}

	prices := job.fetchCurrentPrices(securities)

	// Verify all conversions
	assert.Equal(t, 42.5, prices["VWS.AS"], "EUR unchanged")
	assert.InDelta(t, 139.5, prices["AAPL"], 0.01, "USD converted")
	assert.InDelta(t, 9.9, prices["0700.HK"], 0.01, "HKD converted")
	assert.InDelta(t, 29.25, prices["BARC.L"], 0.01, "GBP converted")
}
