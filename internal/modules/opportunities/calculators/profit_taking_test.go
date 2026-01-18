package calculators

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Mock implementations for testing (duplicated here for backward compatibility with existing tests)
type mockTagFilter struct {
	sellCandidates []string
	err            error
}

func (m *mockTagFilter) GetOpportunityCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return nil, nil
}

func (m *mockTagFilter) GetSellCandidates(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) ([]string, error) {
	return m.sellCandidates, m.err
}

func (m *mockTagFilter) IsMarketVolatile(ctx *planningdomain.OpportunityContext, config *planningdomain.PlannerConfiguration) bool {
	return false
}

type mockSecurityRepo struct {
	tags map[string][]string
}

func (m *mockSecurityRepo) GetTagsForSecurity(symbol string) ([]string, error) {
	if tags, ok := m.tags[symbol]; ok {
		return tags, nil
	}
	return []string{}, nil
}

func (m *mockSecurityRepo) GetByTags(tags []string) ([]universe.Security, error) {
	return []universe.Security{}, nil
}

func TestProfitTakingCalculator_MaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{tags: map[string][]string{}}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	tests := []struct {
		name                string
		positionQuantity    float64
		maxSellPercentage   float64
		expectedMaxQuantity int
		description         string
	}{
		{
			name:                "28% of 1000 shares = 280 shares",
			positionQuantity:    1000,
			maxSellPercentage:   0.28,
			expectedMaxQuantity: 280,
			description:         "Should not sell more than 28% of position",
		},
		{
			name:                "28% of 888.8 shares = 248 shares",
			positionQuantity:    888.8,
			maxSellPercentage:   0.28,
			expectedMaxQuantity: 248, // int(888.8 * 0.28) = int(248.864) = 248
			description:         "Should not sell more than 28% of 888.8 shares (PPA.GR case)",
		},
		{
			name:                "50% of 1000 shares = 500 shares",
			positionQuantity:    1000,
			maxSellPercentage:   0.50,
			expectedMaxQuantity: 500,
			description:         "Should not sell more than 50% of position",
		},
		{
			name:                "100% allows full position sale",
			positionQuantity:    500,
			maxSellPercentage:   1.0,
			expectedMaxQuantity: 500,
			description:         "100% max_sell_percentage allows selling entire position",
		},
		{
			name:                "10% of 1000 shares = 100 shares",
			positionQuantity:    1000,
			maxSellPercentage:   0.10,
			expectedMaxQuantity: 100,
			description:         "Should not sell more than 10% of position",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a position with 50% gain (above threshold)
			position := domain.Position{
				Symbol:      "TEST.US",
				ISIN:        "US1234567890",
				Quantity:    tt.positionQuantity,
				AverageCost: 10.0,
			}

			security := universe.Security{
				Symbol:    "TEST.US",
				Name:      "Test Security",
				ISIN:      "US1234567890",
				AllowSell: true,
				Currency:  "EUR",
			}

			currentPrice := 15.0 // 50% gain

			ctx := &planningdomain.OpportunityContext{
				EnrichedPositions: []planningdomain.EnrichedPosition{
					createEnrichedPosition(position, security, 15.0),
				},
				Securities:        []universe.Security{security},
				CurrentPrices:     map[string]float64{"US1234567890": currentPrice},
				StocksByISIN:      map[string]universe.Security{"US1234567890": security},
				IneligibleISINs:   map[string]bool{},
				RecentlySoldISINs: map[string]bool{},
				AllowSell:         true,
			}

			config := planningdomain.NewDefaultConfiguration()
			config.EnableTagFiltering = false

			params := map[string]interface{}{
				"min_gain_threshold":  0.15,                 // 15% minimum
				"max_sell_percentage": tt.maxSellPercentage, // From config
				"config":              config,
			}

			result, err := calc.Calculate(ctx, params)
			require.NoError(t, err)
			require.Len(t, result.Candidates, 1, "Should generate one sell candidate")

			candidate := result.Candidates[0]
			assert.Equal(t, "SELL", candidate.Side)
			assert.Equal(t, "TEST.US", candidate.Symbol)
			assert.LessOrEqual(t, candidate.Quantity, tt.expectedMaxQuantity,
				"Quantity %d should not exceed max sell percentage limit %d", candidate.Quantity, tt.expectedMaxQuantity)
		})
	}
}

