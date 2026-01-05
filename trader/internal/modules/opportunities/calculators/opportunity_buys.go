package calculators

import (
	"fmt"
	"math"
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
	minScore := GetFloatParam(params, "min_score", 0.7) // Minimum score threshold
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	minValuePerPosition := GetFloatParam(params, "min_value_per_position", 100.0)
	maxPositions := GetIntParam(params, "max_positions", 5)            // Default to top 5
	excludeExisting := GetBoolParam(params, "exclude_existing", false) // Exclude positions we already have

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping opportunity buys")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= minValuePerPosition {
		c.log.Debug().Msg("Insufficient cash for opportunity buys")
		return nil, nil
	}

	if len(ctx.SecurityScores) == 0 {
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

		// Get security info (try ISIN first, fallback to symbol)
		// SecurityScores uses symbol as key, so we look up by symbol first
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("Security not found in stocks map")
			continue
		}

		// Use ISIN if available, otherwise fallback to symbol
		isin := security.ISIN
		if isin == "" {
			isin = symbol // Fallback for CASH positions or securities without ISIN
		}

		// Apply target return filtering with flexible penalty system (if data available)
		// Get target return and threshold (defaults: 11% target, 80% threshold = 8.8% minimum)
		targetReturn := ctx.TargetReturn
		if targetReturn == 0 {
			targetReturn = 0.11 // Default 11%
		}
		thresholdPct := ctx.TargetReturnThresholdPct
		if thresholdPct == 0 {
			thresholdPct = 0.80 // Default 80%
		}
		minCAGRThreshold := targetReturn * thresholdPct

		// Absolute minimum guardrail: Never allow below 6% CAGR or 50% of target (whichever is higher)
		absoluteMinCAGR := math.Max(0.06, targetReturn*0.50)

		// Get CAGR if available (try ISIN first, fallback to symbol)
		var cagr *float64
		if ctx.CAGRs != nil {
			if cagrVal, ok := ctx.CAGRs[isin]; ok {
				cagr = &cagrVal
			} else if cagrVal, ok := ctx.CAGRs[symbol]; ok {
				cagr = &cagrVal
			}
		}

		// Apply absolute minimum guardrail (hard filter)
		if cagr != nil && *cagr < absoluteMinCAGR {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Float64("cagr", *cagr).
				Float64("absolute_min", absoluteMinCAGR).
				Msg("Filtered out: below absolute minimum CAGR (hard filter)")
			continue
		}

		// Apply flexible penalty if below threshold (if CAGR available)
		penalty := 0.0
		if cagr != nil && *cagr < minCAGRThreshold {
			// Calculate penalty based on how far below threshold
			// Penalty increases as CAGR gets further below threshold
			// Max penalty: 30% reduction
			shortfallRatio := (minCAGRThreshold - *cagr) / minCAGRThreshold
			penalty = math.Min(0.3, shortfallRatio*0.5) // Up to 30% penalty

			// Quality override: Get quality scores for penalty reduction
			var longTermScore, fundamentalsScore *float64
			if ctx.LongTermScores != nil {
				if lt, ok := ctx.LongTermScores[isin]; ok {
					longTermScore = &lt
				} else if lt, ok := ctx.LongTermScores[symbol]; ok {
					longTermScore = &lt
				}
			}
			if ctx.FundamentalsScores != nil {
				if fund, ok := ctx.FundamentalsScores[isin]; ok {
					fundamentalsScore = &fund
				} else if fund, ok := ctx.FundamentalsScores[symbol]; ok {
					fundamentalsScore = &fund
				}
			}

			// Calculate quality score for override
			qualityScore := 0.0
			if longTermScore != nil && fundamentalsScore != nil {
				qualityScore = (*longTermScore + *fundamentalsScore) / 2.0
			} else if longTermScore != nil {
				qualityScore = *longTermScore
			} else if fundamentalsScore != nil {
				qualityScore = *fundamentalsScore
			}

			// Apply quality override: Only exceptional quality gets significant reduction
			if qualityScore > 0.80 {
				penalty *= 0.65 // Reduce penalty by 35% for exceptional quality (0.80+)
			} else if qualityScore > 0.75 {
				penalty *= 0.80 // Reduce penalty by 20% for high quality (0.75-0.80)
			}
			// Quality below 0.75 gets no override (full penalty applies)

			// Apply penalty to score
			score = score * (1.0 - penalty)

			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Float64("cagr", *cagr).
				Float64("min_threshold", minCAGRThreshold).
				Float64("penalty", penalty).
				Float64("quality_score", qualityScore).
				Float64("score_before_penalty", scored.score).
				Float64("score_after_penalty", score).
				Msg("Applied flexible penalty (quality-aware)")
		}

		// Get current price (try ISIN first, fallback to symbol)
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, symbol)
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
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
