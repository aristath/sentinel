package universe

import (
	"errors"
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// ============================================================================
// Mock Broker Client for Testing
// ============================================================================

type MockBrokerClient struct {
	findSymbolResults []domain.BrokerSecurityInfo
	findSymbolError   error
}

func (m *MockBrokerClient) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	if m.findSymbolError != nil {
		return nil, m.findSymbolError
	}
	return m.findSymbolResults, nil
}

// Stub implementations for interface compliance
func (m *MockBrokerClient) GetPortfolio() ([]domain.BrokerPosition, error) { return nil, nil }
func (m *MockBrokerClient) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}
func (m *MockBrokerClient) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetQuote(symbol string) (*domain.BrokerQuote, error) { return nil, nil }
func (m *MockBrokerClient) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}
func (m *MockBrokerClient) GetCashMovements() (*domain.BrokerCashMovement, error) { return nil, nil }
func (m *MockBrokerClient) IsConnected() bool                                     { return true }
func (m *MockBrokerClient) HealthCheck() (*domain.BrokerHealthResult, error)      { return nil, nil }
func (m *MockBrokerClient) SetCredentials(apiKey, apiSecret string)               {}
func (m *MockBrokerClient) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

// ============================================================================
// MetadataEnricher.Enrich Tests
// ============================================================================

func TestMetadataEnricher_Enrich_FillsMissingFields(t *testing.T) {
	name := "Apple Inc."
	currency := "USD"
	country := "US"
	sector := "TEC"
	exchangeName := "NASDAQ"
	isin := "US0378331005"
	marketCode := "FIX"

	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{
			{
				Symbol:       "AAPL.US",
				Name:         &name,
				ISIN:         &isin,
				Currency:     &currency,
				Country:      &country,
				Sector:       &sector,
				ExchangeName: &exchangeName,
				Market:       &marketCode,
			},
		},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	// Security with missing metadata
	security := &Security{
		Symbol: "AAPL.US",
		Name:   "",
		ISIN:   "",
	}

	err := enricher.Enrich(security)

	assert.NoError(t, err)
	assert.Equal(t, "Apple Inc.", security.Name)
	assert.Equal(t, "USD", security.Currency)
	assert.Equal(t, "US", security.Geography)
	assert.Equal(t, "Technology", security.Industry) // Mapped from TEC
	assert.Equal(t, "NASDAQ", security.FullExchangeName)
	assert.Equal(t, "US0378331005", security.ISIN)
	assert.Equal(t, "FIX", security.MarketCode)
}

func TestMetadataEnricher_Enrich_PreservesExistingData(t *testing.T) {
	name := "Apple Inc."
	currency := "USD"
	country := "US"
	sector := "TEC"
	exchangeName := "NASDAQ"
	marketCode := "FIX"

	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{
			{
				Symbol:       "AAPL.US",
				Name:         &name,
				Currency:     &currency,
				Country:      &country,
				Sector:       &sector,
				ExchangeName: &exchangeName,
				Market:       &marketCode,
			},
		},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	// Security with existing data - should NOT be overwritten
	security := &Security{
		Symbol:           "AAPL.US",
		Name:             "Existing Name",
		Currency:         "EUR",
		Geography:        "DE",
		Industry:         "Custom Industry",
		FullExchangeName: "Custom Exchange",
		MarketCode:       "EU",
	}

	err := enricher.Enrich(security)

	assert.NoError(t, err)
	// Existing values should be preserved
	assert.Equal(t, "Existing Name", security.Name)
	assert.Equal(t, "EUR", security.Currency)
	assert.Equal(t, "DE", security.Geography)
	assert.Equal(t, "Custom Industry", security.Industry)
	assert.Equal(t, "Custom Exchange", security.FullExchangeName)
	assert.Equal(t, "EU", security.MarketCode)
}

func TestMetadataEnricher_Enrich_PartialData(t *testing.T) {
	name := "Apple Inc."
	// Only name available from broker

	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{
			{
				Symbol: "AAPL.US",
				Name:   &name,
				// Other fields are nil
			},
		},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	security := &Security{
		Symbol: "AAPL.US",
	}

	err := enricher.Enrich(security)

	assert.NoError(t, err)
	assert.Equal(t, "Apple Inc.", security.Name)
	// Other fields should remain empty
	assert.Equal(t, "", security.Currency)
	assert.Equal(t, "", security.Geography)
	assert.Equal(t, "", security.Industry)
}

func TestMetadataEnricher_Enrich_NoResults(t *testing.T) {
	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	security := &Security{
		Symbol: "UNKNOWN.XX",
	}

	err := enricher.Enrich(security)

	// Should not return error, just no enrichment
	assert.NoError(t, err)
}

