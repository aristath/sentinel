package services

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestExtractUniqueGeographies tests the extractUniqueGeographies helper function
func TestExtractUniqueGeographies(t *testing.T) {
	tests := []struct {
		name       string
		securities []universe.Security
		expected   map[string]bool
	}{
		{
			name: "single geography per security",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Geography: "US"},
				{Symbol: "ASML.EU", Geography: "EU"},
				{Symbol: "PPC.GR", Geography: "GR"},
			},
			expected: map[string]bool{
				"US": true,
				"EU": true,
				"GR": true,
			},
		},
		{
			name: "multiple geographies per security (comma-separated)",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Geography: "US"},
				{Symbol: "ASML.EU", Geography: "EU, NL"},
				{Symbol: "TSM.US", Geography: "AS, US"},
			},
			expected: map[string]bool{
				"US": true,
				"EU": true,
				"NL": true,
				"AS": true,
			},
		},
		{
			name: "excludes index securities",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Geography: "US"},
				{Symbol: "SPY.IDX", Geography: "US"},      // Should be excluded
				{Symbol: "WORLD.IDX", Geography: "WORLD"}, // Should be excluded
				{Symbol: "ASML.EU", Geography: "EU"},
			},
			expected: map[string]bool{
				"US": true,
				"EU": true,
				// WORLD should NOT be included
			},
		},
		{
			name: "skips securities without geography",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Geography: "US"},
				{Symbol: "UNKNOWN", Geography: ""},
				{Symbol: "ASML.EU", Geography: "EU"},
			},
			expected: map[string]bool{
				"US": true,
				"EU": true,
			},
		},
		{
			name:       "empty securities list",
			securities: []universe.Security{},
			expected:   map[string]bool{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := extractUniqueGeographies(tt.securities)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestPopulateGeographyWeights_FiltersUnusedGeographies tests that geography weights
// are filtered to only include geographies present in the universe
func TestPopulateGeographyWeights_FiltersUnusedGeographies(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Setup: Configure targets for many geographies (some not in universe)
	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"US": 0.23,
			"EU": 0.62,
			"AS": 0.81,
			"GR": 0.75,
			"GB": 0.50,
			// These are NOT in the universe:
			"CN": 0.77,
			"DK": 0.50,
			"FR": 0.50,
			"HK": 0.75,
			"IE": 0.50,
			"IT": 0.50,
			"NL": 0.64,
			"TW": 0.51,
			"UA": 0.50,
			"DE": 0.49,
		},
	}

	// Securities in universe (only US, EU, AS, GR, GB)
	securities := []universe.Security{
		{Symbol: "AAPL.US", ISIN: "US0378331005", Geography: "US"},
		{Symbol: "ASML.EU", ISIN: "NL0010273215", Geography: "EU"},
		{Symbol: "TSM.US", ISIN: "US8740391003", Geography: "AS"},
		{Symbol: "PPC.GR", ISIN: "GRS434003000", Geography: "GR"},
		{Symbol: "VOD.GB", ISIN: "GB00BH4HKS39", Geography: "GB"},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	// Call the method
	weights := builder.populateGeographyWeights(securities)

	// Assertions: Should only include the 5 geographies in the universe
	assert.Len(t, weights, 5, "Should only include geographies present in universe")
	assert.Contains(t, weights, "US")
	assert.Contains(t, weights, "EU")
	assert.Contains(t, weights, "AS")
	assert.Contains(t, weights, "GR")
	assert.Contains(t, weights, "GB")

	// Should NOT contain unused geographies
	assert.NotContains(t, weights, "CN")
	assert.NotContains(t, weights, "DK")
	assert.NotContains(t, weights, "FR")
	assert.NotContains(t, weights, "HK")

	// Weights should be normalized to sum to 1.0
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001, "Filtered weights should be normalized to sum to 1.0")
}

// TestPopulateGeographyWeights_NormalizesCorrectly verifies the normalization calculation
func TestPopulateGeographyWeights_NormalizesCorrectly(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Setup: Raw weights that should sum to 2.91 after filtering
	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"US": 0.23,
			"EU": 0.62,
			"AS": 0.81,
			"GR": 0.75,
			"GB": 0.50,
			// Total of active: 0.23 + 0.62 + 0.81 + 0.75 + 0.50 = 2.91
			"CN": 0.77, // Not in universe, should be filtered out
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Geography: "US"},
		{Symbol: "ASML.EU", Geography: "EU"},
		{Symbol: "TSM.US", Geography: "AS"},
		{Symbol: "PPC.GR", Geography: "GR"},
		{Symbol: "VOD.GB", Geography: "GB"},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	weights := builder.populateGeographyWeights(securities)

	// Expected normalized weights (original / 2.91)
	expectedEU := 0.62 / 2.91 // Should be ~0.213 (21.3%)
	expectedAS := 0.81 / 2.91 // Should be ~0.278 (27.8%)
	expectedUS := 0.23 / 2.91 // Should be ~0.079 (7.9%)

	assert.InDelta(t, expectedEU, weights["EU"], 0.001, "EU weight should be normalized correctly")
	assert.InDelta(t, expectedAS, weights["AS"], 0.001, "AS weight should be normalized correctly")
	assert.InDelta(t, expectedUS, weights["US"], 0.001, "US weight should be normalized correctly")
}

