package calculators

import (
	"testing"

	"github.com/aristath/sentinel/internal/domain"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
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

			security := domain.Security{
				Symbol:    "TEST.US",
				Name:      "Test Security",
				ISIN:      "US1234567890",
				Country:   "US",
				Active:    true,
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
				Positions:              []domain.Position{position},
				Securities:             []domain.Security{security},
				CurrentPrices:          map[string]float64{"US1234567890": currentPrice},
				StocksByISIN:           map[string]domain.Security{"US1234567890": security},
				CountryAllocations:     countryAllocations,
				CountryWeights:         countryWeights,
				IneligibleISINs:      map[string]bool{},
				RecentlySoldISINs:           map[string]bool{},
				TotalPortfolioValueEUR: 10000,
				AllowSell:              true,
			}

			params := map[string]interface{}{
				"min_overweight_threshold": 0.05, // 5% overweight threshold
				"max_sell_percentage":      tt.maxSellPercentage,
			}

			candidates, err := calc.Calculate(ctx, params)
			require.NoError(t, err)
			require.Len(t, candidates, 1, "Should generate one sell candidate")

			candidate := candidates[0]
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
	positions := []domain.Position{
		{Symbol: "STOCK_A.US", ISIN: "US1111111111", Quantity: 1000},
		{Symbol: "STOCK_B.US", ISIN: "US2222222222", Quantity: 500},
	}

	securities := []domain.Security{
		{
			Symbol:    "STOCK_A.US",
			Name:      "Stock A",
			ISIN:      "US1111111111",
			Country:   "US",
			Active:    true,
			AllowSell: true,
			Currency:  "EUR",
		},
		{
			Symbol:    "STOCK_B.US",
			Name:      "Stock B",
			ISIN:      "US2222222222",
			Country:   "US",
			Active:    true,
			AllowSell: true,
			Currency:  "EUR",
		},
	}

	countryAllocations := map[string]float64{
		"US": 0.60, // Overweight by 10%
	}

	countryWeights := map[string]float64{
		"US": 0.50,
	}

	ctx := &planningdomain.OpportunityContext{
		Positions:              positions,
		Securities:             securities,
		CurrentPrices:          map[string]float64{"US1111111111": 10.0, "US2222222222": 20.0},
		StocksByISIN:           map[string]domain.Security{"US1111111111": securities[0], "US2222222222": securities[1]},
		CountryAllocations:     countryAllocations,
		CountryWeights:         countryWeights,
		IneligibleISINs:      map[string]bool{},
		RecentlySoldISINs:           map[string]bool{},
		TotalPortfolioValueEUR: 10000,
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_overweight_threshold": 0.05,
		"max_sell_percentage":      0.28, // 28% max sell
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.GreaterOrEqual(t, len(candidates), 1, "Should generate at least one sell candidate")

	// Each position should respect its own max_sell_percentage
	for _, candidate := range candidates {
		switch candidate.Symbol {
		case "STOCK_A.US":
			assert.LessOrEqual(t, candidate.Quantity, 280, "STOCK_A: max 28% of 1000 = 280")
		case "STOCK_B.US":
			assert.LessOrEqual(t, candidate.Quantity, 140, "STOCK_B: max 28% of 500 = 140")
		}
	}
}

func TestRebalanceSellsCalculator_NoMaxSellPercentage_DefaultsToHardcodedCap(t *testing.T) {
	log := zerolog.Nop()
	calc := NewRebalanceSellsCalculator(nil, nil, log)

	// When max_sell_percentage is not provided, the old hardcoded 50% cap should apply
	position := domain.Position{
		Symbol:   "TEST.US",
		ISIN:     "US1234567890",
		Quantity: 1000,
	}

	security := domain.Security{
		Symbol:    "TEST.US",
		Name:      "Test Security",
		ISIN:      "US1234567890",
		Country:   "US",
		Active:    true,
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
		Positions:              []domain.Position{position},
		Securities:             []domain.Security{security},
		CurrentPrices:          map[string]float64{"US1234567890": 10.0},
		StocksByISIN:           map[string]domain.Security{"US1234567890": security},
		CountryAllocations:     countryAllocations,
		CountryWeights:         countryWeights,
		IneligibleISINs:      map[string]bool{},
		RecentlySoldISINs:           map[string]bool{},
		TotalPortfolioValueEUR: 10000,
		AllowSell:              true,
	}

	params := map[string]interface{}{
		"min_overweight_threshold": 0.05,
		// No max_sell_percentage provided
	}

	candidates, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, candidates, 1)

	// Without max_sell_percentage, should still cap at 50% (old hardcoded limit)
	assert.LessOrEqual(t, candidates[0].Quantity, 500, "Should cap at 50% when max_sell_percentage not provided")
}
