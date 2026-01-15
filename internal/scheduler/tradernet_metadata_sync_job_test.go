package scheduler

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestNewTradernetMetadataSyncJob(t *testing.T) {
	log := zerolog.Nop()

	job := NewTradernetMetadataSyncJob(TradernetMetadataSyncJobConfig{
		Log:          log,
		SecurityRepo: nil,
		BrokerClient: nil,
	})

	assert.NotNil(t, job)
	assert.Equal(t, "tradernet_metadata_sync", job.Name())
}

func TestTradernetMetadataSyncJob_Run_NoBrokerClient(t *testing.T) {
	log := zerolog.Nop()

	job := NewTradernetMetadataSyncJob(TradernetMetadataSyncJobConfig{
		Log:          log,
		SecurityRepo: nil,
		BrokerClient: nil,
	})

	err := job.Run()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "broker client not available")
}

// mockBrokerClient implements domain.BrokerClient for testing
type mockBrokerClient struct {
	connected             bool
	findSymbolFn          func(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error)
	getSecurityMetadataFn func(symbol string) (*domain.BrokerSecurityInfo, error)
}

func (m *mockBrokerClient) IsConnected() bool {
	return m.connected
}

func (m *mockBrokerClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	if m.findSymbolFn != nil {
		return m.findSymbolFn(symbol, exchange)
	}
	return nil, nil
}

func (m *mockBrokerClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	if m.getSecurityMetadataFn != nil {
		return m.getSecurityMetadataFn(symbol)
	}
	return nil, nil
}

// Implement other required methods with no-op or nil returns
func (m *mockBrokerClient) GetPortfolio() ([]domain.BrokerPosition, error)       { return nil, nil }
func (m *mockBrokerClient) GetCashBalances() ([]domain.BrokerCashBalance, error) { return nil, nil }
func (m *mockBrokerClient) PlaceOrder(_, _ string, _, _ float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}
func (m *mockBrokerClient) GetExecutedTrades(_ int) ([]domain.BrokerTrade, error)  { return nil, nil }
func (m *mockBrokerClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) { return nil, nil }
func (m *mockBrokerClient) GetQuote(_ string) (*domain.BrokerQuote, error)         { return nil, nil }
func (m *mockBrokerClient) GetQuotes(_ []string) (map[string]*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *mockBrokerClient) GetLevel1Quote(_ string) (*domain.BrokerOrderBook, error) { return nil, nil }
func (m *mockBrokerClient) GetHistoricalPrices(_ string, _, _ int64, _ int) ([]domain.BrokerOHLCV, error) {
	return nil, nil
}
func (m *mockBrokerClient) GetFXRates(_ string, _ []string) (map[string]float64, error) {
	return nil, nil
}
func (m *mockBrokerClient) GetAllCashFlows(_ int) ([]domain.BrokerCashFlow, error) { return nil, nil }
func (m *mockBrokerClient) GetCashMovements() (*domain.BrokerCashMovement, error)  { return nil, nil }
func (m *mockBrokerClient) CancelOrder(_ string) error                             { return nil }
func (m *mockBrokerClient) HealthCheck() (*domain.BrokerHealthResult, error)       { return nil, nil }
func (m *mockBrokerClient) SetCredentials(_, _ string)                             {}

func TestTradernetMetadataSyncJob_Run_NotConnected(t *testing.T) {
	log := zerolog.Nop()

	mockClient := &mockBrokerClient{connected: false}

	job := NewTradernetMetadataSyncJob(TradernetMetadataSyncJobConfig{
		Log:          log,
		SecurityRepo: nil,
		BrokerClient: mockClient,
	})

	err := job.Run()
	// Should not error, just skip
	assert.NoError(t, err)
}

func TestMapSectorToIndustry(t *testing.T) {
	// Known sector codes
	assert.Equal(t, "Technology", mapSectorToIndustry("Technology"))
	assert.Equal(t, "Financial Services", mapSectorToIndustry("Financial Services"))
	assert.Equal(t, "Healthcare", mapSectorToIndustry("Healthcare"))

	// Unknown sector code should return as-is
	assert.Equal(t, "SomeUnknownSector", mapSectorToIndustry("SomeUnknownSector"))
}
