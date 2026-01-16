package portfolio

import (
	"database/sql"
	"errors"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockCashManager is a mock cash manager for testing
type MockCashManager struct {
	mock.Mock
}

func (m *MockCashManager) UpdateCashPosition(currency string, balance float64) error {
	args := m.Called(currency, balance)
	return args.Error(0)
}

func (m *MockCashManager) GetAllCashBalances() (map[string]float64, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]float64), args.Error(1)
}

func (m *MockCashManager) GetCashBalance(currency string) (float64, error) {
	args := m.Called(currency)
	return args.Get(0).(float64), args.Error(1)
}

// MockTradernetClient is a mock broker client for testing
type MockTradernetClient struct {
	mock.Mock
}

func (m *MockTradernetClient) GetPortfolio() ([]domain.BrokerPosition, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerPosition), args.Error(1)
}

func (m *MockTradernetClient) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerCashBalance), args.Error(1)
}

func (m *MockTradernetClient) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	args := m.Called(limit)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerTrade), args.Error(1)
}

func (m *MockTradernetClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	args := m.Called(symbol, side, quantity, limitPrice)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerOrderResult), args.Error(1)
}

func (m *MockTradernetClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerPendingOrder), args.Error(1)
}

func (m *MockTradernetClient) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	args := m.Called(symbol)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerQuote), args.Error(1)
}

func (m *MockTradernetClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	args := m.Called(symbol, exchange)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerSecurityInfo), args.Error(1)
}

func (m *MockTradernetClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	args := m.Called(baseCurrency, currencies)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]float64), args.Error(1)
}

func (m *MockTradernetClient) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	args := m.Called(limit)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerCashFlow), args.Error(1)
}

func (m *MockTradernetClient) GetCashMovements() (*domain.BrokerCashMovement, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerCashMovement), args.Error(1)
}

func (m *MockTradernetClient) IsConnected() bool {
	args := m.Called()
	return args.Bool(0)
}

func (m *MockTradernetClient) HealthCheck() (*domain.BrokerHealthResult, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerHealthResult), args.Error(1)
}

func (m *MockTradernetClient) SetCredentials(apiKey, apiSecret string) {
	m.Called(apiKey, apiSecret)
}

func (m *MockTradernetClient) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	args := m.Called(symbol)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerOrderBook), args.Error(1)
}

func (m *MockTradernetClient) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	args := m.Called(symbols)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]*domain.BrokerQuote), args.Error(1)
}

func (m *MockTradernetClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	args := m.Called(symbol, start, end, timeframeSeconds)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]domain.BrokerOHLCV), args.Error(1)
}

func (m *MockTradernetClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	args := m.Called(symbol)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.BrokerSecurityInfo), args.Error(1)
}

// MockPositionRepository is a mock position repository for testing
type MockPositionRepository struct {
	mock.Mock
}

func (m *MockPositionRepository) GetAll() ([]Position, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]Position), args.Error(1)
}

func (m *MockPositionRepository) GetWithSecurityInfo() ([]PositionWithSecurity, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]PositionWithSecurity), args.Error(1)
}

func (m *MockPositionRepository) Upsert(position Position) error {
	args := m.Called(position)
	return args.Error(0)
}

func (m *MockPositionRepository) GetBySymbol(symbol string) (*Position, error) {
	args := m.Called(symbol)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	if pos, ok := args.Get(0).(*Position); ok {
		return pos, args.Error(1)
	}
	return nil, args.Error(1)
}

func (m *MockPositionRepository) Delete(symbol string) error {
	args := m.Called(symbol)
	return args.Error(0)
}

// Additional methods required by PositionRepositoryInterface

func (m *MockPositionRepository) GetByISIN(isin string) (*Position, error) {
	args := m.Called(isin)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	if pos, ok := args.Get(0).(*Position); ok {
		return pos, args.Error(1)
	}
	return nil, args.Error(1)
}

func (m *MockPositionRepository) GetByIdentifier(identifier string) (*Position, error) {
	args := m.Called(identifier)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	if pos, ok := args.Get(0).(*Position); ok {
		return pos, args.Error(1)
	}
	return nil, args.Error(1)
}

