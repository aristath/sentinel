package hash

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/universe"
)

func TestGeneratePortfolioHash(t *testing.T) {
	tests := []struct {
		name          string
		positions     []Position
		securities    []*universe.Security
		cashBalances  map[string]float64
		pendingOrders []PendingOrder
		wantSameHash  bool
	}{
		{
			name: "same portfolio generates same hash",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
				{Symbol: "GOOGL", Quantity: 5},
			},
			securities: []*universe.Security{
				{Symbol: "AAPL", Country: "US", AllowBuy: true},
				{Symbol: "GOOGL", Country: "US", AllowBuy: true},
			},
			cashBalances: map[string]float64{"EUR": 1000.0},
			wantSameHash: true,
		},
		{
			name:         "empty portfolio generates consistent hash",
			positions:    []Position{},
			securities:   []*universe.Security{},
			cashBalances: map[string]float64{},
			wantSameHash: true,
		},
		{
			name: "with pending buy order",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
			},
			securities: []*universe.Security{
				{Symbol: "AAPL", Country: "US", AllowBuy: true},
			},
			cashBalances: map[string]float64{"EUR": 1000.0},
			pendingOrders: []PendingOrder{
				{Symbol: "AAPL", Side: "buy", Quantity: 5, Price: 150.0, Currency: "EUR"},
			},
			wantSameHash: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Generate hash twice
			hash1 := GeneratePortfolioHash(tt.positions, tt.securities, tt.cashBalances, tt.pendingOrders)
			hash2 := GeneratePortfolioHash(tt.positions, tt.securities, tt.cashBalances, tt.pendingOrders)

			// Verify hash is deterministic
			if hash1 != hash2 {
				t.Errorf("GeneratePortfolioHash() not deterministic: hash1 = %v, hash2 = %v", hash1, hash2)
			}

			// Verify hash length
			if len(hash1) != 8 {
				t.Errorf("GeneratePortfolioHash() hash length = %v, want 8", len(hash1))
			}
		})
	}
}

func TestGeneratePortfolioHash_DifferentPortfolios(t *testing.T) {
	// Portfolio 1
	hash1 := GeneratePortfolioHash(
		[]Position{{Symbol: "AAPL", Quantity: 10}},
		[]*universe.Security{{Symbol: "AAPL", Country: "US", AllowBuy: true}},
		map[string]float64{"EUR": 1000.0},
		nil,
	)

	// Portfolio 2 (different quantity)
	hash2 := GeneratePortfolioHash(
		[]Position{{Symbol: "AAPL", Quantity: 20}},
		[]*universe.Security{{Symbol: "AAPL", Country: "US", AllowBuy: true}},
		map[string]float64{"EUR": 1000.0},
		nil,
	)

	// Portfolio 3 (different cash)
	hash3 := GeneratePortfolioHash(
		[]Position{{Symbol: "AAPL", Quantity: 10}},
		[]*universe.Security{{Symbol: "AAPL", Country: "US", AllowBuy: true}},
		map[string]float64{"EUR": 2000.0},
		nil,
	)

	// All should be different
	if hash1 == hash2 {
		t.Errorf("Different quantities generated same hash: %v", hash1)
	}
	if hash1 == hash3 {
		t.Errorf("Different cash balances generated same hash: %v", hash1)
	}
	if hash2 == hash3 {
		t.Errorf("hash2 and hash3 should be different")
	}
}

func TestGenerateSettingsHash(t *testing.T) {
	settings1 := map[string]interface{}{
		"min_security_score":   0.5,
		"min_hold_days":        30,
		"max_loss_threshold":   -0.15,
		"target_annual_return": 0.10,
	}

	settings2 := map[string]interface{}{
		"min_security_score":   0.6, // Different value
		"min_hold_days":        30,
		"max_loss_threshold":   -0.15,
		"target_annual_return": 0.10,
	}

	hash1 := GenerateSettingsHash(settings1)
	hash2 := GenerateSettingsHash(settings1)
	hash3 := GenerateSettingsHash(settings2)

	// Same settings should generate same hash
	if hash1 != hash2 {
		t.Errorf("Same settings generated different hashes: %v vs %v", hash1, hash2)
	}

	// Different settings should generate different hashes
	if hash1 == hash3 {
		t.Errorf("Different settings generated same hash: %v", hash1)
	}

	// Verify hash length
	if len(hash1) != 8 {
		t.Errorf("Hash length = %v, want 8", len(hash1))
	}
}

