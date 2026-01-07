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

func TestBuildOpportunityContextJob_Name(t *testing.T) {
	job := NewBuildOpportunityContextJob(nil, nil, nil, nil, nil, nil, nil, nil)
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

	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
		mockCashManager,
		mockPriceClient,
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

	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		nil,
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

	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
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

	job := NewBuildOpportunityContextJob(
		mockPositionRepo,
		mockSecurityRepo,
		mockAllocRepo,
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
