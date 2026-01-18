package services

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/logger"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestExtractUniqueIndustries tests the extractUniqueIndustries helper function
func TestExtractUniqueIndustries(t *testing.T) {
	tests := []struct {
		name       string
		securities []universe.Security
		expected   map[string]bool
	}{
		{
			name: "single industry per security",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Industry: "Technology"},
				{Symbol: "JPM.US", Industry: "Finance"},
				{Symbol: "BA.US", Industry: "Defense"},
			},
			expected: map[string]bool{
				"Technology": true,
				"Finance":    true,
				"Defense":    true,
			},
		},
		{
			name: "multiple industries per security (comma-separated)",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Industry: "Technology"},
				{Symbol: "TSLA.US", Industry: "Automobile, Technology"},
				{Symbol: "BYD.AS", Industry: "Energy, Industrial, Automobile"},
			},
			expected: map[string]bool{
				"Technology": true,
				"Automobile": true,
				"Energy":     true,
				"Industrial": true,
			},
		},
		{
			name: "excludes index securities",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Industry: "Technology"},
				{Symbol: "TECH.IDX", Industry: "Technology"}, // Should be excluded
				{Symbol: "FINANCE.IDX", Industry: "Finance"}, // Should be excluded
				{Symbol: "JPM.US", Industry: "Finance"},
			},
			expected: map[string]bool{
				"Technology": true,
				"Finance":    true,
				// No index-only industries
			},
		},
		{
			name: "skips securities without industry",
			securities: []universe.Security{
				{Symbol: "AAPL.US", Industry: "Technology"},
				{Symbol: "UNKNOWN", Industry: ""},
				{Symbol: "JPM.US", Industry: "Finance"},
			},
			expected: map[string]bool{
				"Technology": true,
				"Finance":    true,
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
			result := extractUniqueIndustries(tt.securities)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// TestPopulateIndustryWeights_FiltersUnusedIndustries tests that industry weights
// are filtered to only include industries present in the universe
func TestPopulateIndustryWeights_FiltersUnusedIndustries(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Setup: Configure targets for many industries (some not in universe)
	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.77,
			"Finance":    0.58,
			"Defense":    0.88,
			"Energy":     0.77,
			"Healthcare": 0.31,
			// These are NOT in the universe:
			"ETF":            0.76,
			"Oil & Gas":      0.74,
			"Industrial":     0.65,
			"Infrastructure": 0.63,
			"Automobile":     0.52,
			"Consumer":       0.51,
			"OTH":            0.51,
			"Investment Banking & Investment Services": 0.50,
		},
	}

	// Securities in universe (only Technology, Finance, Defense, Energy, Healthcare)
	securities := []universe.Security{
		{Symbol: "AAPL.US", ISIN: "US0378331005", Industry: "Technology"},
		{Symbol: "JPM.US", ISIN: "US46625H1005", Industry: "Finance"},
		{Symbol: "LMT.US", ISIN: "US5398301094", Industry: "Defense"},
		{Symbol: "XOM.US", ISIN: "US30231G1022", Industry: "Energy"},
		{Symbol: "JNJ.US", ISIN: "US4781601046", Industry: "Healthcare"},
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
	weights := builder.populateIndustryWeights(securities)

	// Assertions: Should only include the 5 industries in the universe
	assert.Len(t, weights, 5, "Should only include industries present in universe")
	assert.Contains(t, weights, "Technology")
	assert.Contains(t, weights, "Finance")
	assert.Contains(t, weights, "Defense")
	assert.Contains(t, weights, "Energy")
	assert.Contains(t, weights, "Healthcare")

	// Should NOT contain unused industries
	assert.NotContains(t, weights, "ETF")
	assert.NotContains(t, weights, "Oil & Gas")
	assert.NotContains(t, weights, "Industrial")
	assert.NotContains(t, weights, "Infrastructure")

	// Weights should be normalized to sum to 1.0
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001, "Filtered weights should be normalized to sum to 1.0")
}

// TestPopulateIndustryWeights_NormalizesCorrectly verifies the normalization calculation
func TestPopulateIndustryWeights_NormalizesCorrectly(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Setup: Raw weights that should sum to 3.31 after filtering
	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.77,
			"Finance":    0.58,
			"Defense":    0.88,
			"Energy":     0.77,
			"Healthcare": 0.31,
			// Total of active: 0.77 + 0.58 + 0.88 + 0.77 + 0.31 = 3.31
			"ETF": 0.76, // Not in universe, should be filtered out
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Industry: "Technology"},
		{Symbol: "JPM.US", Industry: "Finance"},
		{Symbol: "LMT.US", Industry: "Defense"},
		{Symbol: "XOM.US", Industry: "Energy"},
		{Symbol: "JNJ.US", Industry: "Healthcare"},
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

	weights := builder.populateIndustryWeights(securities)

	// Expected normalized weights (original / 3.31)
	expectedDefense := 0.88 / 3.31    // Should be ~0.266 (26.6%)
	expectedTechnology := 0.77 / 3.31 // Should be ~0.233 (23.3%)
	expectedEnergy := 0.77 / 3.31     // Should be ~0.233 (23.3%)

	assert.InDelta(t, expectedDefense, weights["Defense"], 0.001, "Defense weight should be normalized correctly")
	assert.InDelta(t, expectedTechnology, weights["Technology"], 0.001, "Technology weight should be normalized correctly")
	assert.InDelta(t, expectedEnergy, weights["Energy"], 0.001, "Energy weight should be normalized correctly")
}