func TestProfitTakingCalculator_MaxSellPercentage_WithSellPercentageParam(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{tags: map[string][]string{}}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// Test interaction between sell_percentage (old param) and max_sell_percentage (new constraint)
	// max_sell_percentage should always take precedence as the hard limit
	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    1000,
		AverageCost: 10.0,
	}

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		Currency:  "EUR",
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 15.0),
		},
		Securities:        []universe.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]universe.Security{"US1234567890": security},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
	}

	tests := []struct {
		name                string
		sellPercentage      float64
		maxSellPercentage   float64
		expectedMaxQuantity int
		description         string
	}{
		{
			name:                "sell_percentage 100%, max_sell 28% = 280 shares",
			sellPercentage:      1.0,
			maxSellPercentage:   0.28,
			expectedMaxQuantity: 280,
			description:         "max_sell_percentage should cap the sell_percentage",
		},
		{
			name:                "sell_percentage 50%, max_sell 28% = 280 shares",
			sellPercentage:      0.5,
			maxSellPercentage:   0.28,
			expectedMaxQuantity: 280,
			description:         "max_sell_percentage should cap even when sell_percentage is lower",
		},
		{
			name:                "sell_percentage 20%, max_sell 28% = 200 shares",
			sellPercentage:      0.2,
			maxSellPercentage:   0.28,
			expectedMaxQuantity: 200,
			description:         "sell_percentage takes effect when it's lower than max_sell",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := planningdomain.NewDefaultConfiguration()
			config.EnableTagFiltering = false

			params := map[string]interface{}{
				"min_gain_threshold":  0.15,
				"sell_percentage":     tt.sellPercentage,
				"max_sell_percentage": tt.maxSellPercentage,
				"config":              config,
			}

			result, err := calc.Calculate(ctx, params)
			require.NoError(t, err)
			require.Len(t, result.Candidates, 1)

			assert.LessOrEqual(t, result.Candidates[0].Quantity, tt.expectedMaxQuantity,
				"Quantity %d should not exceed %d", result.Candidates[0].Quantity, tt.expectedMaxQuantity)
		})
	}
}

func TestProfitTakingCalculator_NoMaxSellPercentage_DefaultsTo20Percent(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{tags: map[string][]string{}}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// When max_sell_percentage is not provided, should default to 20% (config default)
	position := domain.Position{
		Symbol:      "TEST.US",
		ISIN:        "US1234567890",
		Quantity:    1000,
		AverageCost: 10.0,
	}

	security := universe.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		Currency:  "EUR",
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 15.0),
		},
		Securities:        []universe.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]universe.Security{"US1234567890": security},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = false

	params := map[string]interface{}{
		"min_gain_threshold": 0.15,
		"config":             config,
		// No max_sell_percentage provided - should default to 20%
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Should cap at 20% (200 shares) when no max_sell_percentage is set (new default)
	assert.LessOrEqual(t, result.Candidates[0].Quantity, 200,
		"Should cap at 20%% when max_sell_percentage not provided")
}

