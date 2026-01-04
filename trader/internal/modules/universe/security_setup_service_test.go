package universe

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestSecuritySetupServiceCreation(t *testing.T) {
	log := zerolog.Nop()

	service := NewSecuritySetupService(
		nil, // symbolResolver
		nil, // securityRepo
		nil, // tradernetClient
		nil, // yahooClient
		nil, // historicalSync
		nil, // eventManager
		nil, // scoreCalculator
		log,
	)

	assert.NotNil(t, service)
}

func TestSecuritySetupService_AddByIdentifier_EmptyIdentifier(t *testing.T) {
	log := zerolog.Nop()

	service := NewSecuritySetupService(
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
		log,
	)

	_, err := service.AddSecurityByIdentifier("", 1, true, true)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "identifier cannot be empty")
}

func TestSecuritySetupService_AddByIdentifier_WithoutClients(t *testing.T) {
	log := zerolog.Nop()

	service := NewSecuritySetupService(
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
		nil,
		log,
	)

	// Should panic with nil security repo (nil pointer dereference)
	assert.Panics(t, func() {
		_, _ = service.AddSecurityByIdentifier("AAPL.US", 1, true, true)
	})
}

func TestProductTypeFromYahooQuoteType(t *testing.T) {
	tests := []struct {
		name        string
		quoteType   string
		productName string
		want        ProductType
	}{
		{
			name:        "EQUITY quote type",
			quoteType:   "EQUITY",
			productName: "Apple Inc.",
			want:        ProductTypeEquity,
		},
		{
			name:        "ETF quote type",
			quoteType:   "ETF",
			productName: "SPDR S&P 500 ETF",
			want:        ProductTypeETF,
		},
		{
			name:        "MUTUALFUND with ETC name",
			quoteType:   "MUTUALFUND",
			productName: "WisdomTree Physical Gold ETC",
			want:        ProductTypeETC,
		},
		{
			name:        "MUTUALFUND with ETF name",
			quoteType:   "MUTUALFUND",
			productName: "Vanguard FTSE All-World UCITS ETF",
			want:        ProductTypeETF,
		},
		{
			name:        "MUTUALFUND with commodity name",
			quoteType:   "MUTUALFUND",
			productName: "iShares Physical Silver",
			want:        ProductTypeETC,
		},
		{
			name:        "MUTUALFUND generic",
			quoteType:   "MUTUALFUND",
			productName: "Some Mutual Fund",
			want:        ProductTypeMutualFund,
		},
		{
			name:        "Unknown quote type",
			quoteType:   "INDEX",
			productName: "S&P 500 Index",
			want:        ProductTypeUnknown,
		},
		{
			name:        "Empty quote type",
			quoteType:   "",
			productName: "Some Product",
			want:        ProductTypeUnknown,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := FromYahooQuoteType(tt.quoteType, tt.productName)
			assert.Equal(t, tt.want, got)
		})
	}
}

// Note: Full integration tests with real Tradernet, Yahoo Finance, and database
// should be in integration test suite. These are unit tests focusing on
// service logic without external dependencies.
