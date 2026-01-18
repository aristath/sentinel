package calculators

import (
	"testing"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCalculateGeographySellPlan_RespectsMaxSellPercentage(t *testing.T) {
	tests := []struct {
		name              string
		positionQuantity  float64
		maxSellPercentage float64
		overweightPercent float64
		expectedMaxQty    int
		description       string
	}{
		{
			name:              "20% max with 1000 shares",
			positionQuantity:  1000,
			maxSellPercentage: 0.20,
			overweightPercent: 0.30, // Geography is 30% overweight
			expectedMaxQty:    200,  // Should cap at 20% of 1000
			description:       "Should never exceed 20% of position even with high overweight",
		},
		{
			name:              "20% max with 200 shares",
			positionQuantity:  200,
			maxSellPercentage: 0.20,
			overweightPercent: 0.50, // Geography is 50% overweight
			expectedMaxQty:    40,   // Should cap at 20% of 200
			description:       "XIAO case: 200 shares should max at 40 sold",
		},
		{
			name:              "10% max with 500 shares",
			positionQuantity:  500,
			maxSellPercentage: 0.10,
			overweightPercent: 0.20,
			expectedMaxQty:    50, // 10% of 500
			description:       "Lower max percentage should be respected",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			position := createTestEnrichedPosition(tt.positionQuantity, 10.0, "US")

			ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, 100000)

			plan, err := CalculateGeographySellPlan(
				"US",
				tt.overweightPercent,
				[]planningdomain.EnrichedPosition{position},
				ctx,
				tt.maxSellPercentage,
				nil, // No security repo needed for basic test
				nil, // No config needed for basic test
			)

			require.NoError(t, err)
			require.NotNil(t, plan)
			require.Len(t, plan.PositionSells, 1)

			assert.LessOrEqual(t, plan.PositionSells[0].SellQuantity, tt.expectedMaxQty,
				"%s: Quantity %d should not exceed max %d",
				tt.description, plan.PositionSells[0].SellQuantity, tt.expectedMaxQty)

			assert.LessOrEqual(t, plan.PositionSells[0].SellPercentage, tt.maxSellPercentage,
				"%s: Sell percentage %.2f should not exceed max %.2f",
				tt.description, plan.PositionSells[0].SellPercentage, tt.maxSellPercentage)
		})
	}
}

func TestCalculateGeographySellPlan_CalculatesCorrectValueToReduce(t *testing.T) {
	tests := []struct {
		name                  string
		portfolioValue        float64
		overweightPercent     float64
		expectedValueToReduce float64
		tolerance             float64 // Acceptable deviation
	}{
		{
			name:                  "10% overweight on 100k portfolio",
			portfolioValue:        100000,
			overweightPercent:     0.10,
			expectedValueToReduce: 10000, // 10% of 100k
			tolerance:             100,
		},
		{
			name:                  "5% overweight on 50k portfolio",
			portfolioValue:        50000,
			overweightPercent:     0.05,
			expectedValueToReduce: 2500, // 5% of 50k
			tolerance:             50,
		},
		{
			name:                  "30% overweight on 200k portfolio",
			portfolioValue:        200000,
			overweightPercent:     0.30,
			expectedValueToReduce: 60000, // 30% of 200k
			tolerance:             500,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			position := createTestEnrichedPosition(1000, 100.0, "US")
			ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, tt.portfolioValue)

			plan, err := CalculateGeographySellPlan(
				"US",
				tt.overweightPercent,
				[]planningdomain.EnrichedPosition{position},
				ctx,
				0.20, // 20% max
				nil,
				nil,
			)

			require.NoError(t, err)
			require.NotNil(t, plan)

			assert.InDelta(t, tt.expectedValueToReduce, plan.TotalValueToReduce, tt.tolerance,
				"TotalValueToReduce should be approximately %.2f", tt.expectedValueToReduce)
		})
	}
}

