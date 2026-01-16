package universe

import (
	"encoding/json"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MockBrokerClientForMetadataSync mocks the broker client for metadata sync tests
type MockBrokerClientForMetadataSync struct {
	RawResponse interface{}
	Error       error
}

func (m *MockBrokerClientForMetadataSync) GetSecurityMetadataRaw(symbol string) (interface{}, error) {
	return m.RawResponse, m.Error
}

// Implement other BrokerClient methods as no-ops
func (m *MockBrokerClientForMetadataSync) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) IsConnected() bool {
	return true
}
func (m *MockBrokerClientForMetadataSync) HealthCheck() (*domain.BrokerHealthResult, error) {
	return nil, nil
}
func (m *MockBrokerClientForMetadataSync) SetCredentials(apiKey, apiSecret string) {}

// TestMetadataSyncService_StoresRawTradernetData verifies that metadata sync stores
// raw Tradernet API response without any transformation
func TestMetadataSyncService_StoresRawTradernetData(t *testing.T) {
	// Setup test database
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Create test security
	security := Security{
		ISIN:   "US0378331005",
		Symbol: "AAPL.US",
		Name:   "Apple Inc.",
	}
	err := repo.Create(security)
	require.NoError(t, err)

	// Mock broker client returns full Tradernet response
	mockBroker := &MockBrokerClientForMetadataSync{
		RawResponse: map[string]interface{}{
			"total": 1,
			"securities": []interface{}{
				map[string]interface{}{
					"id":                  12345,
					"ticker":              "AAPL.US",
					"name":                "Apple Inc.",
					"issue_nb":            "US0378331005",
					"face_curr_c":         "USD",
					"mkt_name":            "FIX",
					"codesub_nm":          "NASDAQ",
					"lot_size_q":          "1.00000000",
					"issuer_country_code": "0",
					"sector_code":         "Technology",
					"type":                "Regular stock",
					"quotes": map[string]interface{}{
						"x_lot":    float64(1),
						"min_step": 0.01,
					},
					"attributes": map[string]interface{}{
						"CntryOfRisk": "US",
						"base_mkt_id": "FIX",
					},
				},
			},
		},
	}

	// Create metadata sync service
	syncService := NewMetadataSyncService(repo, mockBroker, log)

	// Execute metadata sync
	symbol, err := syncService.SyncMetadata("US0378331005")
	require.NoError(t, err)
	assert.Equal(t, "AAPL.US", symbol)

	// Verify raw format stored in database
	var storedJSON string
	query := `SELECT data FROM securities WHERE isin = ?`
	err = db.QueryRow(query, "US0378331005").Scan(&storedJSON)
	require.NoError(t, err)
	require.NotEmpty(t, storedJSON)

	// Parse stored JSON
	var storedData map[string]interface{}
	err = json.Unmarshal([]byte(storedJSON), &storedData)
	require.NoError(t, err)

	// Verify it's the raw Tradernet format (securities[0] was extracted and stored as-is)
	assert.Equal(t, "AAPL.US", storedData["ticker"])
	assert.Equal(t, "Apple Inc.", storedData["name"])
	assert.Equal(t, "US0378331005", storedData["issue_nb"])
	assert.Equal(t, "USD", storedData["face_curr_c"])
	assert.Equal(t, "FIX", storedData["mkt_name"])
	assert.Equal(t, "NASDAQ", storedData["codesub_nm"])
	assert.Equal(t, "Technology", storedData["sector_code"])
	assert.Equal(t, "Regular stock", storedData["type"])

	// Verify nested structures preserved
	attributes, ok := storedData["attributes"].(map[string]interface{})
	require.True(t, ok, "attributes should be a map")
	assert.Equal(t, "US", attributes["CntryOfRisk"])

	quotes, ok := storedData["quotes"].(map[string]interface{})
	require.True(t, ok, "quotes should be a map")
	assert.Equal(t, float64(1), quotes["x_lot"])

	// CRITICAL: Verify NO transformation occurred
	// The stored data should have Tradernet field names, not our Security struct field names
	assert.NotContains(t, storedData, "geography") // Should use "attributes.CntryOfRisk"
	assert.NotContains(t, storedData, "industry")  // Should use "sector_code"
	assert.NotContains(t, storedData, "currency")  // Should use "face_curr_c"
}

// TestMetadataSyncService_EmptyResponse verifies handling of empty securities array
func TestMetadataSyncService_EmptyResponse(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	// Create test security
	security := Security{
		ISIN:   "US0378331005",
		Symbol: "AAPL.US",
		Name:   "Apple Inc.",
	}
	err := repo.Create(security)
	require.NoError(t, err)

	// Mock returns empty securities array
	mockBroker := &MockBrokerClientForMetadataSync{
		RawResponse: map[string]interface{}{
			"total":      0,
			"securities": []interface{}{},
		},
	}

	syncService := NewMetadataSyncService(repo, mockBroker, log)

	// Should not error, but also should not update
	symbol, err := syncService.SyncMetadata("US0378331005")
	require.NoError(t, err)
	assert.Equal(t, "AAPL.US", symbol)

	// Verify data column unchanged (still placeholder {})
	var storedJSON string
	query := `SELECT data FROM securities WHERE isin = ?`
	err = db.QueryRow(query, "US0378331005").Scan(&storedJSON)
	require.NoError(t, err)
	assert.Equal(t, "{}", storedJSON)
}

// TestMetadataSyncService_SecurityNotFound verifies handling of non-existent ISIN
func TestMetadataSyncService_SecurityNotFound(t *testing.T) {
	db := setupTestDBWithISINPrimaryKey(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewSecurityRepository(db, log)

	mockBroker := &MockBrokerClientForMetadataSync{
		RawResponse: map[string]interface{}{},
	}

	syncService := NewMetadataSyncService(repo, mockBroker, log)

	// Should not error when security doesn't exist
	symbol, err := syncService.SyncMetadata("NONEXISTENT")
	require.NoError(t, err)
	assert.Equal(t, "", symbol)
}
