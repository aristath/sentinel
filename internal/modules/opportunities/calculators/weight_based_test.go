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

func TestWeightBasedCalculator_MaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()
	calc := NewWeightBasedCalculator(nil, log)

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
			expectedMaxQuantity: 248,
			description:         "Should not sell more than 28% of 888.8 shares",
		},
		{
			name:                "50% of 1000 shares = 500 shares",
			positionQuantity:    1000,
			maxSellPercentage:   0.50,
			expectedMaxQuantity: 500,
			description:         "Should respect 50% max_sell_percentage",
		},
		{
			name:                "20% of 1000 shares = 200 shares",
			positionQuantity:    1000,
			maxSellPercentage:   0.20,
			expectedMaxQuantity: 200,
			description:         "Should respect 20% max_sell_percentage",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create overweight position scenario
			position := domain.Position{
				Symbol:   "TEST.US",
				ISIN:     "US1234567890",
				Quantity: tt.positionQuantity,
			}

			security := universe.Security{
				Symbol:    "TEST.US",
				Name:      "Test Security",
				ISIN:      "US1234567890",
				AllowSell: true,
				Currency:  "EUR",
			}

			currentPrice := 10.0

			// Portfolio with overweight position
			// Current: 100% in TEST.US, Target: 40% (60% overweight)
			ctx := &planningdomain.OpportunityContext{
				EnrichedPositions: []planningdomain.EnrichedPosition{
					createEnrichedPositionWithWeight(position, security, currentPrice, 1.0),
				},
				Securities:             []universe.Security{security},
				CurrentPrices:          map[string]float64{"US1234567890": currentPrice}, // ISIN key ✅
				StocksByISIN:           map[string]universe.Security{"US1234567890": security},
				TotalPortfolioValueEUR: tt.positionQuantity * currentPrice,       // All in one position
				TargetWeights:          map[string]float64{"US1234567890": 0.40}, // Target 40% (ISIN key ✅)
				IneligibleISINs:        map[string]bool{},
				RecentlySoldISINs:      map[string]bool{},
				AllowSell:              true,
			}

			params := map[string]interface{}{
				"min_weight_diff":     0.05, // 5% minimum difference to trigger
				"max_sell_percentage": tt.maxSellPercentage,
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

func TestWeightBasedCalculator_MaxSellPercentage_MultiplePositions(t *testing.T) {
	log := zerolog.Nop()
	calc := NewWeightBasedCalculator(nil, log)

	// Two overweight positions
	position1 := domain.Position{Symbol: "STOCK_A.US", ISIN: "US1111111111", Quantity: 1000}
	position2 := domain.Position{Symbol: "STOCK_B.US", ISIN: "US2222222222", Quantity: 500}

	security1 := universe.Security{Symbol: "STOCK_A.US", Name: "Stock A", ISIN: "US1111111111", AllowSell: true, Currency: "EUR"}
	security2 := universe.Security{Symbol: "STOCK_B.US", Name: "Stock B", ISIN: "US2222222222", AllowSell: true, Currency: "EUR"}

	securities := []universe.Security{security1, security2}

	// Portfolio: 66% STOCK_A (10000), 33% STOCK_B (5000), total 15000
	// Targets: 40% STOCK_A, 20% STOCK_B
	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPositionWithWeight(position1, security1, 10.0, 0.66),
			createEnrichedPositionWithWeight(position2, security2, 10.0, 0.33),
		},
		Securities:             securities,
		CurrentPrices:          map[string]float64{"US1111111111": 10.0, "US2222222222": 10.0}, // ISIN keys ✅
		StocksByISIN:           map[string]universe.Security{"US1111111111": securities[0], "US2222222222": securities[1]},
		TotalPortfolioValueEUR: 15000,
		TargetWeights:          map[string]float64{"US1111111111": 0.40, "US2222222222": 0.20}, // ISIN keys ✅
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_weight_diff":     0.05,
		"max_sell_percentage": 0.28, // 28% max sell
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.GreaterOrEqual(t, len(result.Candidates), 1, "Should generate at least one sell candidate")

	// Each position should respect its own max_sell_percentage
	for _, candidate := range result.Candidates {
		if candidate.Side == "SELL" {
			switch candidate.Symbol {
			case "STOCK_A.US":
				assert.LessOrEqual(t, candidate.Quantity, 280, "STOCK_A: max 28% of 1000 = 280")
			case "STOCK_B.US":
				assert.LessOrEqual(t, candidate.Quantity, 140, "STOCK_B: max 28% of 500 = 140")
			}
		}
	}
}

func TestWeightBasedCalculator_NoMaxSellPercentage_DefaultsTo20Percent(t *testing.T) {
	log := zerolog.Nop()
	calc := NewWeightBasedCalculator(nil, log)

	// When max_sell_percentage is not provided, should default to 20% (config default)
	position := domain.Position{
		Symbol:   "TEST.US",
		ISIN:     "US1234567890",
		Quantity: 1000,
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
			createEnrichedPositionWithWeight(position, security, 10.0, 1.0),
		},
		Securities:             []universe.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 10.0}, // ISIN key ✅
		StocksByISIN:           map[string]universe.Security{"US1234567890": security},
		TotalPortfolioValueEUR: 10000,
		TargetWeights:          map[string]float64{"US1234567890": 0.20}, // Severely overweight (ISIN key ✅)
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_weight_diff": 0.05,
		// No max_sell_percentage provided - should default to 20%
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Should cap at 20% (200 shares) when no max_sell_percentage is set (new default)
	assert.Equal(t, "SELL", result.Candidates[0].Side)
	assert.LessOrEqual(t, result.Candidates[0].Quantity, 200,
		"Should cap at 20%% when max_sell_percentage not provided")
}