func TestCalculateGeographySellPlan_DistributesAcrossPositions(t *testing.T) {
	// Given: Geography needs 6000 EUR reduction
	// And: 3 positions worth 10000 EUR each (30000 total in geography)
	// When: CalculateGeographySellPlan is called
	// Then: Reduction should be distributed across positions (approx 2000 EUR each)

	position1 := createTestEnrichedPositionWithISIN("US111", 100, 100.0, "US") // 10000 EUR
	position2 := createTestEnrichedPositionWithISIN("US222", 100, 100.0, "US") // 10000 EUR
	position3 := createTestEnrichedPositionWithISIN("US333", 100, 100.0, "US") // 10000 EUR

	positions := []planningdomain.EnrichedPosition{position1, position2, position3}
	ctx := createTestOpportunityContext(positions, 100000) // 100k portfolio

	plan, err := CalculateGeographySellPlan(
		"US",
		0.06, // 6% overweight = 6000 EUR to reduce
		positions,
		ctx,
		0.20, // 20% max per position
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, plan)
	require.Len(t, plan.PositionSells, 3, "Should create sell plans for all 3 positions")

	// Each position should sell some amount (roughly equal if same quality)
	totalSellValue := 0.0
	for _, posSell := range plan.PositionSells {
		totalSellValue += posSell.SellValueEUR
		// No single position should exceed 20% (2000 EUR of 10000)
		assert.LessOrEqual(t, posSell.SellValueEUR, 2000.0,
			"Position %s should not sell more than 20%% (2000 EUR)", posSell.Symbol)
	}

	// Total sell value should aim for 6000 EUR (may be capped by max per position)
	// With 20% max per position and 10000 EUR each, max total is 6000 EUR
	assert.InDelta(t, 6000, totalSellValue, 500,
		"Total sell value should be approximately 6000 EUR")
}

func TestCalculateGeographySellPlan_NeverSells100Percent(t *testing.T) {
	// Even when geography needs massive reduction, should never recommend selling 100%

	position := createTestEnrichedPosition(100, 100.0, "US") // 10000 EUR position
	ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, 20000)

	plan, err := CalculateGeographySellPlan(
		"US",
		0.80, // 80% overweight - massive reduction needed
		[]planningdomain.EnrichedPosition{position},
		ctx,
		0.80, // Even with 80% max sell percentage
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, plan)
	require.Len(t, plan.PositionSells, 1)

	// Should cap at MaxSellPercentageAbsolute (80%), never 100%
	assert.Less(t, plan.PositionSells[0].SellPercentage, 1.0,
		"Should never recommend selling 100%% of position")
	assert.LessOrEqual(t, plan.PositionSells[0].SellPercentage, MaxSellPercentageAbsolute,
		"Should cap at absolute maximum of %.0f%%", MaxSellPercentageAbsolute*100)
}

func TestCalculateGeographySellPlan_RespectsLotSize(t *testing.T) {
	// Create position with min_lot of 10
	position := planningdomain.EnrichedPosition{
		ISIN:           "US1234567890",
		Symbol:         "TEST.US",
		Quantity:       100,
		CurrentPrice:   10.0,
		MarketValueEUR: 1000.0,
		Geography:      "US",
		AllowSell:      true,
		MinLot:         10, // Minimum lot size of 10
	}

	ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, 10000)

	plan, err := CalculateGeographySellPlan(
		"US",
		0.15, // 15% overweight
		[]planningdomain.EnrichedPosition{position},
		ctx,
		0.20,
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, plan)

	if len(plan.PositionSells) > 0 {
		// Sell quantity should be a multiple of lot size
		sellQty := plan.PositionSells[0].SellQuantity
		assert.Equal(t, 0, sellQty%10,
			"Sell quantity %d should be a multiple of lot size 10", sellQty)
	}
}

func TestCalculateGeographySellPlan_HandlesSmallOverweight(t *testing.T) {
	// When overweight is very small, may not generate any sells

	position := createTestEnrichedPosition(100, 100.0, "US")
	ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, 100000)

	plan, err := CalculateGeographySellPlan(
		"US",
		0.01, // Only 1% overweight = 1000 EUR to reduce
		[]planningdomain.EnrichedPosition{position},
		ctx,
		0.20,
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, plan)

	// Should still create plan with small reduction
	assert.InDelta(t, 1000, plan.TotalValueToReduce, 100)
}

func TestCalculateGeographySellPlan_EmptyPositionList(t *testing.T) {
	ctx := createTestOpportunityContext(nil, 100000)

	plan, err := CalculateGeographySellPlan(
		"US",
		0.10,
		[]planningdomain.EnrichedPosition{}, // Empty
		ctx,
		0.20,
		nil,
		nil,
	)

	require.NoError(t, err)
	require.NotNil(t, plan)
	assert.Empty(t, plan.PositionSells, "Should return empty plan for empty positions")
}

