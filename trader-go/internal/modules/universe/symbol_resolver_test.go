package universe

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestIsISIN(t *testing.T) {
	tests := []struct {
		name       string
		identifier string
		want       bool
	}{
		{
			name:       "valid US ISIN",
			identifier: "US0378331005",
			want:       true,
		},
		{
			name:       "valid ES ISIN",
			identifier: "ES0113900J37",
			want:       true,
		},
		{
			name:       "valid DE ISIN",
			identifier: "DE0005140008",
			want:       true,
		},
		{
			name:       "lowercase ISIN should work",
			identifier: "us0378331005",
			want:       true,
		},
		{
			name:       "ISIN with spaces should work",
			identifier: " US0378331005 ",
			want:       true,
		},
		{
			name:       "too short",
			identifier: "US037833100",
			want:       false,
		},
		{
			name:       "too long",
			identifier: "US03783310055",
			want:       false,
		},
		{
			name:       "invalid format",
			identifier: "1234567890AB",
			want:       false,
		},
		{
			name:       "empty string",
			identifier: "",
			want:       false,
		},
		{
			name:       "Tradernet symbol",
			identifier: "AAPL.US",
			want:       false,
		},
		{
			name:       "Yahoo symbol",
			identifier: "AAPL",
			want:       false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsISIN(tt.identifier)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestIsTradernetFormat(t *testing.T) {
	tests := []struct {
		name       string
		identifier string
		want       bool
	}{
		{
			name:       "valid Tradernet .US",
			identifier: "AAPL.US",
			want:       true,
		},
		{
			name:       "valid Tradernet .DE",
			identifier: "SAP.DE",
			want:       true,
		},
		{
			name:       "valid Tradernet .GR",
			identifier: "OPAP.GR",
			want:       true,
		},
		{
			name:       "valid Tradernet .EUR (3 chars)",
			identifier: "SAN.EUR",
			want:       true,
		},
		{
			name:       "lowercase should work",
			identifier: "aapl.us",
			want:       true,
		},
		{
			name:       "no suffix",
			identifier: "AAPL",
			want:       false,
		},
		{
			name:       "ISIN",
			identifier: "US0378331005",
			want:       false,
		},
		{
			name:       "invalid suffix length (1 char)",
			identifier: "AAPL.U",
			want:       false,
		},
		{
			name:       "invalid suffix length (4 chars)",
			identifier: "AAPL.USAA",
			want:       false,
		},
		{
			name:       "empty string",
			identifier: "",
			want:       false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsTradernetFormat(tt.identifier)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestDetectIdentifierType(t *testing.T) {
	tests := []struct {
		name       string
		identifier string
		want       IdentifierType
	}{
		{
			name:       "ISIN detected",
			identifier: "US0378331005",
			want:       IdentifierTypeISIN,
		},
		{
			name:       "Tradernet .US detected",
			identifier: "AAPL.US",
			want:       IdentifierTypeTradernet,
		},
		{
			name:       "Tradernet .DE detected",
			identifier: "SAP.DE",
			want:       IdentifierTypeTradernet,
		},
		{
			name:       "Yahoo symbol detected",
			identifier: "AAPL",
			want:       IdentifierTypeYahoo,
		},
		{
			name:       "Yahoo with suffix detected",
			identifier: "SAP.DE",
			want:       IdentifierTypeTradernet, // Has .DE suffix
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := DetectIdentifierType(tt.identifier)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestTradernetToYahoo(t *testing.T) {
	tests := []struct {
		name            string
		tradernetSymbol string
		want            string
	}{
		{
			name:            "US symbol - strip .US",
			tradernetSymbol: "AAPL.US",
			want:            "AAPL",
		},
		{
			name:            "Greek symbol - convert .GR to .AT",
			tradernetSymbol: "OPAP.GR",
			want:            "OPAP.AT",
		},
		{
			name:            "German symbol - pass through",
			tradernetSymbol: "SAP.DE",
			want:            "SAP.DE",
		},
		{
			name:            "European symbol - pass through",
			tradernetSymbol: "SAN.EUR",
			want:            "SAN.EUR",
		},
		{
			name:            "lowercase should be uppercased",
			tradernetSymbol: "aapl.us",
			want:            "AAPL",
		},
		{
			name:            "already Yahoo format",
			tradernetSymbol: "AAPL",
			want:            "AAPL",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := TradernetToYahoo(tt.tradernetSymbol)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestSymbolResolverDetectType(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	tests := []struct {
		name       string
		identifier string
		want       IdentifierType
	}{
		{
			name:       "ISIN",
			identifier: "US0378331005",
			want:       IdentifierTypeISIN,
		},
		{
			name:       "Tradernet",
			identifier: "AAPL.US",
			want:       IdentifierTypeTradernet,
		},
		{
			name:       "Yahoo",
			identifier: "AAPL",
			want:       IdentifierTypeYahoo,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := resolver.DetectType(tt.identifier)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestSymbolResolverResolveISIN(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	isin := "US0378331005"
	info, err := resolver.Resolve(isin)

	assert.NoError(t, err)
	assert.NotNil(t, info)
	assert.Nil(t, info.TradernetSymbol)
	assert.NotNil(t, info.ISIN)
	assert.Equal(t, isin, *info.ISIN)
	assert.Equal(t, isin, info.YahooSymbol) // ISIN used as Yahoo symbol
}

func TestSymbolResolverResolveTradernetWithoutClient(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	symbol := "AAPL.US"
	info, err := resolver.Resolve(symbol)

	assert.NoError(t, err)
	assert.NotNil(t, info)
	assert.NotNil(t, info.TradernetSymbol)
	assert.Equal(t, symbol, *info.TradernetSymbol)
	assert.Nil(t, info.ISIN)                  // No ISIN without Tradernet client
	assert.Equal(t, "AAPL", info.YahooSymbol) // Converted to Yahoo format
}

func TestSymbolResolverResolveYahoo(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	symbol := "AAPL"
	info, err := resolver.Resolve(symbol)

	assert.NoError(t, err)
	assert.NotNil(t, info)
	assert.Nil(t, info.TradernetSymbol)
	assert.Nil(t, info.ISIN)
	assert.Equal(t, symbol, info.YahooSymbol)
}

func TestSymbolResolverResolveToISIN(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	tests := []struct {
		name       string
		identifier string
		wantISIN   bool
		want       string
	}{
		{
			name:       "ISIN returns itself",
			identifier: "US0378331005",
			wantISIN:   true,
			want:       "US0378331005",
		},
		{
			name:       "Yahoo symbol - no ISIN",
			identifier: "AAPL",
			wantISIN:   false,
		},
		{
			name:       "Tradernet without client - no ISIN",
			identifier: "AAPL.US",
			wantISIN:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := resolver.ResolveToISIN(tt.identifier)
			assert.NoError(t, err)
			if tt.wantISIN {
				assert.NotNil(t, got)
				assert.Equal(t, tt.want, *got)
			} else {
				assert.Nil(t, got)
			}
		})
	}
}

func TestSymbolResolverGetSymbolForDisplay(t *testing.T) {
	log := zerolog.Nop()
	resolver := NewSymbolResolver(nil, nil, log)

	tests := []struct {
		name         string
		isinOrSymbol string
		want         string
	}{
		{
			name:         "symbol returns itself (no repo)",
			isinOrSymbol: "AAPL.US",
			want:         "AAPL.US",
		},
		{
			name:         "ISIN returns itself (no repo)",
			isinOrSymbol: "US0378331005",
			want:         "US0378331005",
		},
		{
			name:         "Yahoo symbol returns itself",
			isinOrSymbol: "AAPL",
			want:         "AAPL",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := resolver.GetSymbolForDisplay(tt.isinOrSymbol)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestSymbolInfoHasISIN(t *testing.T) {
	tests := []struct {
		name string
		info SymbolInfo
		want bool
	}{
		{
			name: "has ISIN",
			info: SymbolInfo{
				ISIN:        strPtr("US0378331005"),
				YahooSymbol: "AAPL",
			},
			want: true,
		},
		{
			name: "ISIN is nil",
			info: SymbolInfo{
				ISIN:        nil,
				YahooSymbol: "AAPL",
			},
			want: false,
		},
		{
			name: "ISIN is empty string",
			info: SymbolInfo{
				ISIN:        strPtr(""),
				YahooSymbol: "AAPL",
			},
			want: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.info.HasISIN()
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestIdentifierTypeString(t *testing.T) {
	tests := []struct {
		name   string
		idType IdentifierType
		want   string
	}{
		{
			name:   "ISIN",
			idType: IdentifierTypeISIN,
			want:   "ISIN",
		},
		{
			name:   "Tradernet",
			idType: IdentifierTypeTradernet,
			want:   "Tradernet",
		},
		{
			name:   "Yahoo",
			idType: IdentifierTypeYahoo,
			want:   "Yahoo",
		},
		{
			name:   "Unknown",
			idType: IdentifierType(999),
			want:   "Unknown",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := tt.idType.String()
			assert.Equal(t, tt.want, got)
		})
	}
}

// Helper functions

func strPtr(s string) *string {
	return &s
}

// Note: Full integration tests with real Tradernet microservice should be in integration test suite
// These are unit tests focusing on the resolver logic without external dependencies
