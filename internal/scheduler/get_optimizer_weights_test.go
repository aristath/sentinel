package scheduler

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockPositionRepoForOptimizer is a mock implementation of PositionRepositoryInterface
type MockPositionRepoForOptimizer struct {
	GetAllFunc func() ([]interface{}, error)
}

func (m *MockPositionRepoForOptimizer) GetAll() ([]interface{}, error) {
	if m.GetAllFunc != nil {
		return m.GetAllFunc()
	}
	return []interface{}{}, nil
}

// MockSecurityRepoForOptimizer is a mock implementation of SecurityRepositoryInterface
type MockSecurityRepoForOptimizer struct {
	GetAllActiveFunc func() ([]interface{}, error)
}

func (m *MockSecurityRepoForOptimizer) GetAllActive() ([]interface{}, error) {
	if m.GetAllActiveFunc != nil {
		return m.GetAllActiveFunc()
	}
	return []interface{}{}, nil
}

// MockAllocationRepoForOptimizer is a mock implementation of AllocationRepositoryInterface
type MockAllocationRepoForOptimizer struct {
	GetAllFunc func() (map[string]float64, error)
}

func (m *MockAllocationRepoForOptimizer) GetAll() (map[string]float64, error) {
	if m.GetAllFunc != nil {
		return m.GetAllFunc()
	}
	return map[string]float64{}, nil
}

// MockCashManagerForOptimizer is a mock implementation of CashManagerInterface
type MockCashManagerForOptimizer struct {
	GetAllCashBalancesFunc func() (map[string]float64, error)
}

func (m *MockCashManagerForOptimizer) GetAllCashBalances() (map[string]float64, error) {
	if m.GetAllCashBalancesFunc != nil {
		return m.GetAllCashBalancesFunc()
	}
	return map[string]float64{}, nil
}

// MockPriceClient is a mock implementation of PriceClientInterface
type MockPriceClient struct {
	GetBatchQuotesFunc func(symbolMap map[string]*string) (map[string]*float64, error)
}

func (m *MockPriceClient) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if m.GetBatchQuotesFunc != nil {
		return m.GetBatchQuotesFunc(symbolMap)
	}
	return make(map[string]*float64), nil
}

// MockOptimizerService is a mock implementation of OptimizerServiceInterface
type MockOptimizerService struct {
	OptimizeFunc func(state interface{}, settings interface{}) (interface{}, error)
}

func (m *MockOptimizerService) Optimize(state interface{}, settings interface{}) (interface{}, error) {
	if m.OptimizeFunc != nil {
		return m.OptimizeFunc(state, settings)
	}
	return nil, nil
}

func TestGetOptimizerWeightsJob_Name(t *testing.T) {
	job := NewGetOptimizerWeightsJob(nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	assert.Equal(t, "get_optimizer_weights", job.Name())
}

func TestGetOptimizerWeightsJob_Run_Success(t *testing.T) {
	// Mock position repo
	positions := []portfolio.Position{
		{Symbol: "AAPL", Quantity: 10},
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
		{ISIN: "US0378331005", Symbol: "AAPL", Geography: "US", Industry: "Technology"},
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

	// Mock optimizer service
	optimizeCalled := false
	mockOptimizerService := &MockOptimizerService{
		OptimizeFunc: func(state interface{}, settings interface{}) (interface{}, error) {
			optimizeCalled = true
			return &optimization.Result{
				Success:       true,
				TargetWeights: map[string]float64{"AAPL": 0.5},
			}, nil
		},
	}

	job := NewGetOptimizerWeightsJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockCashManager,
		mockPriceClient,
		mockOptimizerService,
		nil, // priceConversionService
		nil, // plannerConfigRepo
		nil, // clientDataRepo
		nil, // marketHoursService
	)

	err := job.Run()
	require.NoError(t, err)
	assert.True(t, optimizeCalled, "Optimize should have been called")
}

func TestGetOptimizerWeightsJob_Run_NoOptimizerService(t *testing.T) {
	job := NewGetOptimizerWeightsJob(nil, nil, nil, nil, nil, nil, nil, nil, nil, nil)
	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "optimizer service not available")
}