func (m *MockPositionRepository) GetCount() (int, error) {
	args := m.Called()
	return args.Int(0), args.Error(1)
}

func (m *MockPositionRepository) GetTotalValue() (float64, error) {
	args := m.Called()
	return args.Get(0).(float64), args.Error(1)
}

func (m *MockPositionRepository) DeleteAll() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockPositionRepository) UpdatePrice(isin string, price float64, currencyRate float64) error {
	args := m.Called(isin, price, currencyRate)
	return args.Error(0)
}

func (m *MockPositionRepository) UpdateLastSoldAt(isin string) error {
	args := m.Called(isin)
	return args.Error(0)
}

func TestSyncFromTradernet_Success(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with securities (required for ISIN lookup)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	// Create securities table with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert test securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp.'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	// Mock data
	tradernetPositions := []domain.BrokerPosition{
		{
			Symbol:         "AAPL",
			Quantity:       10,
			AvgPrice:       150.0,
			CurrentPrice:   160.0,
			Currency:       "USD",
			CurrencyRate:   1.1,
			MarketValueEUR: 1454.54,
		},
		{
			Symbol:         "MSFT",
			Quantity:       5,
			AvgPrice:       300.0,
			CurrentPrice:   320.0,
			Currency:       "USD",
			CurrencyRate:   1.1,
			MarketValueEUR: 1454.54,
		},
	}

	currentPositions := []Position{}

	cashBalances := []domain.BrokerCashBalance{
		{Currency: "EUR", Amount: 1000.0},
		{Currency: "USD", Amount: 500.0},
	}

	// Mock expectations
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(currentPositions, nil)
	mockPositionRepo.On("Upsert", mock.AnythingOfType("Position")).Return(nil).Times(2)
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	mockCashManager.On("UpdateCashPosition", "EUR", 1000.0).Return(nil).Once()
	mockCashManager.On("UpdateCashPosition", "USD", 500.0).Return(nil).Once()

	// Execute
	err = service.SyncFromTradernet()

	// Assert
	assert.NoError(t, err)
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

func TestSyncFromTradernet_DeleteStale(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with securities (required for ISIN lookup)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	// Create securities table with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert test securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	// Mock data - Tradernet has AAPL, DB has AAPL and MSFT (MSFT is stale)
	tradernetPositions := []domain.BrokerPosition{
		{
			Symbol:         "AAPL",
			Quantity:       10,
			AvgPrice:       150.0,
			CurrentPrice:   160.0,
			Currency:       "USD",
			CurrencyRate:   1.1,
			MarketValueEUR: 1454.54,
		},
	}

	currentPositions := []Position{
		{Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
		{Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5}, // Stale - not in Tradernet
	}

	cashBalances := []domain.BrokerCashBalance{}

	// Mock expectations
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(currentPositions, nil)
	mockPositionRepo.On("Upsert", mock.AnythingOfType("Position")).Return(nil).Once()
	mockPositionRepo.On("Delete", "US5949181045").Return(nil).Once() // Delete by ISIN
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	mockCashManager.On("UpdateCashPosition", mock.Anything, mock.Anything).Return(nil)

	// Execute
	err = service.SyncFromTradernet()

	// Assert
	assert.NoError(t, err)
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
	mockPositionRepo.AssertCalled(t, "Delete", "US5949181045") // Delete by ISIN
}

func TestSyncFromTradernet_SkipZeroQuantity(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with securities (required for ISIN lookup)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	// Create securities table with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert test securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	// Mock data - one position with zero quantity
	tradernetPositions := []domain.BrokerPosition{
		{
			Symbol:   "AAPL",
			Quantity: 10,
			AvgPrice: 150.0,
		},
		{
			Symbol:   "MSFT",
			Quantity: 0, // Should be skipped
			AvgPrice: 300.0,
		},
	}

	currentPositions := []Position{}
	cashBalances := []domain.BrokerCashBalance{}

	// Mock expectations - Upsert should only be called once (for AAPL)
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(currentPositions, nil)
	mockPositionRepo.On("Upsert", mock.AnythingOfType("Position")).Return(nil).Once()
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	mockCashManager.On("UpdateCashPosition", mock.Anything, mock.Anything).Return(nil)

	// Execute
	err = service.SyncFromTradernet()

	// Assert
	assert.NoError(t, err)
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

func TestSyncFromTradernet_TradernetError(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &PortfolioService{
		brokerClient: mockTradernetClient,
		log:          log,
	}

	// Mock expectations - Tradernet API error
	mockTradernetClient.On("GetPortfolio").Return(nil, errors.New("tradernet api error"))

	// Execute
	err := service.SyncFromTradernet()

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to fetch portfolio from Tradernet")
	mockTradernetClient.AssertExpectations(t)
}

func TestSyncFromTradernet_NilClient(t *testing.T) {
	// Setup
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &PortfolioService{
		brokerClient: nil,
		log:          log,
	}

	// Execute
	err := service.SyncFromTradernet()

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "tradernet client not available")
}

func TestSyncFromTradernet_RepositoryError(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	service := &PortfolioService{
		brokerClient: mockTradernetClient,
		positionRepo: mockPositionRepo,
		cashManager:  mockCashManager,
		log:          log,
	}

	tradernetPositions := []domain.BrokerPosition{
		{Symbol: "AAPL", Quantity: 10},
	}

	// Mock expectations - GetAll fails
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(nil, errors.New("database error"))

	// Execute
	err := service.SyncFromTradernet()

	// Assert
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get current positions")
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

func TestSyncFromTradernet_UpsertError(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with securities (required for ISIN lookup)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	// Create securities table with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert test securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp.'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	tradernetPositions := []domain.BrokerPosition{
		{Symbol: "AAPL", Quantity: 10},
		{Symbol: "MSFT", Quantity: 5},
	}

	currentPositions := []Position{}
	cashBalances := []domain.BrokerCashBalance{}

	// Mock expectations - Upsert fails for first position but succeeds for second
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(currentPositions, nil)
	mockPositionRepo.On("Upsert", mock.MatchedBy(func(p Position) bool {
		return p.Symbol == "AAPL"
	})).Return(errors.New("database error")).Once()
	mockPositionRepo.On("Upsert", mock.MatchedBy(func(p Position) bool {
		return p.Symbol == "MSFT"
	})).Return(nil).Once()
	mockTradernetClient.On("GetCashBalances").Return(cashBalances, nil)
	mockCashManager.On("UpdateCashPosition", mock.Anything, mock.Anything).Return(nil)

	// Execute
	err = service.SyncFromTradernet()

	// Assert - Should not error, just log and continue
	assert.NoError(t, err)
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

func TestSyncFromTradernet_CashBalancesError(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with securities (required for ISIN lookup)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	// Create securities table with JSON storage (migration 038)
	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert test securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	tradernetPositions := []domain.BrokerPosition{
		{Symbol: "AAPL", Quantity: 10},
	}

	currentPositions := []Position{}

	// Mock expectations - GetCashBalances fails
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockPositionRepo.On("GetAll").Return(currentPositions, nil)
	mockPositionRepo.On("Upsert", mock.AnythingOfType("Position")).Return(nil).Once()
	mockTradernetClient.On("GetCashBalances").Return(nil, errors.New("cash balances error"))

	// Execute
	err = service.SyncFromTradernet()

	// Assert - Should not error, just warn and continue
	assert.NoError(t, err)
	mockTradernetClient.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

// Mock AllocationTargetProvider for testing GetPortfolioSummary

type MockAllocationTargetProvider struct {
	mock.Mock
}

func (m *MockAllocationTargetProvider) GetAll() (map[string]float64, error) {
	args := m.Called()
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(map[string]float64), args.Error(1)
}

// TestGetPortfolioSummary_Success tests successful portfolio summary calculation
func TestGetPortfolioSummary_Success(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockAllocRepo := new(MockAllocationTargetProvider)
	mockPositionRepo := new(MockPositionRepository)

	// Setup test data
	targets := map[string]float64{
		"geography:USA":          0.60,
		"geography:Germany":      0.30,
		"geography:Japan":        0.10,
		"industry:Technology":    0.40,
		"industry:Finance":       0.30,
		"industry:Healthcare":    0.20,
		"industry:Manufacturing": 0.10,
	}

	positions := []PositionWithSecurity{
		{
			Symbol:         "AAPL",
			Quantity:       10,
			AvgPrice:       150.0,
			CurrentPrice:   160.0,
			MarketValueEUR: 1600.0,
			Geography:      "USA",
			Industry:       "Technology",
		},
		{
			Symbol:         "SAP",
			Quantity:       20,
			AvgPrice:       100.0,
			CurrentPrice:   110.0,
			MarketValueEUR: 2200.0,
			Geography:      "Germany",
			Industry:       "Technology",
		},
		{
			Symbol:         "JPM",
			Quantity:       5,
			AvgPrice:       140.0,
			CurrentPrice:   150.0,
			MarketValueEUR: 750.0,
			Geography:      "USA",
			Industry:       "Finance",
		},
	}

	// Mock expectations
	mockAllocRepo.On("GetAll").Return(targets, nil)
	mockPositionRepo.On("GetWithSecurityInfo").Return(positions, nil)

	// Create service with mocked dependencies
	// Note: We need a real database connection for getAllSecurityCountriesAndIndustries
	// For now, we'll test the parts we can with mocks
	service := &PortfolioService{
		allocRepo:    mockAllocRepo,
		positionRepo: mockPositionRepo,
		log:          log,
	}

	// Define all known geographies and industries for aggregation
	allGeographies := map[string]bool{"USA": true, "Germany": true, "Japan": true}
	allIndustries := map[string]bool{"Technology": true, "Finance": true, "Healthcare": true, "Manufacturing": true}

	// Test aggregatePositionValues directly (doesn't need DB)
	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	// Verify aggregations
	assert.Equal(t, 2350.0, geographyValues["USA"])       // AAPL (1600) + JPM (750)
	assert.Equal(t, 2200.0, geographyValues["Germany"])   // SAP (2200)
	assert.Equal(t, 3800.0, industryValues["Technology"]) // AAPL (1600) + SAP (2200)
	assert.Equal(t, 750.0, industryValues["Finance"])     // JPM (750)
	assert.Equal(t, 4550.0, totalValue)
}

// TestAggregatePositionValues_MultipleIndustries tests splitting value across multiple industries
func TestAggregatePositionValues_MultipleIndustries(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "AAPL",
			Quantity:       10,
			CurrentPrice:   100.0,
			MarketValueEUR: 1000.0,
			Geography:      "USA",
			Industry:       "Technology, Manufacturing", // Multiple industries
		},
	}

	allGeographies := map[string]bool{"USA": true}
	allIndustries := map[string]bool{"Technology": true, "Manufacturing": true}

	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	assert.Equal(t, 1000.0, geographyValues["USA"])
	assert.Equal(t, 500.0, industryValues["Technology"])    // Split 50/50
	assert.Equal(t, 500.0, industryValues["Manufacturing"]) // Split 50/50
	assert.Equal(t, 1000.0, totalValue)
}

// TestAggregatePositionValues_EmptyIndustry tests that securities without industry
// have their value split equally across ALL known industries
func TestAggregatePositionValues_EmptyIndustry(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "UNKNOWN",
			Quantity:       10,
			CurrentPrice:   50.0,
			MarketValueEUR: 500.0,
			Geography:      "USA",
			Industry:       "", // Empty industry - should count as ALL
		},
	}

	allGeographies := map[string]bool{"USA": true}
	allIndustries := map[string]bool{
		"Technology": true,
		"Finance":    true,
	}

	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	assert.Equal(t, 500.0, geographyValues["USA"])
	// Empty industry should split across ALL industries
	assert.InDelta(t, 250.0, industryValues["Technology"], 0.01) // 500 / 2
	assert.InDelta(t, 250.0, industryValues["Finance"], 0.01)    // 500 / 2
	assert.Equal(t, 500.0, totalValue)
}

