package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// OpportunityBuysCalculator identifies new buying opportunities based on security scores.
type OpportunityBuysCalculator struct {
	*BaseCalculator
}

// NewOpportunityBuysCalculator creates a new opportunity buys calculator.
func NewOpportunityBuysCalculator(log zerolog.Logger) *OpportunityBuysCalculator {
	return &OpportunityBuysCalculator{
		BaseCalculator: NewBaseCalculator(log, "opportunity_buys"),
	}
}

// Name returns the calculator name.
func (c *OpportunityBuysCalculator) Name() string {
	return "opportunity_buys"
}

// Category returns the opportunity category.
func (c *OpportunityBuysCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryOpportunityBuys
}

// Calculate identifies opportunity buy candidates.
func (c *OpportunityBuysCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minScore := GetFloatParam(params, "min_score", 0.7)                        // Minimum score threshold
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	minValuePerPosition := GetFloatParam(params, "min_value_per_position", 100.0)
	maxPositions := GetIntParam(params, "max_positions", 5)                    // Default to top 5
	excludeExisting := GetBoolParam(params, "exclude_existing", false)         // Exclude positions we already have

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping opportunity buys")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= minValuePerPosition {
		c.log.Debug().Msg("Insufficient cash for opportunity buys")
		return nil, nil
	}

	if ctx.SecurityScores == nil || len(ctx.SecurityScores) == 0 {
		c.log.Debug().Msg("No security scores available")
		return nil, nil
	}

	c.log.Debug().
		Float64("min_score", minScore).
		Int("max_positions", maxPositions).
		Msg("Calculating opportunity buys")

	// Build list of scored securities
	type scoredSecurity struct {
		symbol string
		score  float64
	}
	var scoredSecurities []scoredSecurity

	// Check which positions we already have
	existingPositions := make(map[string]bool)
	for _, position := range ctx.Positions {
		existingPositions[position.Symbol] = true
	}

	for symbol, score := range ctx.SecurityScores {
		// Skip if below threshold
		if score < minScore {
			continue
		}

		// Skip if we already have this position and exclude_existing is true
		if excludeExisting && existingPositions[symbol] {
			continue
		}

		// Skip if recently bought
		if ctx.RecentlyBought[symbol] {
			continue
		}

		scoredSecurities = append(scoredSecurities, scoredSecurity{
			symbol: symbol,
			score:  score,
		})
	}

	// Sort by score descending
	sort.Slice(scoredSecurities, func(i, j int) bool {
		return scoredSecurities[i].score > scoredSecurities[j].score
	})

	// Take top N
	if maxPositions > 0 && len(scoredSecurities) > maxPositions {
		scoredSecurities = scoredSecurities[:maxPositions]
	}

	// Create candidates
	var candidates []domain.ActionCandidate
	for _, scored := range scoredSecurities {
		symbol := scored.symbol
		score := scored.score

		// Get security info
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("Security not found in stocks map")
			continue
		}

		// Get current price
		currentPrice, ok := ctx.CurrentPrices[symbol]
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("No current price available")
			continue
		}

		// Calculate quantity based on max value
		targetValue := maxValuePerPosition
		if targetValue > ctx.AvailableCashEUR {
			targetValue = ctx.AvailableCashEUR
		}

		quantity := int(targetValue / currentPrice)
		if quantity == 0 {
			quantity = 1
		}

		// Calculate actual value
		valueEUR := float64(quantity) * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		totalCostEUR := valueEUR + transactionCost

		// Check if we have enough cash
		if totalCostEUR > ctx.AvailableCashEUR {
			continue
		}

		// Priority is based on score
		priority := score

		// Build reason
		reason := fmt.Sprintf("High score: %.2f - opportunity buy", score)

		// Build tags
		tags := []string{"opportunity_buy", "high_score"}
		if !existingPositions[symbol] {
			tags = append(tags, "new_position")
		}

		candidate := domain.ActionCandidate{
			Side:     "BUY",
			Symbol:   symbol,
			Name:     security.Name,
			Quantity: quantity,
			Price:    currentPrice,
			ValueEUR: totalCostEUR,
			Currency: string(security.Currency),
			Priority: priority,
			Reason:   reason,
			Tags:     tags,
		}

		candidates = append(candidates, candidate)
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Msg("Opportunity buy candidates identified")

	return candidates, nil
}

func init() {
	// Auto-register on import
	DefaultCalculatorRegistry.Register(NewOpportunityBuysCalculator(zerolog.Nop()))
}
