package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ProfitTakingCalculator identifies opportunities to take profits from positions with gains.
// Supports optional tag-based pre-filtering for performance when EnableTagFiltering=true.
type ProfitTakingCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo SecurityRepository
}

// NewProfitTakingCalculator creates a new profit taking calculator.
func NewProfitTakingCalculator(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *ProfitTakingCalculator {
	return &ProfitTakingCalculator{
		BaseCalculator: NewBaseCalculator(log, "profit_taking"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *ProfitTakingCalculator) Name() string {
	return "profit_taking"
}

// Category returns the opportunity category.
func (c *ProfitTakingCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryProfitTaking
}

// Calculate identifies profit-taking opportunities.
func (c *ProfitTakingCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) (domain.CalculatorResult, error) {
	// Parameters with defaults
	minGainThreshold := GetFloatParam(params, "min_gain_threshold", 0.15)  // 15% minimum gain
	windfallThreshold := GetFloatParam(params, "windfall_threshold", 0.30) // 30% for windfall
	minHoldDays := GetIntParam(params, "min_hold_days", 90)                // Minimum holding period
	sellPercentage := GetFloatParam(params, "sell_percentage", 1.0)        // Sell 100% by default
	maxSellPercentage := GetFloatParam(params, "max_sell_percentage", 1.0) // Risk management cap (from config)
	maxPositions := GetIntParam(params, "max_positions", 0)                // 0 = unlimited
	_ = minHoldDays                                                        // Reserved for future use

	// Initialize exclusion collector
	exclusions := NewExclusionCollector(c.Name(), ctx.DismissedFilters)

	if !ctx.AllowSell {
		c.log.Debug().Msg("Selling not allowed, skipping profit taking")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	if len(ctx.EnrichedPositions) == 0 {
		c.log.Debug().Msg("No positions available for profit taking")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	// Extract config for tag filtering
	var config *domain.PlannerConfiguration
	if cfg, ok := params["config"].(*domain.PlannerConfiguration); ok && cfg != nil {
		config = cfg
	} else {
		config = domain.NewDefaultConfiguration()
	}

	// Tag-based pre-filtering (when enabled)
	var candidateMap map[string]bool
	if config.EnableTagFiltering && c.tagFilter != nil {
		candidateSymbols, err := c.tagFilter.GetSellCandidates(ctx, config)
		if err != nil {
			return domain.CalculatorResult{PreFiltered: exclusions.Result()}, fmt.Errorf("failed to get tag-based sell candidates: %w", err)
		}

		if len(candidateSymbols) == 0 {
			c.log.Debug().Msg("No tag-based sell candidates found")
			return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
		}

		// Build lookup map
		candidateMap = make(map[string]bool)
		for _, symbol := range candidateSymbols {
			candidateMap[symbol] = true
		}

		c.log.Debug().
			Int("tag_candidates", len(candidateSymbols)).
			Msg("Tag-based pre-filtering complete")
	}

	var candidates []domain.ActionCandidate

	c.log.Debug().
		Float64("min_gain_threshold", minGainThreshold).
		Float64("windfall_threshold", windfallThreshold).
		Int("min_hold_days", minHoldDays).
		Bool("tag_filtering_enabled", config.EnableTagFiltering).
		Msg("Calculating profit-taking opportunities")

	for _, position := range ctx.EnrichedPositions {
		isin := position.ISIN
		symbol := position.Symbol
		securityName := position.SecurityName

		// Skip if not in tag-filtered candidates (when tag filtering enabled)
		if candidateMap != nil && !candidateMap[symbol] {
			exclusions.Add(isin, symbol, securityName, "no matching sell tags")
			continue
		}

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

		// Current price embedded in position (no lookup needed)
		currentPrice := position.CurrentPrice
		if currentPrice <= 0 {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available, skipping")
			exclusions.Add(isin, symbol, securityName, "no current price available")
			continue
		}

		// Calculate gain using embedded helper (no map lookups)
		costBasis := position.AverageCost
		if costBasis <= 0 {
			exclusions.Add(isin, symbol, securityName, "no cost basis available")
			continue
		}

		gainPercent := position.GainPercent()

		// Check if gain meets threshold
		if gainPercent < minGainThreshold {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("gain %.1f%% below threshold %.1f%%", gainPercent*100, minGainThreshold*100))
			continue
		}

		// Determine if windfall
		isWindfall := gainPercent >= windfallThreshold

		// Calculate quantity to sell
		// Apply both sellPercentage (strategy) and maxSellPercentage (risk management cap)
		// The effective percentage is the minimum of the two
		effectiveSellPct := sellPercentage
		if maxSellPercentage < effectiveSellPct {
			effectiveSellPct = maxSellPercentage
		}

		quantity := position.Quantity * effectiveSellPct
		if quantity == 0 {
			quantity = 1
		}

		// Round quantity to lot size and validate
		quantityInt := int(quantity)
		quantityInt = RoundToLotSize(quantityInt, position.MinLot)
		if quantityInt <= 0 {
			c.log.Debug().
				Str("symbol", symbol).
				Int("min_lot", position.MinLot).
				Msg("Skipping security: quantity below minimum lot size after rounding")
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quantity below minimum lot size %d", position.MinLot))
			continue
		}
		quantity = float64(quantityInt)

		// Calculate value
		valueEUR := quantity * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		netValueEUR := valueEUR - transactionCost

		// Get security tags for priority boosting and reason enhancement
		var securityTags []string
		if config.EnableTagFiltering && c.securityRepo != nil {
			tags, err := c.securityRepo.GetTagsForSecurity(position.Symbol)
			if err == nil && len(tags) > 0 {
				securityTags = tags
			}
		}

		// Calculate priority with tag-based boosting
		priority := c.calculatePriority(gainPercent, isWindfall, securityTags, config)

		// Apply tag-based priority boosts (with regime-aware logic, sell calculator - no quantum penalty)
		if config.EnableTagFiltering && len(securityTags) > 0 {
			priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "profit_taking", c.securityRepo)
		}

		// Build reason
		reason := fmt.Sprintf("%.1f%% gain (cost basis: %.2f, current: %.2f)",
			gainPercent*100, costBasis, currentPrice)

		if isWindfall {
			reason = fmt.Sprintf("Windfall: %s", reason)
		}

		// Add tag-based reason enhancements
		if contains(securityTags, "bubble-risk") {
			reason += " [Bubble Risk]"
		}
		if contains(securityTags, "needs-rebalance") {
			reason += " [Needs Rebalance]"
		}
		if contains(securityTags, "overweight") {
			reason += " [Overweight]"
		}

		// Build tags
		tags := []string{"profit_taking"}
		if isWindfall {
			tags = append(tags, "windfall")
		}
		if contains(securityTags, "bubble-risk") {
			tags = append(tags, "bubble_risk")
		}
		if contains(securityTags, "needs-rebalance") {
			tags = append(tags, "rebalance")
		}

		candidate := domain.ActionCandidate{
			Side:     "SELL",
			ISIN:     isin,         // PRIMARY identifier ✅
			Symbol:   symbol,       // BOUNDARY identifier
			Name:     securityName, // Embedded security metadata
			Quantity: int(quantity),
			Price:    currentPrice,
			ValueEUR: netValueEUR,
			Currency: position.Currency, // Embedded from position
			Priority: priority,
			Reason:   reason,
			Tags:     tags,
		}

		candidates = append(candidates, candidate)
	}

	// Sort by priority descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Priority > candidates[j].Priority
	})

	// Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	logMsg := c.log.Info().Int("candidates", len(candidates))
	if candidateMap != nil {
		logMsg = logMsg.Int("filtered_from", len(candidateMap))
	}
	logMsg.Int("pre_filtered", len(exclusions.Result())).Msg("Profit-taking opportunities identified")

	return domain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}

// calculatePriority calculates priority with optional tag-based boosting.
func (c *ProfitTakingCalculator) calculatePriority(
	gainPercent float64,
	isWindfall bool,
	securityTags []string,
	config *domain.PlannerConfiguration,
) float64 {
	priority := gainPercent

	// Windfall gets extra priority boost
	if isWindfall {
		priority *= 1.5
	}

	// Apply tag-based boosts only when tag filtering is enabled and tags are available
	if config == nil || !config.EnableTagFiltering || len(securityTags) == 0 {
		return priority
	}

	// Bubble risk gets significant boost (sell before it pops)
	if contains(securityTags, "bubble-risk") {
		priority *= 1.4
	}

	// Needs rebalance gets boost (optimizer alignment)
	if contains(securityTags, "needs-rebalance") {
		priority *= 1.3
	}

	// Overweight gets moderate boost
	if contains(securityTags, "overweight") || contains(securityTags, "concentration-risk") {
		priority *= 1.2
	}

	// Overvalued gets moderate boost
	if contains(securityTags, "overvalued") {
		priority *= 1.15
	}

	// Near 52-week high gets small boost
	if contains(securityTags, "near-52w-high") {
		priority *= 1.1
	}

	return priority
}