// TestAggregatePositionValues_ZeroMarketValue tests fallback to quantity * price
func TestAggregatePositionValues_ZeroMarketValue(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "TEST",
			Quantity:       10,
			AvgPrice:       50.0,
			CurrentPrice:   60.0,
			MarketValueEUR: 0, // Zero, should fallback to qty * current_price
			Geography:      "USA",
			Industry:       "Technology",
		},
	}

	allGeographies := map[string]bool{"USA": true}
	allIndustries := map[string]bool{"Technology": true}

	_, _, totalValue := service.aggregatePositionValues(positions, allGeographies, allIndustries)

	// Should use quantity * current_price = 10 * 60 = 600
	assert.Equal(t, 600.0, totalValue)
}

// TestAggregatePositionValues_ZeroPrices tests fallback to avg_price when current_price is zero
func TestAggregatePositionValues_ZeroPrices(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "TEST",
			Quantity:       10,
			AvgPrice:       50.0,
			CurrentPrice:   0, // Zero current price, should use avg_price
			MarketValueEUR: 0,
			Geography:      "USA",
			Industry:       "Technology",
		},
	}

	allGeographies := map[string]bool{"USA": true}
	allIndustries := map[string]bool{"Technology": true}

	_, _, totalValue := service.aggregatePositionValues(positions, allGeographies, allIndustries)

	// Should use quantity * avg_price = 10 * 50 = 500
	assert.Equal(t, 500.0, totalValue)
}