func TestProfitTakingCalculator_HighQualityProtection(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{
		tags: map[string][]string{
			"QUALITY.US": {"high-quality", "consistent-grower"},
		},
	}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// High-quality position with moderate gains should have reduced sell quantity
	position := domain.Position{
		Symbol:      "QUALITY.US",
		ISIN:        "US1234567890",
		Quantity:    1000,
		AverageCost: 10.0,
	}

	security := universe.Security{
		Symbol:    "QUALITY.US",
		Name:      "Quality Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		Currency:  "EUR",
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 12.0), // 20% gain (moderate, not windfall)
		},
		Securities:        []universe.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 12.0},
		StocksByISIN:      map[string]universe.Security{"US1234567890": security},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
		StabilityScores:   map[string]float64{"US1234567890": 0.9}, // High stability
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = false // Disable tag pre-filtering for this test

	params := map[string]interface{}{
		"min_gain_threshold":  0.15,
		"max_sell_percentage": 0.20, // 20% max
		"windfall_threshold":  0.30, // 30% windfall
		"config":              config,
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1, "Should generate one sell candidate")

	// High-quality position should have reduced quantity via SellPriorityBoost
	// With tags "high-quality" + "consistent-grower" and stability 0.9:
	// SellPriorityBoost ≈ 0.75 * 0.75 * 0.9 ≈ 0.506 (roughly 50% of original)
	// 20% max of 1000 = 200, then ~50% reduction ≈ 100-105 shares
	assert.Less(t, result.Candidates[0].Quantity, 150,
		"High-quality position should have significantly reduced sell quantity")
	assert.Greater(t, result.Candidates[0].Quantity, 50,
		"High-quality position should still sell some shares")
}

func TestProfitTakingCalculator_LowQualityBoostedSelling(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{
		tags: map[string][]string{
			"LOWQ.US": {"stagnant", "underperforming"},
		},
	}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// Low-quality position should have boosted sell quantity
	position := domain.Position{
		Symbol:      "LOWQ.US",
		ISIN:        "US9999999999",
		Quantity:    1000,
		AverageCost: 10.0,
	}

	security := universe.Security{
		Symbol:    "LOWQ.US",
		Name:      "Low Quality Security",
		ISIN:      "US9999999999",
		AllowSell: true,
		Currency:  "EUR",
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 12.0), // 20% gain
		},
		Securities:        []universe.Security{security},
		CurrentPrices:     map[string]float64{"US9999999999": 12.0},
		StocksByISIN:      map[string]universe.Security{"US9999999999": security},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = false // Disable tag pre-filtering for this test

	params := map[string]interface{}{
		"min_gain_threshold":  0.15,
		"max_sell_percentage": 0.20, // 20% max
		"config":              config,
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Low-quality position should have boosted quantity (20% boost capped at maxSellPercentage)
	// Base would be 200 (20% of 1000), boosted by 20% = 240, but capped at 200
	// So it should still be 200 (capped)
	assert.LessOrEqual(t, result.Candidates[0].Quantity, 200,
		"Low-quality position should respect max_sell_percentage cap")
}

func TestProfitTakingCalculator_WindfallOverridesQualityProtection(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{
		tags: map[string][]string{
			"QUALITY.US": {"high-quality", "consistent-grower"},
		},
	}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// High-quality position with windfall gains should NOT have reduced quantity
	position := domain.Position{
		Symbol:      "QUALITY.US",
		ISIN:        "US1234567890",
		Quantity:    1000,
		AverageCost: 10.0,
	}

	security := universe.Security{
		Symbol:    "QUALITY.US",
		Name:      "Quality Security",
		ISIN:      "US1234567890",
		AllowSell: true,
		Currency:  "EUR",
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 15.0), // 50% gain (windfall!)
		},
		Securities:        []universe.Security{security},
		CurrentPrices:     map[string]float64{"US1234567890": 15.0},
		StocksByISIN:      map[string]universe.Security{"US1234567890": security},
		IneligibleISINs:   map[string]bool{},
		RecentlySoldISINs: map[string]bool{},
		AllowSell:         true,
		StabilityScores:   map[string]float64{"US1234567890": 0.9},
	}

	config := planningdomain.NewDefaultConfiguration()
	config.EnableTagFiltering = false // Disable tag pre-filtering for this test

	params := map[string]interface{}{
		"min_gain_threshold":  0.15,
		"max_sell_percentage": 0.20,
		"windfall_threshold":  0.30, // 30% threshold - 50% gain qualifies as windfall
		"config":              config,
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Windfall overrides quality protection - should get full 20% (200 shares)
	assert.Equal(t, 200, result.Candidates[0].Quantity,
		"Windfall gains should override high-quality protection")
}
