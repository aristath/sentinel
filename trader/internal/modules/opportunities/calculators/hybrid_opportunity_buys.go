package calculators

import (
	"fmt"
	"math"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// TagFilter is an interface for tag-based filtering to avoid import cycles.
type TagFilter interface {
	GetOpportunityCandidates(ctx *domain.OpportunityContext) ([]string, error)
	GetSellCandidates(ctx *domain.OpportunityContext) ([]string, error)
}

// HybridOpportunityBuysCalculator identifies buying opportunities using tag-based pre-filtering
// followed by focused calculations on the filtered candidate set.
// This provides 5-7x performance improvement over scanning all securities.
type HybridOpportunityBuysCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo *universe.SecurityRepository
}

// NewHybridOpportunityBuysCalculator creates a new hybrid opportunity buys calculator.
func NewHybridOpportunityBuysCalculator(
	tagFilter TagFilter,
	securityRepo *universe.SecurityRepository,
	log zerolog.Logger,
) *HybridOpportunityBuysCalculator {
	return &HybridOpportunityBuysCalculator{
		BaseCalculator: NewBaseCalculator(log, "hybrid_opportunity_buys"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *HybridOpportunityBuysCalculator) Name() string {
	return "hybrid_opportunity_buys"
}

// Category returns the opportunity category.
func (c *HybridOpportunityBuysCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryOpportunityBuys
}

// Calculate identifies opportunity buy candidates using tag-based pre-filtering.
func (c *HybridOpportunityBuysCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minScore := GetFloatParam(params, "min_score", 0.7)
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	maxPositions := GetIntParam(params, "max_positions", 5)
	excludeExisting := GetBoolParam(params, "exclude_existing", false)

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping hybrid opportunity buys")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= minTradeAmount {
		c.log.Debug().
			Float64("available_cash", ctx.AvailableCashEUR).
			Float64("min_trade_amount", minTradeAmount).
			Msg("Insufficient cash for opportunity buys (below minimum trade amount)")
		return nil, nil
	}

	// Step 1: Fast tag-based pre-filtering (10-50ms)
	candidateSymbols, err := c.tagFilter.GetOpportunityCandidates(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get tag-based candidates: %w", err)
	}

	if len(candidateSymbols) == 0 {
		c.log.Debug().Msg("No tag-based candidates found")
		return nil, nil
	}

	c.log.Debug().
		Int("tag_candidates", len(candidateSymbols)).
		Msg("Tag-based pre-filtering complete")

	// Check which positions we already have
	existingPositions := make(map[string]bool)
	for _, position := range ctx.Positions {
		existingPositions[position.Symbol] = true
	}

	// Step 2: Focused calculations on filtered set (100-500ms vs 2-5s)
	var candidates []domain.ActionCandidate

	for _, symbol := range candidateSymbols {
		// Skip if we already have this position and exclude_existing is true
		if excludeExisting && existingPositions[symbol] {
			continue
		}

		// Skip if recently bought
		if ctx.RecentlyBought[symbol] {
			continue
		}

		// Get security info
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Debug().
				Str("symbol", symbol).
				Msg("Security not found in stocks map, skipping")
			continue
		}

		// Use ISIN if available, otherwise fallback to symbol
		isin := security.ISIN
		if isin == "" {
			isin = symbol
		}

		// Get current price
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, symbol)
		if !ok || currentPrice <= 0 {
			c.log.Debug().
				Str("symbol", symbol).
				Msg("No current price available, skipping")
			continue
		}

		// Get score (already calculated, just lookup)
		score, ok := ctx.SecurityScores[symbol]
		if !ok || score < minScore {
			continue
		}

		// Apply target return filtering with absolute minimum guardrail (if CAGR data available)
		// Get target return and threshold (defaults: 11% target, 80% threshold = 8.8% minimum)
		targetReturn := ctx.TargetReturn
		if targetReturn == 0 {
			targetReturn = 0.11 // Default 11%
		}
		thresholdPct := ctx.TargetReturnThresholdPct
		if thresholdPct == 0 {
			thresholdPct = 0.80 // Default 80%
		}

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

		// Apply absolute minimum guardrail (hard filter) - only if CAGR data is available
		if cagr != nil && *cagr < absoluteMinCAGR {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Float64("cagr", *cagr).
				Float64("absolute_min", absoluteMinCAGR).
				Msg("Filtered out: below absolute minimum CAGR (hard filter)")
			continue
		}

		// Quality gate: Exclude value traps and bubble risks
		securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
		if err == nil {
			// Skip value traps
			if contains(securityTags, "value-trap") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping value trap")
				continue
			}

			// Skip bubble risks (unless it's quality-high-cagr)
			if contains(securityTags, "bubble-risk") && !contains(securityTags, "quality-high-cagr") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping bubble risk")
				continue
			}

			// Require quality gate pass for new positions
			if !existingPositions[symbol] && !contains(securityTags, "quality-gate-pass") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - quality gate failed")
				continue
			}
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

		// Check if trade meets minimum trade amount (transaction cost efficiency)
		if valueEUR < minTradeAmount {
			c.log.Debug().
				Str("symbol", symbol).
				Float64("trade_value", valueEUR).
				Float64("min_trade_amount", minTradeAmount).
				Msg("Skipping trade below minimum trade amount")
			continue
		}

		// Check if we have enough cash
		if totalCostEUR > ctx.AvailableCashEUR {
			continue
		}

		// Calculate priority with tag-based boosting
		priority := c.calculatePriority(score, securityTags)

		// Build reason
		reason := fmt.Sprintf("Tag-filtered opportunity: score %.2f", score)
		if len(securityTags) > 0 {
			reason += fmt.Sprintf(" (tags: %v)", securityTags[:min(3, len(securityTags))])
		}

		// Build candidate tags
		candidateTags := []string{"opportunity_buy", "hybrid_filtered"}
		if !existingPositions[symbol] {
			candidateTags = append(candidateTags, "new_position")
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
			Tags:     candidateTags,
		}

		candidates = append(candidates, candidate)
	}

	// Step 3: Sort by priority descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Priority > candidates[j].Priority
	})

	// Step 4: Limit to top N
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("filtered_from", len(candidateSymbols)).
		Msg("Hybrid opportunity buys calculated")

	return candidates, nil
}