// TestBuildGeographyAllocations tests geography allocation calculation
func TestBuildGeographyAllocations(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	targets := map[string]float64{
		"geography:USA":     0.60,
		"geography:Germany": 0.30,
		"geography:Japan":   0.10,
	}

	geographyValues := map[string]float64{
		"USA":     7000.0,
		"Germany": 2000.0,
		"Japan":   1000.0,
	}

	totalValue := 10000.0

	allStockGeographies := map[string]bool{
		"USA":     true,
		"Germany": true,
		"Japan":   true,
		"France":  true, // Has no current value but has stocks
	}

	allocations := service.buildGeographyAllocations(targets, geographyValues, totalValue, allStockGeographies)

	// Should have 4 allocations (USA, Germany, Japan, France)
	assert.Equal(t, 4, len(allocations))

	// Find USA allocation
	var usaAlloc AllocationStatus
	for _, alloc := range allocations {
		if alloc.Name == "USA" {
			usaAlloc = alloc
			break
		}
	}

	assert.Equal(t, "geography", usaAlloc.Category)
	assert.Equal(t, "USA", usaAlloc.Name)
	assert.Equal(t, 0.60, usaAlloc.TargetPct)
	assert.Equal(t, 0.70, usaAlloc.CurrentPct) // 7000/10000 = 0.70
	assert.Equal(t, 7000.0, usaAlloc.CurrentValue)
	assert.Equal(t, 0.10, usaAlloc.Deviation) // 0.70 - 0.60 = 0.10 (over-allocated)

	// Find France allocation (should be zero but included)
	var franceAlloc AllocationStatus
	for _, alloc := range allocations {
		if alloc.Name == "France" {
			franceAlloc = alloc
			break
		}
	}

	assert.Equal(t, 0.0, franceAlloc.TargetPct)
	assert.Equal(t, 0.0, franceAlloc.CurrentPct)
	assert.Equal(t, 0.0, franceAlloc.CurrentValue)
	assert.Equal(t, 0.0, franceAlloc.Deviation)
}