// TestPopulateIndustryWeights_ExcludesIndexSecurities ensures .IDX securities are not considered
func TestPopulateIndustryWeights_ExcludesIndexSecurities(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.50,
			"ETF":        0.50, // Index-only industry
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Industry: "Technology"},
		{Symbol: "TECH.IDX", Industry: "ETF"}, // Index security - should be excluded
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

	weights := builder.populateIndustryWeights(securities)

	// Only Technology should be included
	assert.Len(t, weights, 1)
	assert.Contains(t, weights, "Technology")
	assert.NotContains(t, weights, "ETF")
	assert.InDelta(t, 1.0, weights["Technology"], 0.0001, "Technology should be normalized to 100%")
}

// TestPopulateIndustryWeights_HandlesMultipleIndustriesPerSecurity tests comma-separated industries
func TestPopulateIndustryWeights_HandlesMultipleIndustriesPerSecurity(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.30,
			"Automobile": 0.40,
			"Energy":     0.30,
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Industry: "Technology"},
		{Symbol: "TSLA.US", Industry: "Automobile, Technology"}, // Multiple industries
		{Symbol: "XOM.US", Industry: "Energy"},
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

	weights := builder.populateIndustryWeights(securities)

	// All three industries should be included
	assert.Len(t, weights, 3)
	assert.Contains(t, weights, "Technology")
	assert.Contains(t, weights, "Automobile")
	assert.Contains(t, weights, "Energy")

	// Should sum to 1.0
	sum := 0.0
	for _, w := range weights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001)
}

// TestPopulateIndustryWeights_EmptySecurities handles edge case of no securities
func TestPopulateIndustryWeights_EmptySecurities(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.50,
			"Finance":    0.50,
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

	weights := builder.populateIndustryWeights([]universe.Security{})

	// Should return empty map
	assert.Empty(t, weights, "Should return empty map when no securities exist")
}

// TestPopulateIndustryWeights_NoMatchingIndustries tests when configured targets don't match universe
func TestPopulateIndustryWeights_NoMatchingIndustries(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Retail":      0.50, // Not in universe
			"Agriculture": 0.50, // Not in universe
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", Industry: "Technology"},
		{Symbol: "JPM.US", Industry: "Finance"},
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

	weights := builder.populateIndustryWeights(securities)

	// Should return empty map when no targets match
	assert.Empty(t, weights, "Should return empty map when no configured targets match universe industries")
}

// TestBuild_IntegrationWithIndustryWeights verifies the fix in the full Build context
func TestBuild_IntegrationWithIndustryWeights(t *testing.T) {
	log := logger.New(logger.Config{Level: "error", Pretty: false})

	// Realistic scenario: Many configured targets, only some in universe
	allocRepo := &ocbMockAllocationRepository{
		industryTargets: map[string]float64{
			"Technology": 0.77,
			"Finance":    0.58,
			"Defense":    0.88,
			"Energy":     0.77,
			"Healthcare": 0.31,
			// These are NOT in the universe:
			"ETF":            0.76,
			"Oil & Gas":      0.74,
			"Industrial":     0.65,
			"Infrastructure": 0.63,
			"Automobile":     0.52,
			"Consumer":       0.51,
			"OTH":            0.51,
			"Investment Banking & Investment Services": 0.50,
		},
	}

	securities := []universe.Security{
		{Symbol: "AAPL.US", ISIN: "US0378331005", Industry: "Technology", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "JPM.US", ISIN: "US46625H1005", Industry: "Finance", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "LMT.US", ISIN: "US5398301094", Industry: "Defense", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "XOM.US", ISIN: "US30231G1022", Industry: "Energy", AllowBuy: true, AllowSell: true, MinLot: 1},
		{Symbol: "JNJ.US", ISIN: "US4781601046", Industry: "Healthcare", AllowBuy: true, AllowSell: true, MinLot: 1},
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

	// Industry weights should only include the 5 active industries
	assert.Len(t, ctx.IndustryWeights, 5)
	assert.Contains(t, ctx.IndustryWeights, "Technology")
	assert.Contains(t, ctx.IndustryWeights, "Finance")
	assert.Contains(t, ctx.IndustryWeights, "Defense")
	assert.Contains(t, ctx.IndustryWeights, "Energy")
	assert.Contains(t, ctx.IndustryWeights, "Healthcare")

	// Verify Defense target is normalized correctly
	// Raw weights sum: 0.77 + 0.58 + 0.88 + 0.77 + 0.31 = 3.31
	// Defense normalized: 0.88 / 3.31 = 0.2658 (26.58%)
	expectedDefense := 0.88 / 3.31
	assert.InDelta(t, expectedDefense, ctx.IndustryWeights["Defense"], 0.001, "Defense weight should be 26.6%, not 10.8%")

	// Verify weights sum to 1.0
	sum := 0.0
	for _, w := range ctx.IndustryWeights {
		sum += w
	}
	assert.InDelta(t, 1.0, sum, 0.0001, "Industry weights should sum to 1.0")
}
