package domain

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNewMoney(t *testing.T) {
	tests := []struct {
		name     string
		amount   float64
		currency Currency
		expected Money
	}{
		{
			name:     "EUR money",
			amount:   100.50,
			currency: CurrencyEUR,
			expected: Money{Amount: 100.50, Currency: CurrencyEUR},
		},
		{
			name:     "USD money",
			amount:   50.25,
			currency: CurrencyUSD,
			expected: Money{Amount: 50.25, Currency: CurrencyUSD},
		},
		{
			name:     "GBP money",
			amount:   75.0,
			currency: CurrencyGBP,
			expected: Money{Amount: 75.0, Currency: CurrencyGBP},
		},
		{
			name:     "zero amount",
			amount:   0.0,
			currency: CurrencyUSD,
			expected: Money{Amount: 0.0, Currency: CurrencyUSD},
		},
		{
			name:     "negative amount",
			amount:   -10.0,
			currency: CurrencyEUR,
			expected: Money{Amount: -10.0, Currency: CurrencyEUR},
		},
		{
			name:     "TEST currency",
			amount:   999.99,
			currency: CurrencyTEST,
			expected: Money{Amount: 999.99, Currency: CurrencyTEST},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := NewMoney(tt.amount, tt.currency)
			assert.Equal(t, tt.expected, result)
			assert.Equal(t, tt.amount, result.Amount)
			assert.Equal(t, tt.currency, result.Currency)
		})
	}
}

func TestCurrency_Constants(t *testing.T) {
	// Test that currency constants are defined correctly
	assert.Equal(t, Currency("EUR"), CurrencyEUR)
	assert.Equal(t, Currency("USD"), CurrencyUSD)
	assert.Equal(t, Currency("GBP"), CurrencyGBP)
	assert.Equal(t, Currency("TEST"), CurrencyTEST)
}

// Security tests removed - use universe.Security tests instead (single source of truth).
// See internal/modules/universe/*_test.go for security model tests.

func TestPosition_Fields(t *testing.T) {
	now := time.Now()
	position := Position{
		LastUpdated:  now,
		Symbol:       "AAPL.US",
		ISIN:         "US0378331005",
		Currency:     CurrencyUSD,
		ID:           1,
		SecurityID:   100,
		Quantity:     10.0,
		AverageCost:  150.0,
		CurrentPrice: 175.0,
		MarketValue:  1750.0,
		UnrealizedPL: 250.0,
	}

	assert.Equal(t, now, position.LastUpdated)
	assert.Equal(t, "AAPL.US", position.Symbol)
	assert.Equal(t, "US0378331005", position.ISIN)
	assert.Equal(t, CurrencyUSD, position.Currency)
	assert.Equal(t, int64(1), position.ID)
	assert.Equal(t, int64(100), position.SecurityID)
	assert.Equal(t, 10.0, position.Quantity)
	assert.Equal(t, 150.0, position.AverageCost)
	assert.Equal(t, 175.0, position.CurrentPrice)
	assert.Equal(t, 1750.0, position.MarketValue)
	assert.Equal(t, 250.0, position.UnrealizedPL)
}

func TestTrade_Fields(t *testing.T) {
	now := time.Now()
	executedAt := now.Add(-1 * time.Hour)
	trade := Trade{
		ExecutedAt: executedAt,
		CreatedAt:  now,
		Symbol:     "AAPL.US",
		Side:       "BUY",
		Currency:   CurrencyUSD,
		ID:         1,
		SecurityID: 100,
		Quantity:   10.0,
		Price:      150.0,
		Fees:       1.5,
		Total:      1501.5,
	}

	assert.Equal(t, executedAt, trade.ExecutedAt)
	assert.Equal(t, now, trade.CreatedAt)
	assert.Equal(t, "AAPL.US", trade.Symbol)
	assert.Equal(t, "BUY", trade.Side)
	assert.Equal(t, CurrencyUSD, trade.Currency)
	assert.Equal(t, int64(1), trade.ID)
	assert.Equal(t, int64(100), trade.SecurityID)
	assert.Equal(t, 10.0, trade.Quantity)
	assert.Equal(t, 150.0, trade.Price)
	assert.Equal(t, 1.5, trade.Fees)
	assert.Equal(t, 1501.5, trade.Total)
}
