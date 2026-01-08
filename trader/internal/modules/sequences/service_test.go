package sequences

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestEnsureSellBeforeBuy(t *testing.T) {
	log := zerolog.Nop()
	service := &Service{
		log: log,
	}

	tests := []struct {
		name     string
		input    []domain.ActionSequence
		expected []domain.ActionSequence
	}{
		{
			name: "SELL actions already before BUY - no change",
			input: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
					},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
					},
					PatternType: "test",
				},
			},
		},
		{
			name: "BUY actions before SELL - should reorder",
			input: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
					},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
					},
					PatternType: "test",
				},
			},
		},
		{
			name: "Mixed order - should reorder",
			input: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
					},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
					},
					PatternType: "test",
				},
			},
		},
		{
			name: "Only BUY actions - no change",
			input: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
					},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "BUY", Symbol: "GOOGL", Quantity: 3},
						{Side: "BUY", Symbol: "TSLA", Quantity: 2},
					},
					PatternType: "test",
				},
			},
		},
		{
			name: "Only SELL actions - no change",
			input: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
					},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions: []domain.ActionCandidate{
						{Side: "SELL", Symbol: "AAPL", Quantity: 10},
						{Side: "SELL", Symbol: "MSFT", Quantity: 5},
					},
					PatternType: "test",
				},
			},
		},
		{
			name: "Empty sequence - no change",
			input: []domain.ActionSequence{
				{
					Actions:     []domain.ActionCandidate{},
					PatternType: "test",
				},
			},
			expected: []domain.ActionSequence{
				{
					Actions:     []domain.ActionCandidate{},
					PatternType: "test",
				},
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.ensureSellBeforeBuy(tt.input)

			assert.Equal(t, len(tt.expected), len(result), "Result should have same number of sequences")

			for i, expectedSeq := range tt.expected {
				if i < len(result) {
					actualSeq := result[i]

					// Check that actions are properly ordered
					assert.Equal(t, len(expectedSeq.Actions), len(actualSeq.Actions), "Sequence %d should have same number of actions", i)

					for j, expectedAction := range expectedSeq.Actions {
						if j < len(actualSeq.Actions) {
							actualAction := actualSeq.Actions[j]
							assert.Equal(t, expectedAction.Side, actualAction.Side, "Action %d in sequence %d should have correct side", j, i)
							assert.Equal(t, expectedAction.Symbol, actualAction.Symbol, "Action %d in sequence %d should have correct symbol", j, i)
						}
					}

					// Verify that SELL actions come before BUY actions
					seenBuy := false
					for _, action := range actualSeq.Actions {
						if action.Side == "BUY" {
							seenBuy = true
						}
						if action.Side == "SELL" && seenBuy {
							t.Errorf("SELL action found after BUY action in sequence %d", i)
						}
					}

					// Check that hash was regenerated (should be different if order changed)
					assert.NotEmpty(t, actualSeq.SequenceHash, "Sequence hash should be set")
					assert.Equal(t, expectedSeq.PatternType, actualSeq.PatternType, "Pattern type should be preserved")
				}
			}
		})
	}
}
