package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// HybridAveragingDownCalculator identifies averaging-down opportunities using tag-based pre-filtering.
// It uses quality gates to ensure we only average down on quality positions, and excludes value traps.
type HybridAveragingDownCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo *universe.SecurityRepository
}

// NewHybridAveragingDownCalculator creates a new hybrid averaging down calculator.
func NewHybridAveragingDownCalculator(
	tagFilter TagFilter,
	securityRepo *universe.SecurityRepository,
	log zerolog.Logger,
) *HybridAveragingDownCalculator {
	return &HybridAveragingDownCalculator{
		BaseCalculator: NewBaseCalculator(log, "hybrid_averaging_down"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *HybridAveragingDownCalculator) Name() string {
	return "hybrid_averaging_down"
}

// Category returns the opportunity category.
func (c *HybridAveragingDownCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryAveragingDown
}

// Calculate identifies averaging-down opportunities using tag-based pre-filtering.
func (c *HybridAveragingDownCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	maxLossPercent := GetFloatParam(params, "max_loss_percent", -0.20) // -20% maximum loss
	minLossPercent := GetFloatParam(params, "min_loss_percent", -0.05) // -5% minimum loss (must be down)
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	maxPositions := GetIntParam(params, "max_positions", 3) // Default to top 3

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping hybrid averaging down")
		return nil, nil
	}

	if len(ctx.Positions) == 0 {
		c.log.Debug().Msg("No positions available for averaging down")
		return nil, nil
	}

	// Step 1: Fast tag-based pre-filtering for averaging-down opportunities
	// We want: recovery-candidate, value-opportunity, quality-gate-pass, quality-value
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

	// Build a map of candidate symbols for fast lookup
	candidateMap := make(map[string]bool)
	for _, symbol := range candidateSymbols {
		candidateMap[symbol] = true
	}

	// Step 2: Focused calculations on filtered set (only positions with tags AND losses)
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

		// Skip if recently bought
		if ctx.RecentlyBought[position.Symbol] {
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

		// Calculate loss
		costBasis := position.AverageCost
		if costBasis <= 0 {
			continue
		}

		lossPercent := (currentPrice - costBasis) / costBasis

		// CRITICAL: Only average down on positions with losses
		// Must be between minLossPercent and maxLossPercent
		if lossPercent >= 0 || lossPercent < maxLossPercent || lossPercent > minLossPercent {
			continue
		}

		// Get tags for this security
		securityTags, err := c.securityRepo.GetTagsForSecurity(position.Symbol)
		if err != nil {
			// Log but continue - tags are optional
			c.log.Debug().
				Str("symbol", position.Symbol).
				Err(err).
				Msg("Failed to get tags for security")
			securityTags = []string{}
		}

		// CRITICAL: Exclude value traps
		if contains(securityTags, "value-trap") {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Msg("Skipping value trap")
			continue
		}

		// CRITICAL: Require quality gate pass
		if !contains(securityTags, "quality-gate-pass") {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Msg("Skipping - quality gate failed")
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

		// Check if trade meets minimum trade amount (transaction cost efficiency)
		if valueEUR < minTradeAmount {
			c.log.Debug().
				Str("symbol", position.Symbol).
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
		priority := c.calculatePriority(lossPercent, securityTags)

		// Build reason
		reason := fmt.Sprintf("Averaging down: %.1f%% loss (cost basis: %.2f, current: %.2f)",
			lossPercent*100, costBasis, currentPrice)

		// Add tag-based reasons
		if contains(securityTags, "quality-value") {
			reason += " [Quality Value]"
		} else if contains(securityTags, "recovery-candidate") {
			reason += " [Recovery Candidate]"
		}

		// Build tags
		tags := []string{"averaging_down", "hybrid_filtered"}
		if contains(securityTags, "quality-value") {
			tags = append(tags, "quality_value")
		}
		if contains(securityTags, "recovery-candidate") {
			tags = append(tags, "recovery_candidate")
		}

		candidate := domain.ActionCandidate{
			Side:     "BUY",
			Symbol:   position.Symbol,
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
		Msg("Hybrid averaging-down opportunities calculated")

	return candidates, nil
}

// calculatePriority intelligently boosts priority based on loss and tags.
// More negative loss (deeper discount) and quality tags increase priority.
func (c *HybridAveragingDownCalculator) calculatePriority(
	lossPercent float64,
	tags []string,
) float64 {
	// Base priority is inverse of loss (more negative = higher priority)
	// Convert loss to positive scale: -0.20 loss = 0.20 priority, -0.05 loss = 0.05 priority
	priority := -lossPercent

	// Quality value gets significant boost
	if contains(tags, "quality-value") {
		priority *= 1.5
	}

	// Recovery candidate gets boost
	if contains(tags, "recovery-candidate") {
		priority *= 1.3
	}

	// Quality gate pass gets moderate boost
	if contains(tags, "quality-gate-pass") {
		priority *= 1.2
	}

	// High quality gets boost
	if contains(tags, "high-quality") {
		priority *= 1.15
	}

	// Value opportunity gets small boost
	if contains(tags, "value-opportunity") {
		priority *= 1.1
	}

	return priority
}
