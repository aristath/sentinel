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

func TestProfitTakingCalculator_NoMaxSellPercentage(t *testing.T) {
	log := zerolog.Nop()
	tagFilter := &mockTagFilter{sellCandidates: []string{}}
	securityRepo := &mockSecurityRepo{tags: map[string][]string{}}
	calc := NewProfitTakingCalculator(tagFilter, securityRepo, log)

	// When max_sell_percentage is not provided, should use sell_percentage (default 100%)
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
		// No max_sell_percentage provided
	}

	result, err := calc.Calculate(ctx, params)
	require.NoError(t, err)
	require.Len(t, result.Candidates, 1)

	// Should sell 100% (1000 shares) when no max_sell_percentage is set
	assert.Equal(t, 1000, result.Candidates[0].Quantity)
}