func TestGetOptimizerWeightsJob_Run_PositionRepoError(t *testing.T) {
	mockPositionRepo := &MockPositionRepoForOptimizer{
		GetAllFunc: func() ([]interface{}, error) {
			return nil, assert.AnError
		},
	}

	mockOptimizerService := &MockOptimizerService{}

	job := NewGetOptimizerWeightsJob(
		mockPositionRepo,
		nil,
		nil,
		nil,
		nil,
		mockOptimizerService,
		nil, // priceConversionService
		nil, // plannerConfigRepo
		nil, // clientDataRepo
		nil, // marketHoursService
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get positions")
}

func TestGetOptimizerWeightsJob_Run_SecurityRepoError(t *testing.T) {
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

	mockOptimizerService := &MockOptimizerService{}

	job := NewGetOptimizerWeightsJob(
		mockPositionRepo,
		mockSecurityRepo,
		nil,
		nil,
		nil,
		mockOptimizerService,
		nil, // priceConversionService
		nil, // plannerConfigRepo
		nil, // clientDataRepo
		nil, // marketHoursService
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get securities")
}

func TestGetOptimizerWeightsJob_Run_AllocationRepoError(t *testing.T) {
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

	mockOptimizerService := &MockOptimizerService{}

	job := NewGetOptimizerWeightsJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		nil,
		nil,
		mockOptimizerService,
		nil, // priceConversionService
		nil, // plannerConfigRepo
		nil, // clientDataRepo
		nil, // marketHoursService
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get allocations")
}

func TestGetOptimizerWeightsJob_Run_OptimizerError(t *testing.T) {
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
			return map[string]float64{}, nil
		},
	}

	mockCashManager := &MockCashManagerForOptimizer{
		GetAllCashBalancesFunc: func() (map[string]float64, error) {
			return map[string]float64{"EUR": 1000.0}, nil
		},
	}

	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return map[string]*float64{}, nil
		},
	}

	mockOptimizerService := &MockOptimizerService{
		OptimizeFunc: func(state interface{}, settings interface{}) (interface{}, error) {
			return nil, assert.AnError
		},
	}

	job := NewGetOptimizerWeightsJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockCashManager,
		mockPriceClient,
		mockOptimizerService,
		nil, // priceConversionService
		nil, // plannerConfigRepo
		nil, // clientDataRepo
		nil, // marketHoursService
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "optimizer failed")
}

// Helper function
func floatPtr(f float64) *float64 {
	return &f
}

// MockClientDataRepository is a mock implementation of ClientDataRepositoryInterface
type MockClientDataRepository struct {
	GetIfFreshFunc func(table, key string) (json.RawMessage, error)
	GetFunc        func(table, key string) (json.RawMessage, error)
	StoreFunc      func(table, key string, data interface{}, ttl time.Duration) error
	StoredData     map[string]json.RawMessage // Track what was stored
	StoredTTLs     map[string]time.Duration   // Track TTLs used
}

func (m *MockClientDataRepository) GetIfFresh(table, key string) (json.RawMessage, error) {
	if m.GetIfFreshFunc != nil {
		return m.GetIfFreshFunc(table, key)
	}
	return nil, nil
}

func (m *MockClientDataRepository) Get(table, key string) (json.RawMessage, error) {
	if m.GetFunc != nil {
		return m.GetFunc(table, key)
	}
	return nil, nil
}

func (m *MockClientDataRepository) Store(table, key string, data interface{}, ttl time.Duration) error {
	if m.StoreFunc != nil {
		return m.StoreFunc(table, key, data, ttl)
	}
	if m.StoredData == nil {
		m.StoredData = make(map[string]json.RawMessage)
	}
	if m.StoredTTLs == nil {
		m.StoredTTLs = make(map[string]time.Duration)
	}
	jsonData, _ := json.Marshal(data)
	m.StoredData[table+":"+key] = jsonData
	m.StoredTTLs[table+":"+key] = ttl
	return nil
}

// MockMarketHoursService is a mock implementation of MarketHoursServiceInterface
type MockMarketHoursService struct {
	AnyMajorMarketOpenFunc func(t time.Time) bool
}

