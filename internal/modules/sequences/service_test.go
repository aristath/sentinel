package sequences

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestGeneratorNormalizeSequence(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	tests := []struct {
		name     string
		input    []domain.ActionCandidate
		expected []domain.ActionCandidate
	}{
		{
			name: "SELL actions already before BUY - no change needed",
			input: []domain.ActionCandidate{
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
			},
			expected: []domain.ActionCandidate{
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
			},
		},
		{
			name: "BUY actions before SELL - should reorder",
			input: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
				{Side: "BUY", Symbol: "TSLA", ISIN: "US88160R1014", Quantity: 2},
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
			},
			expected: []domain.ActionCandidate{
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
				{Side: "BUY", Symbol: "TSLA", ISIN: "US88160R1014", Quantity: 2},
			},
		},
		{
			name: "Mixed order - should reorder",
			input: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "BUY", Symbol: "TSLA", ISIN: "US88160R1014", Quantity: 2},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
			},
			expected: []domain.ActionCandidate{
				{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10},
				{Side: "SELL", Symbol: "MSFT", ISIN: "US5949181045", Quantity: 5},
				{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 3},
				{Side: "BUY", Symbol: "TSLA", ISIN: "US88160R1014", Quantity: 2},
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := generator.normalizeSequence(tt.input)

			require.Equal(t, len(tt.expected), len(result), "Should have same number of actions")

			// Verify SELL before BUY
			seenBuy := false
			for i, action := range result {
				if action.Side == "BUY" {
					seenBuy = true
				}
				if action.Side == "SELL" && seenBuy {
					t.Errorf("SELL action found after BUY at index %d", i)
				}
			}

			// Verify expected order
			for i, expected := range tt.expected {
				assert.Equal(t, expected.Side, result[i].Side, "Action %d should have correct side", i)
				assert.Equal(t, expected.ISIN, result[i].ISIN, "Action %d should have correct ISIN", i)
			}
		})
	}
}

func TestGeneratorCashFeasibility(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	tests := []struct {
		name          string
		actions       []domain.ActionCandidate
		availableCash float64
		expectedOk    bool
	}{
		{
			name: "Enough cash for buys",
			actions: []domain.ActionCandidate{
				{Side: "SELL", ValueEUR: 1000},
				{Side: "BUY", ValueEUR: 500},
			},
			availableCash: 100,
			expectedOk:    true,
		},
		{
			name: "Not enough cash without sells",
			actions: []domain.ActionCandidate{
				{Side: "BUY", ValueEUR: 500},
			},
			availableCash: 100,
			expectedOk:    false,
		},
		{
			name: "Sells generate enough cash",
			actions: []domain.ActionCandidate{
				{Side: "SELL", ValueEUR: 1000},
				{Side: "BUY", ValueEUR: 1050},
			},
			availableCash: 100,
			expectedOk:    true,
		},
		{
			name: "Sells don't generate enough cash",
			actions: []domain.ActionCandidate{
				{Side: "SELL", ValueEUR: 500},
				{Side: "BUY", ValueEUR: 1000},
			},
			availableCash: 100,
			expectedOk:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := generator.checkCashFeasibility(tt.actions, tt.availableCash)
			assert.Equal(t, tt.expectedOk, result)
		})
	}
}

func TestGeneratorCombinations(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	items := []domain.ActionCandidate{
		{Side: "SELL", Symbol: "A", ISIN: "ISIN_A"},
		{Side: "SELL", Symbol: "B", ISIN: "ISIN_B"},
		{Side: "BUY", Symbol: "C", ISIN: "ISIN_C"},
	}

	// Test combinations of size 2
	combos := generator.generateCombinations(items, 2)
	assert.Len(t, combos, 3, "Should generate 3 combinations (3 choose 2)")

	// Test combinations of size 1
	combos = generator.generateCombinations(items, 1)
	assert.Len(t, combos, 3, "Should generate 3 single-item combinations")

	// Test combinations of size 3
	combos = generator.generateCombinations(items, 3)
	assert.Len(t, combos, 1, "Should generate 1 combination of all items")
}

func TestGeneratorGenerateWithOpportunities(t *testing.T) {
	log := zerolog.Nop()
	generator := NewExhaustiveGenerator(log, nil)

	opportunities := domain.OpportunitiesByCategory{
		domain.OpportunityCategoryProfitTaking: []domain.ActionCandidate{
			{Side: "SELL", Symbol: "AAPL", ISIN: "US0378331005", Quantity: 10, ValueEUR: 1000, Priority: 0.8},
		},
		domain.OpportunityCategoryOpportunityBuys: []domain.ActionCandidate{
			{Side: "BUY", Symbol: "GOOGL", ISIN: "US02079K1079", Quantity: 5, ValueEUR: 500, Priority: 0.7},
		},
	}

	ctx := &domain.OpportunityContext{
		AllowSell:           true,
		AllowBuy:            true,
		AvailableCashEUR:    100,
		RecentlySoldISINs:   make(map[string]bool),
		RecentlyBoughtISINs: make(map[string]bool),
		IneligibleISINs:     make(map[string]bool),
	}

	config := GenerationConfig{
		MaxDepth:        3,
		AvailableCash:   100,
		PruneInfeasible: true,
	}

	sequences := generator.Generate(opportunities, ctx, config)

	// Should generate:
	// - depth 1: SELL AAPL, BUY GOOGL (but BUY alone not feasible without cash)
	// - depth 2: SELL AAPL + BUY GOOGL (feasible)
	assert.NotEmpty(t, sequences, "Should generate at least one sequence")

	// All sequences should have SELL before BUY
	for _, seq := range sequences {
		seenBuy := false
		for _, action := range seq.Actions {
			if action.Side == "BUY" {
				seenBuy = true
			}
			if action.Side == "SELL" && seenBuy {
				t.Errorf("SELL after BUY in sequence: %v", seq.Actions)
			}
		}
	}
}