// Mock security repo for quality tests
type mockWeightSecurityRepo struct {
	tags map[string][]string
}

func (m *mockWeightSecurityRepo) GetTagsForSecurity(symbol string) ([]string, error) {
	if tags, ok := m.tags[symbol]; ok {
		return tags, nil
	}
	return []string{}, nil
}

func (m *mockWeightSecurityRepo) GetByTags(tags []string) ([]universe.Security, error) {
	return []universe.Security{}, nil
}

func TestWeightBasedCalculator_HighQualityProtection(t *testing.T) {
	log := zerolog.Nop()
	securityRepo := &mockWeightSecurityRepo{
		tags: map[string][]string{
			"QUALITY.US": {"high-quality", "consistent-grower"},
		},
	}
	calc := NewWeightBasedCalculator(securityRepo, log)

	// High-quality position should have reduced sell quantity
	position := domain.Position{
		Symbol:   "QUALITY.US",
		ISIN:     "US1234567890",
		Quantity: 1000,
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
			createEnrichedPositionWithWeight(position, security, 10.0, 1.0),
		},
		Securities:             []universe.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 10.0},
		StocksByISIN:           map[string]universe.Security{"US1234567890": security},
		TotalPortfolioValueEUR: 10000,
		TargetWeights:          map[string]float64{"US1234567890": 0.40}, // Overweight
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		AllowSell:              true,
		StabilityScores:        map[string]float64{"US1234567890": 0.9},
	}

	config := planningdomain.NewDefaultConfiguration()

	params := map[string]interface{}{
		"min_weight_diff":     0.05,
		"max_sell_percentage": 0.20,
		"config":              config,
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// High-quality position should have reduced quantity via SellPriorityBoost
	// With tags "high-quality" + "consistent-grower" and stability 0.9:
	// SellPriorityBoost ≈ 0.75 * 0.75 * 0.9 ≈ 0.506
	// The initial quantity is reduced, then capped at maxSellPercentage
	t.Logf("Candidate quantity: %d", result.Candidates[0].Quantity)
	assert.Less(t, result.Candidates[0].Quantity, 150,
		"High-quality position should have significantly reduced sell quantity")
}

func TestWeightBasedCalculator_LowQualityBoostedSelling(t *testing.T) {
	log := zerolog.Nop()
	securityRepo := &mockWeightSecurityRepo{
		tags: map[string][]string{
			"LOWQ.US": {"stagnant", "underperforming"},
		},
	}
	calc := NewWeightBasedCalculator(securityRepo, log)

	// Low-quality position should have boosted sell quantity
	position := domain.Position{
		Symbol:   "LOWQ.US",
		ISIN:     "US9999999999",
		Quantity: 1000,
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
			createEnrichedPositionWithWeight(position, security, 10.0, 1.0),
		},
		Securities:             []universe.Security{security},
		CurrentPrices:          map[string]float64{"US9999999999": 10.0},
		StocksByISIN:           map[string]universe.Security{"US9999999999": security},
		TotalPortfolioValueEUR: 10000,
		TargetWeights:          map[string]float64{"US9999999999": 0.40}, // Overweight
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		AllowSell:              true,
	}

	config := planningdomain.NewDefaultConfiguration()

	params := map[string]interface{}{
		"min_weight_diff":     0.05,
		"max_sell_percentage": 0.20,
		"config":              config,
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Low-quality should have boosted quantity (up to 20% boost), but still capped at max
	// With 20% boost, quantity may be higher but should still respect max_sell_percentage after lot rounding
	assert.LessOrEqual(t, result.Candidates[0].Quantity, 200,
		"Low-quality position should respect max_sell_percentage cap")
}