func TestGenerateAllocationsHash(t *testing.T) {
	allocations1 := map[string]float64{
		"country:US":       0.6,
		"country:EU":       0.3,
		"industry:Tech":    0.5,
		"industry:Finance": 0.2,
	}

	allocations2 := map[string]float64{
		"country:US":       0.7, // Different value
		"country:EU":       0.3,
		"industry:Tech":    0.5,
		"industry:Finance": 0.2,
	}

	hash1 := GenerateAllocationsHash(allocations1)
	hash2 := GenerateAllocationsHash(allocations1)
	hash3 := GenerateAllocationsHash(allocations2)

	// Same allocations should generate same hash
	if hash1 != hash2 {
		t.Errorf("Same allocations generated different hashes: %v vs %v", hash1, hash2)
	}

	// Different allocations should generate different hashes
	if hash1 == hash3 {
		t.Errorf("Different allocations generated same hash: %v", hash1)
	}

	// Empty allocations should return special hash
	emptyHash := GenerateAllocationsHash(map[string]float64{})
	if emptyHash != "00000000" {
		t.Errorf("Empty allocations hash = %v, want 00000000", emptyHash)
	}
}

func TestApplyPendingOrdersToPortfolio(t *testing.T) {
	tests := []struct {
		name              string
		positions         []Position
		cashBalances      map[string]float64
		pendingOrders     []PendingOrder
		allowNegativeCash bool
		wantPositions     int // number of positions
		wantCash          float64
	}{
		{
			name: "buy order reduces cash and increases position",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
			},
			cashBalances: map[string]float64{"EUR": 1000.0},
			pendingOrders: []PendingOrder{
				{Symbol: "AAPL", Side: "buy", Quantity: 5, Price: 100.0, Currency: "EUR"},
			},
			allowNegativeCash: false,
			wantPositions:     1,
			wantCash:          500.0, // 1000 - (5 * 100)
		},
		{
			name: "sell order reduces position",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
			},
			cashBalances: map[string]float64{"EUR": 1000.0},
			pendingOrders: []PendingOrder{
				{Symbol: "AAPL", Side: "sell", Quantity: 5, Price: 100.0, Currency: "EUR"},
			},
			allowNegativeCash: false,
			wantPositions:     1,
			wantCash:          1000.0, // Cash unchanged (sell doesn't add cash until execution)
		},
		{
			name: "buy with insufficient cash clamped at zero",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
			},
			cashBalances: map[string]float64{"EUR": 100.0},
			pendingOrders: []PendingOrder{
				{Symbol: "AAPL", Side: "buy", Quantity: 5, Price: 100.0, Currency: "EUR"},
			},
			allowNegativeCash: false,
			wantPositions:     1,
			wantCash:          0.0, // 100 - 500 = -400, clamped to 0
		},
		{
			name: "buy with insufficient cash allows negative",
			positions: []Position{
				{Symbol: "AAPL", Quantity: 10},
			},
			cashBalances: map[string]float64{"EUR": 100.0},
			pendingOrders: []PendingOrder{
				{Symbol: "AAPL", Side: "buy", Quantity: 5, Price: 100.0, Currency: "EUR"},
			},
			allowNegativeCash: true,
			wantPositions:     1,
			wantCash:          -400.0, // 100 - 500 = -400
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotPositions, gotCash := ApplyPendingOrdersToPortfolio(
				tt.positions,
				tt.cashBalances,
				tt.pendingOrders,
				tt.allowNegativeCash,
			)

			if len(gotPositions) != tt.wantPositions {
				t.Errorf("ApplyPendingOrdersToPortfolio() positions count = %v, want %v", len(gotPositions), tt.wantPositions)
			}

			if gotCash["EUR"] != tt.wantCash {
				t.Errorf("ApplyPendingOrdersToPortfolio() cash = %v, want %v", gotCash["EUR"], tt.wantCash)
			}
		})
	}
}

func TestGenerateRecommendationCacheKey(t *testing.T) {
	positions := []Position{{Symbol: "AAPL", Quantity: 10}}
	settings := map[string]interface{}{"min_security_score": 0.5}
	securities := []*universe.Security{{Symbol: "AAPL", Country: "US", AllowBuy: true}}
	cashBalances := map[string]float64{"EUR": 1000.0}
	allocations := map[string]float64{"country:US": 0.6}

	// Generate cache key twice
	key1 := GenerateRecommendationCacheKey(positions, settings, securities, cashBalances, allocations, nil)
	key2 := GenerateRecommendationCacheKey(positions, settings, securities, cashBalances, allocations, nil)

	// Should be deterministic
	if key1 != key2 {
		t.Errorf("GenerateRecommendationCacheKey() not deterministic: %v vs %v", key1, key2)
	}

	// Should have format "portfolio:settings:allocations" (8:8:8)
	if len(key1) != 26 { // 8 + 1 (colon) + 8 + 1 (colon) + 8
		t.Errorf("Cache key length = %v, want 26", len(key1))
	}

	// Change any parameter and verify hash changes
	key3 := GenerateRecommendationCacheKey(
		[]Position{{Symbol: "AAPL", Quantity: 20}}, // Different quantity
		settings,
		securities,
		cashBalances,
		allocations,
		nil,
	)

	if key1 == key3 {
		t.Errorf("Different portfolios generated same cache key: %v", key1)
	}
}