func TestSellQuantityFormula_OldFormulaComparison(t *testing.T) {
	// Demonstrate that the old formula was wrong
	// Old formula: sellPercentage = overweight / (overweight + minOverweightThreshold)

	tests := []struct {
		name              string
		overweight        float64
		minThreshold      float64
		oldFormulaPct     float64 // What old formula would calculate
		maxSellPct        float64
		newShouldBeCapped bool // New formula should cap at maxSellPct
	}{
		{
			name:              "10% overweight",
			overweight:        0.10,
			minThreshold:      0.05,
			oldFormulaPct:     0.667, // 0.10 / 0.15 = 66.7% - WAY too high!
			maxSellPct:        0.20,
			newShouldBeCapped: true, // Should cap at 20%
		},
		{
			name:              "30% overweight",
			overweight:        0.30,
			minThreshold:      0.05,
			oldFormulaPct:     0.857, // 0.30 / 0.35 = 85.7% - WAY too high!
			maxSellPct:        0.20,
			newShouldBeCapped: true, // Should cap at 20%
		},
		{
			name:              "50% overweight",
			overweight:        0.50,
			minThreshold:      0.05,
			oldFormulaPct:     0.909, // 0.50 / 0.55 = 90.9% - almost everything!
			maxSellPct:        0.20,
			newShouldBeCapped: true, // Should cap at 20%
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Verify old formula calculation for documentation
			oldPct := tt.overweight / (tt.overweight + tt.minThreshold)
			assert.InDelta(t, tt.oldFormulaPct, oldPct, 0.01,
				"Old formula verification: %.1f%% overweight should give %.1f%%",
				tt.overweight*100, tt.oldFormulaPct*100)

			// Verify that old formula exceeds max sell percentage
			assert.Greater(t, oldPct, tt.maxSellPct,
				"Old formula (%.1f%%) exceeds max sell percentage (%.1f%%)",
				oldPct*100, tt.maxSellPct*100)

			// New formula should cap correctly
			position := createTestEnrichedPosition(1000, 10.0, "US")
			ctx := createTestOpportunityContext([]planningdomain.EnrichedPosition{position}, 100000)

			plan, err := CalculateGeographySellPlan(
				"US",
				tt.overweight,
				[]planningdomain.EnrichedPosition{position},
				ctx,
				tt.maxSellPct,
				nil,
				nil,
			)

			require.NoError(t, err)
			require.NotNil(t, plan)

			if len(plan.PositionSells) > 0 {
				assert.LessOrEqual(t, plan.PositionSells[0].SellPercentage, tt.maxSellPct,
					"New formula should cap at %.1f%%", tt.maxSellPct*100)
			}
		})
	}
}

// Test helpers

func createTestEnrichedPosition(quantity, price float64, geography string) planningdomain.EnrichedPosition {
	return planningdomain.EnrichedPosition{
		ISIN:           "US1234567890",
		Symbol:         "TEST.US",
		Quantity:       quantity,
		CurrentPrice:   price,
		MarketValueEUR: quantity * price,
		Geography:      geography,
		AllowSell:      true,
		MinLot:         1,
	}
}

func createTestEnrichedPositionWithISIN(isin string, quantity, price float64, geography string) planningdomain.EnrichedPosition {
	return planningdomain.EnrichedPosition{
		ISIN:           isin,
		Symbol:         "TEST-" + isin,
		Quantity:       quantity,
		CurrentPrice:   price,
		MarketValueEUR: quantity * price,
		Geography:      geography,
		AllowSell:      true,
		MinLot:         1,
	}
}

func createTestOpportunityContext(positions []planningdomain.EnrichedPosition, portfolioValue float64) *planningdomain.OpportunityContext {
	currentPrices := make(map[string]float64)
	stocksByISIN := make(map[string]universe.Security)

	for _, pos := range positions {
		currentPrices[pos.ISIN] = pos.CurrentPrice
		stocksByISIN[pos.ISIN] = universe.Security{
			ISIN:      pos.ISIN,
			Symbol:    pos.Symbol,
			Geography: pos.Geography,
			AllowSell: pos.AllowSell,
			MinLot:    pos.MinLot,
		}
	}

	return &planningdomain.OpportunityContext{
		EnrichedPositions:      positions,
		CurrentPrices:          currentPrices,
		StocksByISIN:           stocksByISIN,
		TotalPortfolioValueEUR: portfolioValue,
		AllowSell:              true,
	}
}
