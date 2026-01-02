package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// RebalanceBuysCalculator identifies underweight positions to buy for rebalancing.
type RebalanceBuysCalculator struct {
	*BaseCalculator
}

// NewRebalanceBuysCalculator creates a new rebalance buys calculator.
func NewRebalanceBuysCalculator(log zerolog.Logger) *RebalanceBuysCalculator {
	return &RebalanceBuysCalculator{
		BaseCalculator: NewBaseCalculator(log, "rebalance_buys"),
	}
}

// Name returns the calculator name.
func (c *RebalanceBuysCalculator) Name() string {
	return "rebalance_buys"
}

// Category returns the opportunity category.
func (c *RebalanceBuysCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryRebalanceBuys
}

// Calculate identifies rebalance buy opportunities.
func (c *RebalanceBuysCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minUnderweightThreshold := GetFloatParam(params, "min_underweight_threshold", 0.05) // 5% underweight
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	minScore := GetFloatParam(params, "min_score", 0.6)     // Minimum security score
	maxPositions := GetIntParam(params, "max_positions", 0) // 0 = unlimited

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping rebalance buys")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= 0 {
		c.log.Debug().Msg("No available cash")
		return nil, nil
	}

	// Check if we have country allocations and weights
	if ctx.CountryAllocations == nil || ctx.CountryWeights == nil {
		c.log.Debug().Msg("No country allocation data available")
		return nil, nil
	}

	c.log.Debug().
		Float64("min_underweight_threshold", minUnderweightThreshold).
		Msg("Calculating rebalance buys")

	// Identify underweight countries
	underweightCountries := make(map[string]float64)
	for country, targetAllocation := range ctx.CountryWeights {
		currentAllocation := ctx.CountryAllocations[country]
		underweight := targetAllocation - currentAllocation
		if underweight > minUnderweightThreshold {
			underweightCountries[country] = underweight
			c.log.Debug().
				Str("country", country).
				Float64("current", currentAllocation).
				Float64("target", targetAllocation).
				Float64("underweight", underweight).
				Msg("Underweight country identified")
		}
	}

	if len(underweightCountries) == 0 {
		c.log.Debug().Msg("No underweight countries")
		return nil, nil
	}

	// Build candidates for securities in underweight countries
	type scoredCandidate struct {
		symbol      string
		group       string
		underweight float64
		score       float64
	}
	var scoredCandidates []scoredCandidate

	for symbol := range ctx.StocksBySymbol {
		// Skip if recently bought
		if ctx.RecentlyBought[symbol] {
			continue
		}

		// Get security and extract country
		security := ctx.StocksBySymbol[symbol]
		country := security.Country
		if country == "" {
			continue // Skip securities without country
		}

		// Map country to group
		group := country
		if ctx.CountryToGroup != nil {
			if mappedGroup, ok := ctx.CountryToGroup[country]; ok {
				group = mappedGroup
			} else {
				group = "OTHER"
			}
		}

		// Check if this group is underweight
		underweight, ok := underweightCountries[group]
		if !ok {
			continue
		}

		// Get security score
		score := 0.5 // Default neutral score
		if ctx.SecurityScores != nil {
			if s, ok := ctx.SecurityScores[symbol]; ok {
				score = s
			}
		}

		// Filter by minimum score
		if score < minScore {
			continue
		}

		scoredCandidates = append(scoredCandidates, scoredCandidate{
			symbol:      symbol,
			group:       group,
			underweight: underweight,
			score:       score,
		})
	}

	// Sort by combined priority (underweight * score)
	sort.Slice(scoredCandidates, func(i, j int) bool {
		priorityI := scoredCandidates[i].underweight * scoredCandidates[i].score
		priorityJ := scoredCandidates[j].underweight * scoredCandidates[j].score
		return priorityI > priorityJ
	})

	// Limit if needed
	if maxPositions > 0 && len(scoredCandidates) > maxPositions {
		scoredCandidates = scoredCandidates[:maxPositions]
	}

	// Create action candidates
	var candidates []domain.ActionCandidate
	for _, scored := range scoredCandidates {
		symbol := scored.symbol
		security := ctx.StocksBySymbol[symbol]

		// Get current price
		currentPrice, ok := ctx.CurrentPrices[symbol]
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("No current price available")
			continue
		}

		// Calculate quantity
		targetValue := maxValuePerPosition
		if targetValue > ctx.AvailableCashEUR {
			targetValue = ctx.AvailableCashEUR
		}

		quantity := int(targetValue / currentPrice)
		if quantity == 0 {
			quantity = 1
		}

		// Calculate value
		valueEUR := float64(quantity) * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		totalCostEUR := valueEUR + transactionCost

		// Check if we have enough cash
		if totalCostEUR > ctx.AvailableCashEUR {
			continue
		}

		// Priority based on underweight and score
		priority := scored.underweight * scored.score * 0.6

		// Build reason
		reason := fmt.Sprintf("Rebalance: %s underweight by %.1f%% (score: %.2f)",
			scored.group, scored.underweight*100, scored.score)

		// Build tags
		tags := []string{"rebalance", "buy", "underweight"}

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
		Int("underweight_countries", len(underweightCountries)).
		Msg("Rebalance buy opportunities identified")

	return candidates, nil
}

func init() {
	// Auto-register on import
	DefaultCalculatorRegistry.Register(NewRebalanceBuysCalculator(zerolog.Nop()))
}