func TestMetadataEnricher_Enrich_BrokerError(t *testing.T) {
	mockClient := &MockBrokerClient{
		findSymbolError: errors.New("broker unavailable"),
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	security := &Security{
		Symbol: "AAPL.US",
	}

	err := enricher.Enrich(security)

	// Should return the error
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "broker unavailable")
}

func TestMetadataEnricher_Enrich_NilSecurity(t *testing.T) {
	mockClient := &MockBrokerClient{}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	err := enricher.Enrich(nil)

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "security cannot be nil")
}

// ============================================================================
// Sector Mapping Tests
// ============================================================================

func TestSectorMapping_AllSectors(t *testing.T) {
	testCases := []struct {
		code     string
		expected string
	}{
		{"FIN", "Financial Services"},
		{"TEC", "Technology"},
		{"HLT", "Healthcare"},
		{"CST", "Consumer Staples"},
		{"CSD", "Consumer Discretionary"},
		{"IND", "Industrials"},
		{"MAT", "Materials"},
		{"ENE", "Energy"},
		{"UTL", "Utilities"},
		{"COM", "Communication Services"},
		{"REI", "Real Estate"},
		{"OTH", "Other"},
	}

	for _, tc := range testCases {
		t.Run(tc.code, func(t *testing.T) {
			result := MapSectorToIndustry(tc.code)
			assert.Equal(t, tc.expected, result)
		})
	}
}

func TestSectorMapping_UnknownCode(t *testing.T) {
	result := MapSectorToIndustry("UNKNOWN")
	assert.Equal(t, "", result)
}

func TestSectorMapping_EmptyCode(t *testing.T) {
	result := MapSectorToIndustry("")
	assert.Equal(t, "", result)
}

// ============================================================================
// Market Code Enrichment Tests
// ============================================================================

func TestMetadataEnricher_Enrich_AllMarketCodes(t *testing.T) {
	// Test all known Tradernet market codes are properly enriched
	testCases := []struct {
		name       string
		marketCode string
	}{
		{"US Markets (FIX)", "FIX"},
		{"EU Markets", "EU"},
		{"Athens (ATHEX)", "ATHEX"},
		{"Hong Kong (HKEX)", "HKEX"},
		{"Moscow Derivatives (FORTS)", "FORTS"},
		{"Moscow Exchange (MCX)", "MCX"},
		{"Saudi Arabia (TABADUL)", "TABADUL"},
		{"Kazakhstan (KASE)", "KASE"},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			name := "Test Security"
			mockClient := &MockBrokerClient{
				findSymbolResults: []domain.BrokerSecurityInfo{
					{
						Symbol: "TEST.XX",
						Name:   &name,
						Market: &tc.marketCode,
					},
				},
			}
			log := zerolog.Nop()
			enricher := NewMetadataEnricher(mockClient, log)

			security := &Security{
				Symbol: "TEST.XX",
			}

			err := enricher.Enrich(security)

			assert.NoError(t, err)
			assert.Equal(t, tc.marketCode, security.MarketCode)
		})
	}
}

func TestMetadataEnricher_Enrich_MarketCodeNilNotOverwritten(t *testing.T) {
	// If broker returns nil market code, existing value should be preserved
	name := "Test Security"
	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{
			{
				Symbol: "TEST.XX",
				Name:   &name,
				Market: nil, // No market code from broker
			},
		},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	security := &Security{
		Symbol:     "TEST.XX",
		MarketCode: "EU", // Existing market code
	}

	err := enricher.Enrich(security)

	assert.NoError(t, err)
	assert.Equal(t, "EU", security.MarketCode) // Should be preserved
}

func TestMetadataEnricher_Enrich_MarketCodeEmptyStringNotOverwritten(t *testing.T) {
	// If broker returns empty string market code, existing value should be preserved
	name := "Test Security"
	emptyMarket := ""
	mockClient := &MockBrokerClient{
		findSymbolResults: []domain.BrokerSecurityInfo{
			{
				Symbol: "TEST.XX",
				Name:   &name,
				Market: &emptyMarket, // Empty string from broker
			},
		},
	}
	log := zerolog.Nop()
	enricher := NewMetadataEnricher(mockClient, log)

	security := &Security{
		Symbol:     "TEST.XX",
		MarketCode: "HKEX", // Existing market code
	}

	err := enricher.Enrich(security)

	assert.NoError(t, err)
	assert.Equal(t, "HKEX", security.MarketCode) // Should be preserved
}