// TestPopulateGeographyWeights_ExcludesIndexSecurities ensures .IDX securities are not considered
func TestPopulateGeographyWeights_ExcludesIndexSecurities(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"US":    0.50,
			"WORLD": 0.50, // Index-only geography
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Geography: "US"},
		{Symbol: "WORLD.IDX", Geography: "WORLD"}, // Index security - should be excluded
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	weights := builder.populateGeographyWeights(securities)

	// Only US should be included
	assert.Len(t, weights, 1)
	assert.Contains(t, weights, "US")
	assert.NotContains(t, weights, "WORLD")
	assert.InDelta(t, 1.0, weights["US"], 0.0001, "US should be normalized to 100%")
}

// TestPopulateGeographyWeights_HandlesMultipleGeographiesPerSecurity tests comma-separated geographies
func TestPopulateGeographyWeights_HandlesMultipleGeographiesPerSecurity(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"US": 0.30,
			"EU": 0.40,
			"NL": 0.30,
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Geography: "US"},
		{Symbol: "ASML.EU", Geography: "EU, NL"}, // Multiple geographies
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	weights := builder.populateGeographyWeights(securities)

	// All three geographies should be included
	assert.Len(t, weights, 3)
	assert.Contains(t, weights, "US")
	assert.Contains(t, weights, "EU")
	assert.Contains(t, weights, "NL")

	// Should sum to 1.0
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001)
}

// TestPopulateGeographyWeights_EmptySecurities handles edge case of no securities
func TestPopulateGeographyWeights_EmptySecurities(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"US": 0.50,
			"EU": 0.50,
		},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: []universe.Security{}},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	weights := builder.populateGeographyWeights([]universe.Security{})

	// Should return empty map
	assert.Empty(t, weights, "Should return empty map when no securities exist")
}

// TestPopulateGeographyWeights_NoMatchingGeographies tests when configured targets don't match universe
func TestPopulateGeographyWeights_NoMatchingGeographies(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"CN": 0.50, // Not in universe
			"JP": 0.50, // Not in universe
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Geography: "US"},
		{Symbol: "ASML.EU", Geography: "EU"},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	weights := builder.populateGeographyWeights(securities)

	// Should return empty map when no targets match
	assert.Empty(t, weights, "Should return empty map when no configured targets match universe geographies")
}

// TestBuild_IntegrationWithGeographyWeights verifies the fix in the full Build context
func TestBuild_IntegrationWithGeographyWeights(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Realistic scenario: Many configured targets, only some in universe
	allocRepo := &ocbMockAllocationRepository{
		geographyTargets: map[string]float64{
			"AS": 0.81,
			"CN": 0.77, // Not in universe
			"DE": 0.49, // Not in universe
			"DK": 0.50, // Not in universe
			"EU": 0.62,
			"FR": 0.50, // Not in universe
			"GB": 0.50,
			"GR": 0.75,
			"HK": 0.75, // Not in universe
			"IE": 0.50, // Not in universe
			"IT": 0.50, // Not in universe
			"NL": 0.64, // Not in universe
			"TW": 0.51, // Not in universe
			"UA": 0.50, // Not in universe
			"US": 0.23,
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", ISIN: "US0378331005", Geography: "US", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "ASML.EU", ISIN: "NL0010273215", Geography: "EU", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "TSM.US", ISIN: "US8740391003", Geography: "AS", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "PPC.GR", ISIN: "GRS434003000", Geography: "GR", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "VOD.GB", ISIN: "GB00BH4HKS39", Geography: "GB", AllowBuy: true, AllowSell: true, MinLot: 1},
	}

	builder := NewOpportunityContextBuilder(
		&ocbMockPositionRepository{positions: []portfolio.Position{}},
		&ocbMockSecurityRepository{securities: securities},
		allocRepo,
		&ocbMockTradeRepository{},
		&ocbMockScoresRepository{},
		&ocbMockSettingsRepository{},
		&ocbMockRegimeRepository{},
		&ocbMockCashManager{balances: map[string]float64{"EUR": 1000.0}},
		&ocbMockPriceClient{},
		&ocbMockPriceConversionService{},
		&ocbMockBrokerClient{},
		nil, // ExpectedReturnsCalculator
		log,
	)

	ctx, err := builder.Build(nil)
	require.NoError(t, err)
	require.NotNil(t, ctx)

	// Geography weights should only include the 5 active geographies
	assert.Len(t, ctx.GeographyWeights, 5)
	assert.Contains(t, ctx.GeographyWeights, "US")
	assert.Contains(t, ctx.GeographyWeights, "EU")
	assert.Contains(t, ctx.GeographyWeights, "AS")
	assert.Contains(t, ctx.GeographyWeights, "GR")
	assert.Contains(t, ctx.GeographyWeights, "GB")

	// Verify EU target is normalized correctly
	// Raw weights sum: 0.23 + 0.62 + 0.81 + 0.75 + 0.50 = 2.91
	// EU normalized: 0.62 / 2.91 = 0.2130 (21.3%)
	expectedEU := 0.62 / 2.91
	assert.InDelta(t, expectedEU, ctx.GeographyWeights["EU"], 0.001, "EU weight should be 21.3%, not 7.2%")

	// Verify weights sum to 1.0
	sum := 0.0
	for _, w := range ctx.GeographyWeights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001, "Geography weights should sum to 1.0")
}