// TestBuildIndustryAllocations tests industry allocation calculation
func TestBuildIndustryAllocations(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	targets := map[string]float64{
		"industry:Technology":    0.40,
		"industry:Finance":       0.30,
		"industry:Healthcare":    0.20,
		"industry:Manufacturing": 0.10,
	}

	industryValues := map[string]float64{
		"Technology":    5000.0,
		"Finance":       3000.0,
		"Healthcare":    1500.0,
		"Manufacturing": 500.0,
	}

	totalValue := 10000.0

	allStockIndustries := map[string]bool{
		"Technology":    true,
		"Finance":       true,
		"Healthcare":    true,
		"Manufacturing": true,
		"Energy":        true, // Has no current value
	}

	allocations := service.buildIndustryAllocations(targets, industryValues, totalValue, allStockIndustries)

	// Should have 5 allocations
	assert.Equal(t, 5, len(allocations))

	// Find Technology allocation
	var techAlloc AllocationStatus
	for _, alloc := range allocations {
		if alloc.Name == "Technology" {
			techAlloc = alloc
			break
		}
	}

	assert.Equal(t, "industry", techAlloc.Category)
	assert.Equal(t, "Technology", techAlloc.Name)
	assert.Equal(t, 0.40, techAlloc.TargetPct)
	assert.Equal(t, 0.50, techAlloc.CurrentPct) // 5000/10000 = 0.50
	assert.Equal(t, 5000.0, techAlloc.CurrentValue)
	assert.Equal(t, 0.10, techAlloc.Deviation) // 0.50 - 0.40 = 0.10 (over-allocated)
}