func (m *MockMarketHoursService) AnyMajorMarketOpen(t time.Time) bool {
	if m.AnyMajorMarketOpenFunc != nil {
		return m.AnyMajorMarketOpenFunc(t)
	}
	return false
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_CacheHit(t *testing.T) {
	// Setup: All prices are cached
	cachedPrice := 150.0
	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			if table == "current_prices" {
				data, _ := json.Marshal(cachedPrice)
				return data, nil
			}
			return nil, nil
		},
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return true // Markets open
		},
	}

	// Price client should NOT be called when cache hit
	priceClientCalled := false
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			priceClientCalled = true
			return map[string]*float64{}, nil
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil, nil, nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
	}

	prices := job.fetchCurrentPrices(securities)

	assert.False(t, priceClientCalled, "Price client should not be called on cache hit")
	assert.Equal(t, cachedPrice, prices["US0378331005"], "Should return cached price")
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_CacheMiss(t *testing.T) {
	// Setup: No cached prices
	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			return nil, nil // Cache miss
		},
		StoredData: make(map[string]json.RawMessage),
		StoredTTLs: make(map[string]time.Duration),
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return true // Markets open
		},
	}

	// Price client should be called
	fetchedPrice := 150.0
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return map[string]*float64{
				"AAPL": &fetchedPrice,
			}, nil
		},
	}

	// Mock price conversion service
	mockPriceConversion := &MockPriceConversionService{
		ConvertPricesToEURFunc: func(prices map[string]float64, securities []universe.Security) map[string]float64 {
			// Return same prices (assume EUR)
			return prices
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil,
		mockPriceConversion,
		nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
	}

	prices := job.fetchCurrentPrices(securities)

	assert.Equal(t, fetchedPrice, prices["US0378331005"], "Should return fetched price")
	// Verify price was stored in cache
	assert.Contains(t, mockClientDataRepo.StoredData, "current_prices:US0378331005", "Should store fetched price in cache")
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_PartialCache(t *testing.T) {
	// Setup: One price cached, one not
	cachedPrice := 150.0
	fetchedPrice := 200.0

	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			if key == "US0378331005" { // AAPL cached
				data, _ := json.Marshal(cachedPrice)
				return data, nil
			}
			return nil, nil // GOOGL not cached
		},
		StoredData: make(map[string]json.RawMessage),
		StoredTTLs: make(map[string]time.Duration),
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return true
		},
	}

	// Price client should only be called for missing prices
	var fetchedSymbols []string
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			for symbol := range symbolMap {
				fetchedSymbols = append(fetchedSymbols, symbol)
			}
			return map[string]*float64{
				"GOOGL": &fetchedPrice,
			}, nil
		},
	}

	mockPriceConversion := &MockPriceConversionService{
		ConvertPricesToEURFunc: func(prices map[string]float64, securities []universe.Security) map[string]float64 {
			return prices
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil,
		mockPriceConversion,
		nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
		{ISIN: "US02079K3059", Symbol: "GOOGL", Currency: "USD"},
	}

	prices := job.fetchCurrentPrices(securities)

	assert.Equal(t, cachedPrice, prices["US0378331005"], "AAPL should return cached price")
	assert.Equal(t, fetchedPrice, prices["US02079K3059"], "GOOGL should return fetched price")
	assert.Equal(t, []string{"GOOGL"}, fetchedSymbols, "Should only fetch GOOGL")
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_MarketOpenTTL(t *testing.T) {
	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			return nil, nil // Cache miss
		},
		StoredData: make(map[string]json.RawMessage),
		StoredTTLs: make(map[string]time.Duration),
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return true // Markets OPEN
		},
	}

	fetchedPrice := 150.0
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return map[string]*float64{"AAPL": &fetchedPrice}, nil
		},
	}

	mockPriceConversion := &MockPriceConversionService{
		ConvertPricesToEURFunc: func(prices map[string]float64, securities []universe.Security) map[string]float64 {
			return prices
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil,
		mockPriceConversion,
		nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
	}

	job.fetchCurrentPrices(securities)

	// When markets are open, TTL should be 30 minutes
	expectedTTL := 30 * time.Minute
	actualTTL := mockClientDataRepo.StoredTTLs["current_prices:US0378331005"]
	assert.Equal(t, expectedTTL, actualTTL, "Should use 30 minute TTL when markets are open")
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_MarketClosedTTL(t *testing.T) {
	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			return nil, nil // Cache miss
		},
		StoredData: make(map[string]json.RawMessage),
		StoredTTLs: make(map[string]time.Duration),
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return false // Markets CLOSED
		},
	}

	fetchedPrice := 150.0
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return map[string]*float64{"AAPL": &fetchedPrice}, nil
		},
	}

	mockPriceConversion := &MockPriceConversionService{
		ConvertPricesToEURFunc: func(prices map[string]float64, securities []universe.Security) map[string]float64 {
			return prices
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil,
		mockPriceConversion,
		nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
	}

	job.fetchCurrentPrices(securities)

	// When markets are closed, TTL should be 24 hours
	expectedTTL := 24 * time.Hour
	actualTTL := mockClientDataRepo.StoredTTLs["current_prices:US0378331005"]
	assert.Equal(t, expectedTTL, actualTTL, "Should use 24 hour TTL when markets are closed")
}

func TestGetOptimizerWeightsJob_FetchCurrentPrices_APIFallbackToStale(t *testing.T) {
	stalePrice := 145.0 // Stale cached price

	mockClientDataRepo := &MockClientDataRepository{
		GetIfFreshFunc: func(table, key string) (json.RawMessage, error) {
			return nil, nil // No fresh cache
		},
		GetFunc: func(table, key string) (json.RawMessage, error) {
			// Return stale data
			data, _ := json.Marshal(stalePrice)
			return data, nil
		},
	}

	mockMarketHours := &MockMarketHoursService{
		AnyMajorMarketOpenFunc: func(t time.Time) bool {
			return true
		},
	}

	// API fails
	mockPriceClient := &MockPriceClient{
		GetBatchQuotesFunc: func(symbolMap map[string]*string) (map[string]*float64, error) {
			return nil, assert.AnError // API error
		},
	}

	job := NewGetOptimizerWeightsJob(
		nil, nil, nil, nil,
		mockPriceClient,
		nil, nil, nil,
		mockClientDataRepo,
		mockMarketHours,
	)

	securities := []universe.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Currency: "USD"},
	}

	prices := job.fetchCurrentPrices(securities)

	// Should fallback to stale cache
	assert.Equal(t, stalePrice, prices["US0378331005"], "Should return stale cached price when API fails")
}

// MockPriceConversionService is a mock implementation of PriceConversionServiceInterface
type MockPriceConversionService struct {
	ConvertPricesToEURFunc func(prices map[string]float64, securities []universe.Security) map[string]float64
}

func (m *MockPriceConversionService) ConvertPricesToEUR(prices map[string]float64, securities []universe.Security) map[string]float64 {
	if m.ConvertPricesToEURFunc != nil {
		return m.ConvertPricesToEURFunc(prices, securities)
	}
	return prices
}
