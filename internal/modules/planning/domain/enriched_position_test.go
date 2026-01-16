package domain

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestEnrichedPosition_GainPercent_PositiveGain(t *testing.T) {
	pos := EnrichedPosition{
		AverageCost:  100.0,
		CurrentPrice: 120.0,
	}

	gainPercent := pos.GainPercent()

	assert.Equal(t, 0.20, gainPercent, "Expected 20% gain")
}

func TestEnrichedPosition_GainPercent_NegativeGain(t *testing.T) {
	pos := EnrichedPosition{
		AverageCost:  100.0,
		CurrentPrice: 80.0,
	}

	gainPercent := pos.GainPercent()

	assert.Equal(t, -0.20, gainPercent, "Expected 20% loss")
}

func TestEnrichedPosition_GainPercent_ZeroCost(t *testing.T) {
	pos := EnrichedPosition{
		AverageCost:  0.0,
		CurrentPrice: 100.0,
	}

	gainPercent := pos.GainPercent()

	assert.Equal(t, 0.0, gainPercent, "Expected 0% when cost is zero (edge case)")
}

func TestEnrichedPosition_GainPercent_EqualCostAndPrice(t *testing.T) {
	pos := EnrichedPosition{
		AverageCost:  100.0,
		CurrentPrice: 100.0,
	}

	gainPercent := pos.GainPercent()

	assert.Equal(t, 0.0, gainPercent, "Expected 0% gain when cost equals price")
}

func TestEnrichedPosition_CanBuy_ActiveAndAllowed(t *testing.T) {
	pos := EnrichedPosition{
		AllowBuy: true,
	}

	assert.True(t, pos.CanBuy(), "Expected CanBuy=true when active and allowed")
}

func TestEnrichedPosition_CanBuy_InactiveSecurity(t *testing.T) {
	t.Skip("After migration 038: No inactive securities (no soft delete)")
	pos := EnrichedPosition{
		AllowBuy: true,
	}

	assert.False(t, pos.CanBuy(), "Expected CanBuy=false when security inactive")
}

func TestEnrichedPosition_CanBuy_ActiveButNotAllowed(t *testing.T) {
	pos := EnrichedPosition{
		AllowBuy: false,
	}

	assert.False(t, pos.CanBuy(), "Expected CanBuy=false when not allowed")
}

func TestEnrichedPosition_CanSell_ActiveAndAllowed(t *testing.T) {
	pos := EnrichedPosition{
		AllowSell: true,
	}

	assert.True(t, pos.CanSell(), "Expected CanSell=true when active and allowed")
}

func TestEnrichedPosition_CanSell_InactiveSecurity(t *testing.T) {
	t.Skip("After migration 038: No inactive securities (no soft delete)")
	pos := EnrichedPosition{
		AllowSell: true,
	}

	assert.False(t, pos.CanSell(), "Expected CanSell=false when security inactive")
}

func TestEnrichedPosition_CanSell_ActiveButNotAllowed(t *testing.T) {
	pos := EnrichedPosition{
		AllowSell: false,
	}

	assert.False(t, pos.CanSell(), "Expected CanSell=false when not allowed")
}

func TestEnrichedPosition_AllFieldsPopulated(t *testing.T) {
	now := time.Now().UTC()
	firstBought := now.AddDate(0, -6, 0) // 6 months ago
	lastSold := now.AddDate(0, -1, 0)    // 1 month ago
	daysHeld := 180

	pos := EnrichedPosition{
		// Core position data
		ISIN:             "US0378331005",
		Symbol:           "AAPL",
		Quantity:         100.0,
		AverageCost:      150.0,
		Currency:         "USD",
		CurrencyRate:     1.1,
		MarketValueEUR:   13636.36,
		CostBasisEUR:     13636.36,
		UnrealizedPnL:    0.0,
		UnrealizedPnLPct: 0.0,
		LastUpdated:      &now,
		FirstBoughtAt:    &firstBought,
		LastSoldAt:       &lastSold,

		// Security metadata
		SecurityName: "Apple Inc.",
		Geography:    "US",
		Exchange:     "NASDAQ",
		AllowBuy:     true,
		AllowSell:    true,
		MinLot:       1,

		// Market data
		CurrentPrice: 150.0,

		// Calculated fields
		DaysHeld:          &daysHeld,
		WeightInPortfolio: 0.15,
	}

	// Verify all fields can be read
	assert.Equal(t, "US0378331005", pos.ISIN)
	assert.Equal(t, "AAPL", pos.Symbol)
	assert.Equal(t, 100.0, pos.Quantity)
	assert.Equal(t, 150.0, pos.AverageCost)
	assert.Equal(t, "USD", pos.Currency)
	assert.Equal(t, 1.1, pos.CurrencyRate)
	assert.Equal(t, 13636.36, pos.MarketValueEUR)
	assert.Equal(t, 13636.36, pos.CostBasisEUR)
	assert.Equal(t, 0.0, pos.UnrealizedPnL)
	assert.Equal(t, 0.0, pos.UnrealizedPnLPct)
	require.NotNil(t, pos.LastUpdated)
	assert.True(t, now.Equal(*pos.LastUpdated))
	require.NotNil(t, pos.FirstBoughtAt)
	assert.True(t, firstBought.Equal(*pos.FirstBoughtAt))
	require.NotNil(t, pos.LastSoldAt)
	assert.True(t, lastSold.Equal(*pos.LastSoldAt))
	assert.Equal(t, "Apple Inc.", pos.SecurityName)
	assert.Equal(t, "US", pos.Geography)
	assert.Equal(t, "NASDAQ", pos.Exchange)
	// Active field removed after migration 038 (no soft delete - all securities in DB are active)
	assert.True(t, pos.AllowBuy)
	assert.True(t, pos.AllowSell)
	assert.Equal(t, 1, pos.MinLot)
	assert.Equal(t, 150.0, pos.CurrentPrice)
	require.NotNil(t, pos.DaysHeld)
	assert.Equal(t, 180, *pos.DaysHeld)
	assert.Equal(t, 0.15, pos.WeightInPortfolio)
}

func TestEnrichedPosition_NilTimestamps(t *testing.T) {
	pos := EnrichedPosition{
		ISIN:          "US0378331005",
		Symbol:        "AAPL",
		LastUpdated:   nil,
		FirstBoughtAt: nil,
		LastSoldAt:    nil,
		DaysHeld:      nil,
	}

	// Verify nil timestamps are handled gracefully
	assert.Nil(t, pos.LastUpdated)
	assert.Nil(t, pos.FirstBoughtAt)
	assert.Nil(t, pos.LastSoldAt)
	assert.Nil(t, pos.DaysHeld)

	// GainPercent should still work
	pos.AverageCost = 100.0
	pos.CurrentPrice = 120.0
	assert.Equal(t, 0.20, pos.GainPercent())

	// CanBuy/CanSell should still work
	pos.Active = true
	pos.AllowBuy = true
	pos.AllowSell = true
	assert.True(t, pos.CanBuy())
	assert.True(t, pos.CanSell())
}