// TestBuildAllocations_ZeroTotalValue tests handling of zero total value
func TestBuildAllocations_ZeroTotalValue(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	targets := map[string]float64{
		"geography:USA": 0.60,
	}

	geographyValues := map[string]float64{
		"USA": 0.0,
	}

	totalValue := 0.0

	allStockGeographies := map[string]bool{
		"USA": true,
	}

	allocations := service.buildGeographyAllocations(targets, geographyValues, totalValue, allStockGeographies)

	assert.Equal(t, 1, len(allocations))
	assert.Equal(t, 0.0, allocations[0].CurrentPct) // Should be 0, not NaN or error
	assert.Equal(t, 0.60, allocations[0].TargetPct)
	assert.Equal(t, -0.60, allocations[0].Deviation)
}

// TestRound tests the round helper function
func TestRound(t *testing.T) {
	tests := []struct {
		name     string
		val      float64
		decimals int
		expected float64
	}{
		{
			name:     "round to 2 decimals",
			val:      123.456789,
			decimals: 2,
			expected: 123.46,
		},
		{
			name:     "round to 0 decimals",
			val:      123.456789,
			decimals: 0,
			expected: 123.0,
		},
		{
			name:     "round to 4 decimals",
			val:      123.456789,
			decimals: 4,
			expected: 123.4568,
		},
		{
			name:     "round negative number",
			val:      -123.456789,
			decimals: 2,
			expected: -123.46,
		},
		{
			name:     "round zero",
			val:      0.0,
			decimals: 2,
			expected: 0.0,
		},
		{
			name:     "round very small number",
			val:      0.000001,
			decimals: 6,
			expected: 0.000001,
		},
		{
			name:     "round large number",
			val:      999999.123456,
			decimals: 2,
			expected: 999999.12,
		},
		{
			name:     "round with exact decimal",
			val:      123.45,
			decimals: 2,
			expected: 123.45,
		},
		{
			name:     "round with 5 rounding up",
			val:      123.445,
			decimals: 2,
			expected: 123.45,
		},
		{
			name:     "round to negative decimals (edge case)",
			val:      123.456,
			decimals: -1,
			expected: 120.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := round(tt.val, tt.decimals)
			assert.InDelta(t, tt.expected, result, 0.0001, "round(%v, %d) = %v, want %v", tt.val, tt.decimals, result, tt.expected)
		})
	}
}

// TestGetPortfolioSummary_AllocationTargetError tests error handling
func TestGetPortfolioSummary_AllocationTargetError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockAllocRepo := new(MockAllocationTargetProvider)
	mockAllocRepo.On("GetAll").Return(nil, errors.New("database error"))

	service := &PortfolioService{
		allocRepo: mockAllocRepo,
		log:       log,
	}

	_, err := service.GetPortfolioSummary()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get allocation targets")
	mockAllocRepo.AssertExpectations(t)
}

// TestGetPortfolioSummary_PositionError tests error handling for position retrieval
func TestSyncFromTradernet_SkipPositionWithoutISIN(t *testing.T) {
	// Setup
	mockTradernetClient := new(MockTradernetClient)
	mockPositionRepo := new(MockPositionRepository)
	mockCashManager := new(MockCashManager)
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB WITHOUT the security (to simulate missing ISIN)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)
	// Note: No securities inserted - symbol won't be found

	// Create security provider (even though DB is empty)
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		brokerClient:     mockTradernetClient,
		positionRepo:     mockPositionRepo,
		cashManager:      mockCashManager,
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	// Mock Tradernet returns position for symbol not in universe
	tradernetPositions := []domain.BrokerPosition{
		{
			Symbol:   "UNKNOWN.STOCK",
			Quantity: 10.0,
			AvgPrice: 100.0,
			Currency: "USD",
		},
	}
	mockTradernetClient.On("GetPortfolio").Return(tradernetPositions, nil)
	mockTradernetClient.On("GetCashBalances").Return([]domain.BrokerCashBalance{}, nil)
	mockPositionRepo.On("GetAll").Return([]Position{}, nil)
	mockPositionRepo.On("GetBySymbol", "UNKNOWN.STOCK").Return(nil, nil).Once()

	// Execute
	err = service.SyncFromTradernet()
	require.NoError(t, err) // Should not error, just skip

	// Verify position was NOT upserted (no ISIN = skipped)
	mockPositionRepo.AssertNotCalled(t, "Upsert", mock.Anything)
}

