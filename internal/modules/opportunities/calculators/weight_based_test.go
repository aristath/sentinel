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

func TestWeightBasedCalculator_NoMaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()
	calc := NewWeightBasedCalculator(nil, log)

	// When max_sell_percentage is not provided, should default to 100% (no limit)
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
		// No max_sell_percentage provided
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Should be able to sell more than 50% when no max_sell_percentage is set
	// (will be capped by weight calculation, not by artificial limit)
	assert.Equal(t, "SELL", result.Candidates[0].Side)
}
