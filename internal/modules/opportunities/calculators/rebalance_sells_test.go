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

func TestRebalanceSellsCalculator_MaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()
	calc := NewRebalanceSellsCalculator(nil, nil, log)

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
			expectedMaxQuantity: 248, // int(888.8 * 0.28) = 248
			description:         "Should not sell more than 28% of position (PPA.GR case)",
		},
		{
			name:                "50% of 1000 shares = 500 shares (old hardcoded cap)",
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
			// Create overweight country scenario
			position := domain.Position{
				Symbol:   "TEST.US",
				ISIN:     "US1234567890",
				Quantity: tt.positionQuantity,
			}

			security := universe.Security{
				Symbol:    "TEST.US",
				Name:      "Test Security",
				ISIN:      "US1234567890",
				Geography: "US",
				AllowSell: true,
				Currency:  "EUR",
			}

			// US is overweight by 10%
			countryAllocations := map[string]float64{
				"US": 0.60, // Current
			}

			countryWeights := map[string]float64{
				"US": 0.50, // Target
			}

			currentPrice := 10.0

			ctx := &planningdomain.OpportunityContext{
				EnrichedPositions: []planningdomain.EnrichedPosition{
					createEnrichedPosition(position, security, 15.0),
				},
				Securities:             []universe.Security{security},
				CurrentPrices:          map[string]float64{"US1234567890": currentPrice},
				StocksByISIN:           map[string]universe.Security{"US1234567890": security},
				GeographyAllocations:   countryAllocations,
				GeographyWeights:       countryWeights,
				IneligibleISINs:        map[string]bool{},
				RecentlySoldISINs:      map[string]bool{},
				TotalPortfolioValueEUR: 10000,
				AllowSell:              true,
			}

			params := map[string]interface{}{
				"min_overweight_threshold": 0.05, // 5% overweight threshold
				"max_sell_percentage":      tt.maxSellPercentage,
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

func TestRebalanceSellsCalculator_MaxSellPercentage_MultiplePositions(t *testing.T) {
	log := zerolog.Nop()
	calc := NewRebalanceSellsCalculator(nil, nil, log)

	// Test that max_sell_percentage applies per-position
	position1 := domain.Position{Symbol: "STOCK_A.US", ISIN: "US1111111111", Quantity: 1000}
	position2 := domain.Position{Symbol: "STOCK_B.US", ISIN: "US2222222222", Quantity: 500}

	security1 := universe.Security{
		Symbol:    "STOCK_A.US",
		Name:      "Stock A",
		ISIN:      "US1111111111",
		Geography: "US",
		AllowSell: true,
		Currency:  "EUR",
	}
	security2 := universe.Security{
		Symbol:    "STOCK_B.US",
		Name:      "Stock B",
		ISIN:      "US2222222222",
		Geography: "US",
		AllowSell: true,
		Currency:  "EUR",
	}

	securities := []universe.Security{security1, security2}

	countryAllocations := map[string]float64{
		"US": 0.60, // Overweight by 10%
	}

	countryWeights := map[string]float64{
		"US": 0.50,
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position1, security1, 10.0),
			createEnrichedPosition(position2, security2, 20.0),
		},
		Securities:             securities,
		CurrentPrices:          map[string]float64{"US1111111111": 10.0, "US2222222222": 20.0},
		StocksByISIN:           map[string]universe.Security{"US1111111111": security1, "US2222222222": security2},
		GeographyAllocations:   countryAllocations,
		GeographyWeights:       countryWeights,
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		TotalPortfolioValueEUR: 10000,
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_overweight_threshold": 0.05,
		"max_sell_percentage":      0.28, // 28% max sell
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.GreaterOrEqual(t, len(result.Candidates), 1, "Should generate at least one sell candidate")

	// Each position should respect its own max_sell_percentage
	for _, candidate := range result.Candidates {
		switch candidate.Symbol {
		case "STOCK_A.US":
			assert.LessOrEqual(t, candidate.Quantity, 280, "STOCK_A: max 28% of 1000 = 280")
		case "STOCK_B.US":
			assert.LessOrEqual(t, candidate.Quantity, 140, "STOCK_B: max 28% of 500 = 140")
		}
	}
}

func TestRebalanceSellsCalculator_NoMaxSellPercentage_DefaultsTo20Percent(t *testing.T) {
	log := zerolog.Nop()
	calc := NewRebalanceSellsCalculator(nil, nil, log)

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
		Geography: "US",
		AllowSell: true,
		Currency:  "EUR",
	}

	countryAllocations := map[string]float64{
		"US": 0.80, // Significantly overweight
	}

	countryWeights := map[string]float64{
		"US": 0.30, // Target much lower
	}

	ctx := &planningdomain.OpportunityContext{
		EnrichedPositions: []planningdomain.EnrichedPosition{
			createEnrichedPosition(position, security, 15.0),
		},
		Securities:             []universe.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 10.0},
		StocksByISIN:           map[string]universe.Security{"US1234567890": security},
		GeographyAllocations:   countryAllocations,
		GeographyWeights:       countryWeights,
		IneligibleISINs:        map[string]bool{},
		RecentlySoldISINs:      map[string]bool{},
		TotalPortfolioValueEUR: 10000,
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_overweight_threshold": 0.05,
		// No max_sell_percentage provided
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Without max_sell_percentage, should cap at 20% (new default matching config)
	assert.LessOrEqual(t, result.Candidates[0].Quantity, 200, "Should cap at 20% when max_sell_percentage not provided")
}