func TestGetPortfolioSummary_PositionError(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	mockAllocRepo := new(MockAllocationTargetProvider)
	mockPositionRepo := new(MockPositionRepository)

	targets := map[string]float64{"geography:USA": 0.60}

	mockAllocRepo.On("GetAll").Return(targets, nil)
	mockPositionRepo.On("GetWithSecurityInfo").Return(nil, errors.New("database error"))

	service := &PortfolioService{
		allocRepo:    mockAllocRepo,
		positionRepo: mockPositionRepo,
		log:          log,
	}

	_, err := service.GetPortfolioSummary()

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get positions")
	mockAllocRepo.AssertExpectations(t)
	mockPositionRepo.AssertExpectations(t)
}

func TestGetAllSecurityGeographiesAndIndustries_ExcludesIndices(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB with JSON storage schema (migration 038)
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert regular securities
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.', 'product_type', 'EQUITY', 'geography', 'United States', 'industry', 'Technology'), NULL),
			('DE0007164600', 'SAP', json_object('name', 'SAP SE', 'product_type', 'EQUITY', 'geography', 'Germany', 'industry', 'Technology'), NULL)
	`)
	require.NoError(t, err)

	// Insert market indices (should be excluded)
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('INDEX-SP500.IDX', 'SP500.IDX', json_object('name', 'S&P 500', 'product_type', 'INDEX', 'geography', 'United States', 'industry', 'Index'), NULL),
			('INDEX-DAX.IDX', 'DAX.IDX', json_object('name', 'DAX', 'product_type', 'INDEX', 'geography', 'Germany', 'industry', 'Index'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider with universe DB
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		securityProvider: securityProvider,
		log:              log,
	}

	// Execute
	geographies, industries, err := service.getAllSecurityGeographiesAndIndustries()
	require.NoError(t, err)

	// Verify geographies include only regular securities
	assert.True(t, geographies["United States"], "United States should be included from AAPL")
	assert.True(t, geographies["Germany"], "Germany should be included from SAP")
	assert.Len(t, geographies, 2, "Should have exactly 2 geographies")

	// Verify industries exclude "Index" from indices
	assert.True(t, industries["Technology"], "Technology should be included")
	assert.False(t, industries["Index"], "Index industry should be excluded")
	assert.Len(t, industries, 1, "Should have exactly 1 industry")
}

func TestGetAllSecurityGeographiesAndIndustries_IncludesNullProductType(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create test universeDB
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
	`)
	require.NoError(t, err)

	// Insert security with NULL product_type (should be included)
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc.', 'geography', 'United States', 'industry', 'Technology'), NULL)
	`)
	require.NoError(t, err)

	// Insert index (should be excluded)
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('INDEX-SP500.IDX', 'SP500.IDX', json_object('name', 'S&P 500', 'product_type', 'INDEX', 'geography', 'United States', 'industry', 'Index'), NULL)
	`)
	require.NoError(t, err)

	// Create security provider
	securityProvider := newTestSecurityProvider(universeDB, log)

	service := &PortfolioService{
		universeDB:       universeDB,
		securityProvider: securityProvider,
		log:              log,
	}

	// Execute
	geographies, industries, err := service.getAllSecurityGeographiesAndIndustries()
	require.NoError(t, err)

	// Verify NULL product_type is included
	assert.True(t, geographies["United States"], "United States should be included from AAPL with NULL product_type")
	assert.True(t, industries["Technology"], "Technology should be included from AAPL with NULL product_type")
	assert.False(t, industries["Index"], "Index industry should be excluded")
}

