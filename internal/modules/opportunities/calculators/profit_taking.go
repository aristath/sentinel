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
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minGainThreshold := GetFloatParam(params, "min_gain_threshold", 0.15)  // 15% minimum gain
	windfallThreshold := GetFloatParam(params, "windfall_threshold", 0.30) // 30% for windfall
	minHoldDays := GetIntParam(params, "min_hold_days", 90)                // Minimum holding period
	sellPercentage := GetFloatParam(params, "sell_percentage", 1.0)        // Sell 100% by default
	maxSellPercentage := GetFloatParam(params, "max_sell_percentage", 1.0) // Risk management cap (from config)
	maxPositions := GetIntParam(params, "max_positions", 0)                // 0 = unlimited

	if !ctx.AllowSell {
		c.log.Debug().Msg("Selling not allowed, skipping profit taking")
		return nil, nil
	}

	if len(ctx.Positions) == 0 {
		c.log.Debug().Msg("No positions available for profit taking")
		return nil, nil
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
			return nil, fmt.Errorf("failed to get tag-based sell candidates: %w", err)
		}

		if len(candidateSymbols) == 0 {
			c.log.Debug().Msg("No tag-based sell candidates found")
			return nil, nil
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

	for _, position := range ctx.Positions {
		// Skip if not in tag-filtered candidates (when tag filtering enabled)
		if candidateMap != nil && !candidateMap[position.Symbol] {
			continue
		}

		// Use ISIN if available, otherwise fallback to symbol
		isin := position.ISIN
		if isin == "" {
			isin = position.Symbol // Fallback for CASH positions
		}

		// Skip if ineligible
		if ctx.IneligibleSymbols[position.Symbol] {
			continue
		}

		// Skip if recently sold
		if ctx.RecentlySold[position.Symbol] {
			continue
		}

		// Get security info (try ISIN first, fallback to symbol)
		security, ok := ctx.GetSecurityByISINOrSymbol(isin, position.Symbol)
		if !ok {
			continue
		}

		// Check per-security constraint: AllowSell must be true
		if !security.AllowSell {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Msg("Skipping security: allow_sell=false")
			continue
		}

		// Get current price (try ISIN first, fallback to symbol)
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, position.Symbol)
		if !ok || currentPrice <= 0 {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Str("isin", isin).
				Msg("No current price available, skipping")
			continue
		}

		// Calculate gain
		costBasis := position.AverageCost
		if costBasis <= 0 {
			continue
		}

		gainPercent := (currentPrice - costBasis) / costBasis

		// Check if gain meets threshold
		if gainPercent < minGainThreshold {
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
		quantityInt = RoundToLotSize(quantityInt, security.MinLot)
		if quantityInt <= 0 {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Int("min_lot", security.MinLot).
				Msg("Skipping security: quantity below minimum lot size after rounding")
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
	logMsg.Msg("Profit-taking opportunities identified")

	return candidates, nil
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
