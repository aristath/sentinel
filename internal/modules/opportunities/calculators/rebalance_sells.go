package calculators

import (
	"fmt"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
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
	maxSellPercentage := GetFloatParam(params, "max_sell_percentage", 0.50)           // Risk management cap (default 50%)
	maxPositions := GetIntParam(params, "max_positions", 0)                           // 0 = unlimited

	// Initialize exclusion collector
	exclusions := NewExclusionCollector(c.Name(), ctx.DismissedFilters)

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

	// Check if we have country allocations and weights
	if ctx.CountryAllocations == nil || ctx.CountryWeights == nil {
		c.log.Debug().Msg("No country allocation data available")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	if ctx.TotalPortfolioValueEUR <= 0 {
		c.log.Debug().Msg("Invalid portfolio value")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	c.log.Debug().
		Float64("min_overweight_threshold", minOverweightThreshold).
		Msg("Calculating rebalance sells")

	// Identify overweight countries
	overweightCountries := make(map[string]float64)
	for country, currentAllocation := range ctx.CountryAllocations {
		targetAllocation, ok := ctx.CountryWeights[country]
		if !ok {
			targetAllocation = 0.0
		}

		overweight := currentAllocation - targetAllocation
		if overweight > minOverweightThreshold {
			overweightCountries[country] = overweight
			c.log.Debug().
				Str("country", country).
				Float64("current", currentAllocation).
				Float64("target", targetAllocation).
				Float64("overweight", overweight).
				Msg("Overweight country identified")
		}
	}

	if len(overweightCountries) == 0 {
		c.log.Debug().Msg("No overweight countries")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	var candidates []domain.ActionCandidate

	for _, position := range ctx.EnrichedPositions {
		isin := position.ISIN
		symbol := position.Symbol
		securityName := position.SecurityName

		// Skip if ineligible (ISIN lookup)
		if ctx.IneligibleISINs[isin] { // ISIN key ✅
			exclusions.Add(isin, symbol, securityName, "marked as ineligible")
			continue
		}

		// Skip if recently sold (ISIN lookup)
		if ctx.RecentlySoldISINs[isin] { // ISIN key ✅
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

		// Get country from embedded security metadata
		country := position.Country
		if country == "" {
			exclusions.Add(isin, symbol, securityName, "no country assigned")
			continue
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

		// Check if this group is overweight
		overweight, ok := overweightCountries[group]
		if !ok {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("country group %s is not overweight", group))
			continue
		}

		// Current price embedded in position (no lookup needed)
		currentPrice := position.CurrentPrice
		if currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available")
			exclusions.Add(isin, symbol, securityName, "no current price available")
			continue
		}

		// Calculate how much to sell (proportional to overweight)
		// Start with proportional amount based on how overweight we are
		sellPercentage := overweight / (overweight + minOverweightThreshold)

		// Cap at maxSellPercentage (risk management limit)
		if sellPercentage > maxSellPercentage {
			sellPercentage = maxSellPercentage
		}

		quantity := int(float64(position.Quantity) * sellPercentage)
		if quantity == 0 {
			quantity = 1
		}

		// Round quantity to lot size and validate
		quantity = RoundToLotSize(quantity, position.MinLot)
		if quantity <= 0 {
			c.log.Debug().
				Str("symbol", symbol).
				Int("min_lot", position.MinLot).
				Msg("Skipping security: quantity below minimum lot size after rounding")
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quantity below minimum lot size %d", position.MinLot))
			continue
		}

		// Calculate value
		valueEUR := float64(quantity) * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		netValueEUR := valueEUR - transactionCost

		// Priority based on how overweight the country is
		priority := overweight * 0.5 // Lower priority than profit-taking

		// Apply tag-based priority boosts (with regime-aware logic, sell calculator - no quantum penalty)
		if config.EnableTagFiltering && c.securityRepo != nil {
			securityTags, err := c.securityRepo.GetTagsForSecurity(position.Symbol)
			if err == nil && len(securityTags) > 0 {
				priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "rebalance_sells", c.securityRepo)
			}
		}

		// Build reason
		reason := fmt.Sprintf("Rebalance: %s overweight by %.1f%%",
			group, overweight*100)

		// Build tags
		tags := []string{"rebalance", "sell", "overweight"}

		candidate := domain.ActionCandidate{
			Side:     "SELL",
			ISIN:     isin,         // PRIMARY identifier ✅
			Symbol:   symbol,       // BOUNDARY identifier
			Name:     securityName, // Embedded security metadata
			Quantity: quantity,
			Price:    position.CurrentPrice,
			ValueEUR: netValueEUR,
			Currency: position.Currency, // Embedded from position
			Priority: priority,
			Reason:   reason,
			Tags:     tags,
		}

		candidates = append(candidates, candidate)
	}

	// Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("overweight_countries", len(overweightCountries)).
		Int("pre_filtered", len(exclusions.Result())).
		Msg("Rebalance sell opportunities identified")

	return domain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}