// TestAggregatePositionValues_EmptyGeography tests that securities without geography
// have their value split equally across ALL known geographies
func TestAggregatePositionValues_EmptyGeography(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "GLOBAL_ETF",
			Quantity:       10,
			CurrentPrice:   100.0,
			MarketValueEUR: 1000.0,
			Geography:      "", // Empty geography - should count as ALL
			Industry:       "Finance",
		},
	}

	// Define all known geographies
	allGeographies := map[string]bool{
		"USA":     true,
		"Germany": true,
		"Japan":   true,
	}
	allIndustries := map[string]bool{
		"Finance":    true,
		"Technology": true,
	}

	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	// Should split 1000 equally across 3 geographies = 333.33... each
	expectedPerGeography := 1000.0 / 3.0
	assert.InDelta(t, expectedPerGeography, geographyValues["USA"], 0.01)
	assert.InDelta(t, expectedPerGeography, geographyValues["Germany"], 0.01)
	assert.InDelta(t, expectedPerGeography, geographyValues["Japan"], 0.01)

	// Industry should be attributed normally
	assert.Equal(t, 1000.0, industryValues["Finance"])
	assert.Equal(t, 1000.0, totalValue)
}

// TestAggregatePositionValues_EmptyGeographyAndIndustry tests that securities without
// both geography and industry have their value split across ALL known categories
func TestAggregatePositionValues_EmptyGeographyAndIndustry(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "UNKNOWN_SECURITY",
			Quantity:       10,
			CurrentPrice:   100.0,
			MarketValueEUR: 1000.0,
			Geography:      "", // Empty - should count as ALL
			Industry:       "", // Empty - should count as ALL
		},
	}

	allGeographies := map[string]bool{
		"USA":    true,
		"Europe": true,
	}
	allIndustries := map[string]bool{
		"Technology": true,
		"Finance":    true,
		"Healthcare": true,
	}

	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	// Should split 1000 equally across 2 geographies = 500 each
	assert.InDelta(t, 500.0, geographyValues["USA"], 0.01)
	assert.InDelta(t, 500.0, geographyValues["Europe"], 0.01)

	// Should split 1000 equally across 3 industries = 333.33... each
	expectedPerIndustry := 1000.0 / 3.0
	assert.InDelta(t, expectedPerIndustry, industryValues["Technology"], 0.01)
	assert.InDelta(t, expectedPerIndustry, industryValues["Finance"], 0.01)
	assert.InDelta(t, expectedPerIndustry, industryValues["Healthcare"], 0.01)

	assert.Equal(t, 1000.0, totalValue)
}

// TestAggregatePositionValues_MixedEmptyAndSpecific tests aggregation with a mix of
// securities that have specific geographies and ones that don't (count as ALL)
func TestAggregatePositionValues_MixedEmptyAndSpecific(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	service := &PortfolioService{log: log}

	positions := []PositionWithSecurity{
		{
			Symbol:         "AAPL",
			Quantity:       10,
			CurrentPrice:   100.0,
			MarketValueEUR: 1000.0,
			Geography:      "USA", // Specific geography
			Industry:       "Technology",
		},
		{
			Symbol:         "GLOBAL_ETF",
			Quantity:       10,
			CurrentPrice:   50.0,
			MarketValueEUR: 500.0,
			Geography:      "", // Empty - should count as ALL
			Industry:       "Finance",
		},
	}

	allGeographies := map[string]bool{
		"USA":     true,
		"Germany": true,
	}
	allIndustries := map[string]bool{
		"Technology": true,
		"Finance":    true,
	}

	geographyValues, industryValues, totalValue := service.aggregatePositionValues(
		positions, allGeographies, allIndustries,
	)

	// USA: 1000 (AAPL) + 250 (half of GLOBAL_ETF split across 2 geographies) = 1250
	// Germany: 250 (half of GLOBAL_ETF)
	assert.InDelta(t, 1250.0, geographyValues["USA"], 0.01)
	assert.InDelta(t, 250.0, geographyValues["Germany"], 0.01)

	// Industries attributed normally
	assert.Equal(t, 1000.0, industryValues["Technology"])
	assert.Equal(t, 500.0, industryValues["Finance"])

	assert.Equal(t, 1500.0, totalValue)
}
