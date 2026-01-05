package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// HybridProfitTakingCalculator identifies profit-taking opportunities using tag-based pre-filtering.
// It uses enhanced tags like "needs-rebalance" and "bubble-risk" to identify sell candidates,
// then filters to only positions with gains.
type HybridProfitTakingCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo *universe.SecurityRepository
}

// NewHybridProfitTakingCalculator creates a new hybrid profit taking calculator.
func NewHybridProfitTakingCalculator(
	tagFilter TagFilter,
	securityRepo *universe.SecurityRepository,
	log zerolog.Logger,
) *HybridProfitTakingCalculator {
	return &HybridProfitTakingCalculator{
		BaseCalculator: NewBaseCalculator(log, "hybrid_profit_taking"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *HybridProfitTakingCalculator) Name() string {
	return "hybrid_profit_taking"
}

// Category returns the opportunity category.
func (c *HybridProfitTakingCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryProfitTaking
}

// Calculate identifies profit-taking opportunities using tag-based pre-filtering.
func (c *HybridProfitTakingCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minGainThreshold := GetFloatParam(params, "min_gain_threshold", 0.15)  // 15% minimum gain
	windfallThreshold := GetFloatParam(params, "windfall_threshold", 0.30) // 30% for windfall
	sellPercentage := GetFloatParam(params, "sell_percentage", 1.0)        // Sell 100% by default
	maxPositions := GetIntParam(params, "max_positions", 0)                // 0 = unlimited

	if !ctx.AllowSell {
		c.log.Debug().Msg("Selling not allowed, skipping hybrid profit taking")
		return nil, nil
	}

	if len(ctx.Positions) == 0 {
		c.log.Debug().Msg("No positions available for profit taking")
		return nil, nil
	}

	// Step 1: Fast tag-based pre-filtering (10-50ms)
	candidateSymbols, err := c.tagFilter.GetSellCandidates(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get tag-based sell candidates: %w", err)
	}

	if len(candidateSymbols) == 0 {
		c.log.Debug().Msg("No tag-based sell candidates found")
		return nil, nil
	}

	c.log.Debug().
		Int("tag_candidates", len(candidateSymbols)).
		Msg("Tag-based pre-filtering complete")

	// Build a map of candidate symbols for fast lookup
	candidateMap := make(map[string]bool)
	for _, symbol := range candidateSymbols {
		candidateMap[symbol] = true
	}

	// Step 2: Focused calculations on filtered set (only positions with sell tags AND gains)
	var candidates []domain.ActionCandidate

	for _, position := range ctx.Positions {
		// Skip if not in tag-filtered candidates
		if !candidateMap[position.Symbol] {
			continue
		}

		// Use ISIN if available, otherwise fallback to symbol
		isin := position.ISIN
		if isin == "" {
			isin = position.Symbol
		}

		// Skip if ineligible
		if ctx.IneligibleSymbols[position.Symbol] {
			continue
		}

		// Skip if recently sold
		if ctx.RecentlySold[position.Symbol] {
			continue
		}

		// Get security info
		security, ok := ctx.GetSecurityByISINOrSymbol(isin, position.Symbol)
		if !ok {
			continue
		}

		// Get current price
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, position.Symbol)
		if !ok || currentPrice <= 0 {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Msg("No current price available, skipping")
			continue
		}

		// Calculate gain
		costBasis := position.AverageCost
		if costBasis <= 0 {
			continue
		}

		gainPercent := (currentPrice - costBasis) / costBasis

		// CRITICAL: Only profit-taking - must have gains
		if gainPercent < minGainThreshold {
			continue
		}

		// Get tags for this security to boost priority
		securityTags, err := c.securityRepo.GetTagsForSecurity(position.Symbol)
		if err != nil {
			// Log but continue - tags are optional
			c.log.Debug().
				Str("symbol", position.Symbol).
				Err(err).
				Msg("Failed to get tags for security")
		}

		// Determine if windfall
		isWindfall := gainPercent >= windfallThreshold

		// Calculate quantity to sell
		quantity := position.Quantity
		if sellPercentage < 1.0 {
			quantity = position.Quantity * sellPercentage
			if quantity == 0 {
				quantity = 1
			}
		}

		// Calculate value
		valueEUR := quantity * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		netValueEUR := valueEUR - transactionCost

		// Calculate priority with tag-based boosting
		priority := c.calculatePriority(gainPercent, isWindfall, securityTags)

		// Build reason
		reason := fmt.Sprintf("%.1f%% gain (cost basis: %.2f, current: %.2f)",
			gainPercent*100, costBasis, currentPrice)

		if isWindfall {
			reason = fmt.Sprintf("Windfall: %s", reason)
		}

		// Add tag-based reasons
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
		tags := []string{"profit_taking", "hybrid_filtered"}
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
			Symbol:   position.Symbol,
			Name:     security.Name,
			Quantity: int(quantity),
			Price:    currentPrice,
			ValueEUR: netValueEUR,
			Currency: string(security.Currency),
			Priority: priority,
			Reason:   reason,
			Tags:     tags,
		}

		candidates = append(candidates, candidate)
	}

	// Step 3: Sort by priority descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Priority > candidates[j].Priority
	})

	// Step 4: Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("filtered_from", len(candidateSymbols)).
		Msg("Hybrid profit-taking opportunities calculated")

	return candidates, nil
}

// calculatePriority intelligently boosts priority based on gain, windfall status, and tags.
func (c *HybridProfitTakingCalculator) calculatePriority(
	gainPercent float64,
	isWindfall bool,
	tags []string,
) float64 {
	priority := gainPercent

	// Windfall gets extra priority boost
	if isWindfall {
		priority *= 1.5
	}

	// Bubble risk gets significant boost (sell before it pops)
	if contains(tags, "bubble-risk") {
		priority *= 1.4
	}

	// Needs rebalance gets boost (optimizer alignment)
	if contains(tags, "needs-rebalance") {
		priority *= 1.3
	}

	// Overweight gets moderate boost
	if contains(tags, "overweight") || contains(tags, "concentration-risk") {
		priority *= 1.2
	}

	// Overvalued gets moderate boost
	if contains(tags, "overvalued") {
		priority *= 1.15
	}

	// Near 52-week high gets small boost
	if contains(tags, "near-52w-high") {
		priority *= 1.1
	}

	return priority
}

