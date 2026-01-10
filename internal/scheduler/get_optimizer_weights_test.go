package scheduler

import (
	"testing"

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
	job := NewGetOptimizerWeightsJob(nil, nil, nil, nil, nil, nil, nil, nil)
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
		{Symbol: "AAPL", YahooSymbol: "AAPL", Country: "US", Industry: "Technology", Active: true},
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
	)

	err := job.Run()
	require.NoError(t, err)
	assert.True(t, optimizeCalled, "Optimize should have been called")
}

func TestGetOptimizerWeightsJob_Run_NoOptimizerService(t *testing.T) {
	job := NewGetOptimizerWeightsJob(nil, nil, nil, nil, nil, nil, nil, nil)
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
	)

	err := job.Run()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "optimizer failed")
}

// Helper function
func floatPtr(f float64) *float64 {
	return &f
}