// calculatePriority intelligently boosts priority based on tag combinations.
// Enhanced tags provide additional priority boosts.
func (c *HybridOpportunityBuysCalculator) calculatePriority(
	score float64,
	tags []string,
) float64 {
	priority := score

	// High-quality value opportunities get significant boost (enhanced tag)
	if contains(tags, "quality-value") {
		priority *= 1.4
	} else if contains(tags, "high-quality") && contains(tags, "value-opportunity") {
		priority *= 1.3
	}

	// Deep value gets boost
	if contains(tags, "deep-value") {
		priority *= 1.2
	}

	// Oversold high-quality gets boost
	if contains(tags, "oversold") && contains(tags, "high-quality") {
		priority *= 1.15
	}

	// Excellent total return gets boost (enhanced tag)
	if contains(tags, "excellent-total-return") {
		priority *= 1.25
	} else if contains(tags, "high-total-return") {
		priority *= 1.15
	}

	// Quality high CAGR gets boost (enhanced tag)
	if contains(tags, "quality-high-cagr") {
		priority *= 1.2
	}

	// Recovery candidates get moderate boost
	if contains(tags, "recovery-candidate") {
		priority *= 1.1
	}

	// Dividend opportunities get boost
	if contains(tags, "dividend-grower") {
		priority *= 1.15
	} else if contains(tags, "high-dividend") {
		priority *= 1.1
	}

	// Cap at 1.0
	return math.Min(1.0, priority)
}

// contains checks if a string slice contains a value.
func contains(slice []string, value string) bool {
	for _, v := range slice {
		if v == value {
			return true
		}
	}
	return false
}

// min returns the minimum of two integers.
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
