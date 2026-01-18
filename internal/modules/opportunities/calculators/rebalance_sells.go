package calculators

import (
	"fmt"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// RebalanceSellsCalculator identifies overweight positions to sell for rebalancing.
// Supports optional tag-based filtering for performance when EnableTagFiltering=true.
type RebalanceSellsCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo SecurityRepository
}

// NewRebalanceSellsCalculator creates a new rebalance sells calculator.
func NewRebalanceSellsCalculator(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *RebalanceSellsCalculator {
	return &RebalanceSellsCalculator{
		BaseCalculator: NewBaseCalculator(log, "rebalance_sells"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *RebalanceSellsCalculator) Name() string {
	return "rebalance_sells"
}

// Category returns the opportunity category.
func (c *RebalanceSellsCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryRebalanceSells
}

// Calculate identifies rebalance sell opportunities.
func (c *RebalanceSellsCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) (domain.CalculatorResult, error) {
	// Parameters with defaults
	minOverweightThreshold := GetFloatParam(params, "min_overweight_threshold", 0.05) // 5% overweight
	maxSellPercentage := GetFloatParam(params, "max_sell_percentage", 0.20)           // Risk management cap (default 20% - matches config)
	maxPositions := GetIntParam(params, "max_positions", 0)                           // 0 = unlimited

	// Initialize exclusion collector
	exclusions := NewExclusionCollector(c.Name())

	// Extract config for tag filtering (will be used in Phase 4 for priority boosting)
	var config *domain.PlannerConfiguration
	if cfg, ok := params["config"].(*domain.PlannerConfiguration); ok && cfg != nil {
		config = cfg
	} else {
		config = domain.NewDefaultConfiguration()
	}

	if !ctx.AllowSell {
		c.log.Debug().Msg("Selling not allowed, skipping rebalance sells")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	// Check if we have geography allocations and weights
	if ctx.GeographyAllocations == nil || ctx.GeographyWeights == nil {
		c.log.Debug().Msg("No geography allocation data available")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	if ctx.TotalPortfolioValueEUR <= 0 {
		c.log.Debug().Msg("Invalid portfolio value")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	c.log.Debug().
		Float64("min_overweight_threshold", minOverweightThreshold).
		Msg("Calculating rebalance sells")

	// Identify overweight geographies
	overweightGeographies := make(map[string]float64)
	for geo, currentAllocation := range ctx.GeographyAllocations {
		targetAllocation, ok := ctx.GeographyWeights[geo]
		if !ok {
			targetAllocation = 0.0
		}

		overweight := currentAllocation - targetAllocation
		if overweight > minOverweightThreshold {
			overweightGeographies[geo] = overweight
			c.log.Debug().
				Str("geography", geo).
				Float64("current", currentAllocation).
				Float64("target", targetAllocation).
				Float64("overweight", overweight).
				Msg("Overweight geography identified")
		}
	}

	if len(overweightGeographies) == 0 {
		c.log.Debug().Msg("No overweight geographies")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	var candidates []domain.ActionCandidate

	// Group eligible positions by geography
	positionsByGeography := make(map[string][]domain.EnrichedPosition)

	for _, position := range ctx.EnrichedPositions {
		isin := position.ISIN
		symbol := position.Symbol
		securityName := position.SecurityName

		// Skip if ineligible (ISIN lookup)
		if ctx.IneligibleISINs[isin] {
			exclusions.Add(isin, symbol, securityName, "marked as ineligible")
			continue
		}

		// Skip if recently sold (ISIN lookup)
		if ctx.RecentlySoldISINs[isin] {
			exclusions.Add(isin, symbol, securityName, "recently sold (cooling off period)")
			continue
		}

		// Check per-security constraint: AllowSell embedded in position
		if !position.CanSell() {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("Skipping security: allow_sell=false or inactive")
			exclusions.Add(isin, symbol, securityName, "allow_sell=false or inactive")
			continue
		}

		// Get geography from embedded security metadata
		geography := position.Geography
		if geography == "" {
			exclusions.Add(isin, symbol, securityName, "no geography assigned")
			continue
		}

		// Current price check
		if position.CurrentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available")
			exclusions.Add(isin, symbol, securityName, "no current price available")
			continue
		}

		// Check if any of the position's geographies are overweight and group
		geos := utils.ParseCSV(geography)
		for _, geo := range geos {
			if _, ok := overweightGeographies[geo]; ok {
				positionsByGeography[geo] = append(positionsByGeography[geo], position)
			}
		}
	}

	// Process each overweight geography using the new sell plan calculation
	for geo, overweight := range overweightGeographies {
		positions := positionsByGeography[geo]
		if len(positions) == 0 {
			continue
		}

		// Calculate optimal sell plan for this geography
		sellPlan, err := CalculateGeographySellPlan(
			geo,
			overweight,
			positions,
			ctx,
			maxSellPercentage,
			c.securityRepo,
			config,
		)
		if err != nil {
			c.log.Error().Err(err).Str("geography", geo).Msg("Failed to calculate sell plan")
			continue
		}

		// Create candidates from the sell plan
		for _, posSell := range sellPlan.PositionSells {
			// Quality-based protection: check if position should be protected
			var securityTags []string
			if c.securityRepo != nil {
				tags, tagErr := c.securityRepo.GetTagsForSecurity(posSell.Symbol)
				if tagErr == nil {
					securityTags = tags
				}
			}

			qualityScore := CalculateSellQualityScore(ctx, posSell.ISIN, securityTags, config)

			// Protect high-quality positions unless really necessary (overweight > 20%)
			if qualityScore.IsHighQuality && overweight < 0.20 {
				c.log.Debug().
					Str("symbol", posSell.Symbol).
					Str("isin", posSell.ISIN).
					Float64("quality_score", qualityScore.QualityScore).
					Msg("Protected high-quality position from rebalance sell")
				exclusions.Add(posSell.ISIN, posSell.Symbol, posSell.Name, "protected high-quality position")
				continue
			}

			// Calculate net value after transaction costs
			valueEUR := posSell.SellValueEUR
			transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
			netValueEUR := valueEUR - transactionCost

			// Priority based on overweight and quality (low quality = higher priority)
			priority := overweight * 0.5 * posSell.QualityPriority

			// Apply tag-based priority boosts
			if config.EnableTagFiltering && len(securityTags) > 0 {
				priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "rebalance_sells", c.securityRepo)
			}

			// Find position for currency info
			var currency string
			var currentPrice float64
			for _, pos := range positions {
				if pos.ISIN == posSell.ISIN {
					currency = pos.Currency
					currentPrice = pos.CurrentPrice
					break
				}
			}

			// Build reason with quality info
			reason := fmt.Sprintf("Rebalance: %s overweight by %.1f%%", geo, overweight*100)
			if qualityScore.HasNegativeTags {
				reason += " [Low Quality]"
			}

			// Build tags
			tags := []string{"rebalance", "sell", "overweight"}
			if qualityScore.HasNegativeTags {
				tags = append(tags, "low_quality")
			}

			candidate := domain.ActionCandidate{
				Side:     "SELL",
				ISIN:     posSell.ISIN,
				Symbol:   posSell.Symbol,
				Name:     posSell.Name,
				Quantity: posSell.SellQuantity,
				Price:    currentPrice,
				ValueEUR: netValueEUR,
				Currency: currency,
				Priority: priority,
				Reason:   reason,
				Tags:     tags,
			}

			candidates = append(candidates, candidate)
		}
	}

	// Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("overweight_countries", len(overweightGeographies)).
		Int("pre_filtered", len(exclusions.Result())).
		Msg("Rebalance sell opportunities identified")

	return domain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}
