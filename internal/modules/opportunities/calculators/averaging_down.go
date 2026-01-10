package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// AveragingDownCalculator identifies opportunities to average down on losing positions.
// Supports optional tag-based pre-filtering for performance when EnableTagFiltering=true.
type AveragingDownCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo SecurityRepository
}

// NewAveragingDownCalculator creates a new averaging down calculator.
func NewAveragingDownCalculator(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *AveragingDownCalculator {
	return &AveragingDownCalculator{
		BaseCalculator: NewBaseCalculator(log, "averaging_down"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *AveragingDownCalculator) Name() string {
	return "averaging_down"
}

// Category returns the opportunity category.
func (c *AveragingDownCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryAveragingDown
}

// Calculate identifies averaging-down opportunities.
func (c *AveragingDownCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	maxLossThreshold := GetFloatParam(params, "max_loss_percent", -0.20) // -20% maximum loss
	minLossThreshold := GetFloatParam(params, "min_loss_percent", -0.05) // -5% minimum loss
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	avgDownPercent := GetFloatParam(params, "averaging_down_percent", 0.10) // 10% of position (configurable)
	maxPositions := GetIntParam(params, "max_positions", 3)

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01)
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping averaging down")
		return nil, nil
	}

	if len(ctx.Positions) == 0 {
		c.log.Debug().Msg("No positions available for averaging down")
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
		candidateSymbols, err := c.tagFilter.GetOpportunityCandidates(ctx, config)
		if err != nil {
			return nil, fmt.Errorf("failed to get tag-based candidates: %w", err)
		}

		if len(candidateSymbols) == 0 {
			c.log.Debug().Msg("No tag-based candidates found")
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
		Float64("max_loss_threshold", maxLossThreshold).
		Float64("min_loss_threshold", minLossThreshold).
		Float64("averaging_down_percent", avgDownPercent).
		Bool("tag_filtering_enabled", config.EnableTagFiltering).
		Msg("Calculating averaging-down opportunities")

	for _, position := range ctx.Positions {
		// Skip if not in tag-filtered candidates (when tag filtering enabled)
		if candidateMap != nil && !candidateMap[position.Symbol] {
			continue
		}

		// Get ISIN for internal operations
		isin := position.ISIN
		if isin == "" {
			c.log.Warn().
				Str("symbol", position.Symbol).
				Msg("Position missing ISIN, skipping")
			continue
		}

		// Skip if recently bought (ISIN lookup)
		if ctx.RecentlyBoughtISINs[isin] { // ISIN key ✅
			continue
		}

		// Get security info (direct ISIN lookup)
		security, ok := ctx.StocksByISIN[isin] // ISIN key ✅
		if !ok {
			c.log.Debug().
				Str("isin", isin).
				Str("symbol", position.Symbol).
				Msg("Security not found in StocksByISIN, skipping")
			continue
		}

		// Check per-security constraint: AllowBuy must be true
		if !security.AllowBuy {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Str("isin", isin).
				Msg("Skipping security: allow_buy=false")
			continue
		}

		// Get current price (direct ISIN lookup)
		currentPrice, ok := ctx.CurrentPrices[isin] // ISIN key ✅
		if !ok || currentPrice <= 0 {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Str("isin", isin).
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
		// Must be between minLossThreshold and maxLossThreshold
		if lossPercent >= 0 || lossPercent < maxLossThreshold || lossPercent > minLossThreshold {
			continue
		}

		// Get security tags for quality gates and priority boosting
		var securityTags []string
		if config.EnableTagFiltering && c.securityRepo != nil {
			tags, err := c.securityRepo.GetTagsForSecurity(position.Symbol)
			if err == nil && len(tags) > 0 {
				securityTags = tags
			}
		}

		// Quality gates: tag-based when available, score-based fallback
		useTagChecks := len(securityTags) > 0 && config.EnableTagFiltering

		if useTagChecks {
			// Tag-based checks
			// CRITICAL: Exclude value traps (classical or ensemble)
			if contains(securityTags, "value-trap") || contains(securityTags, "ensemble-value-trap") {
				c.log.Debug().
					Str("symbol", position.Symbol).
					Msg("Skipping value trap (tag-based detection)")
				continue
			}

			// CRITICAL: Skip securities below absolute minimum return
			if contains(securityTags, "below-minimum-return") {
				c.log.Debug().
					Str("symbol", position.Symbol).
					Msg("Skipping - below absolute minimum return (tag-based filter)")
				continue
			}

			// CRITICAL: Skip if quality gate failed (inverted logic - cleaner)
			if contains(securityTags, "quality-gate-fail") {
				c.log.Debug().
					Str("symbol", position.Symbol).
					Msg("Skipping - quality gate failed (tag-based check)")
				continue
			}
		} else {
			// Score-based fallback
			qualityCheck := CheckQualityGates(ctx, position.ISIN, false, config)

			if qualityCheck.IsEnsembleValueTrap {
				c.log.Debug().
					Str("symbol", position.Symbol).
					Bool("classical", qualityCheck.IsValueTrap).
					Bool("quantum", qualityCheck.IsQuantumValueTrap).
					Float64("quantum_prob", qualityCheck.QuantumValueTrapProb).
					Msg("Skipping value trap (ensemble detection)")
				continue
			}

			if qualityCheck.BelowMinimumReturn {
				c.log.Debug().
					Str("symbol", position.Symbol).
					Msg("Skipping - below absolute minimum return (score-based filter)")
				continue
			}

			// For averaging down, we're less strict on quality (already in position)
			// Only skip if quality is very poor
			if qualityCheck.QualityGateReason == "quality_gate_fail" {
				fundamentalsScore := GetScoreFromContext(ctx, position.ISIN, ctx.FundamentalsScores)
				if fundamentalsScore > 0 && fundamentalsScore < 0.4 {
					c.log.Debug().
						Str("symbol", position.Symbol).
						Float64("fundamentals_score", fundamentalsScore).
						Msg("Skipping - extremely poor quality (score-based check)")
					continue
				}
			}
		}

		// Calculate quantity based on Kelly-optimal sizing (primary) or percentage (fallback)
		var quantity int

		// Primary strategy: Kelly-based (when available)
		if ctx.KellySizes != nil {
			if kellySize, hasKellySize := ctx.KellySizes[isin]; hasKellySize && kellySize > 0 { // ISIN key ✅
				kellyTargetValue := kellySize * ctx.TotalPortfolioValueEUR
				kellyTargetShares := kellyTargetValue / currentPrice
				currentShares := position.Quantity
				additionalShares := kellyTargetShares - currentShares

				if additionalShares > 0 {
					quantity = int(additionalShares)
					c.log.Debug().
						Str("symbol", position.Symbol).
						Str("isin", isin).
						Float64("kelly_target_shares", kellyTargetShares).
						Float64("current_shares", currentShares).
						Int("additional_shares", quantity).
						Msg("Using Kelly-based quantity calculation")
				} else {
					// Already at or above Kelly optimal - skip averaging down
					c.log.Debug().
						Str("symbol", position.Symbol).
						Str("isin", isin).
						Float64("kelly_target_shares", kellyTargetShares).
						Float64("current_shares", currentShares).
						Msg("Skipping - already at or above Kelly optimal")
					continue
				}
			}
		}

		// Fallback strategy: Percentage-based (when Kelly unavailable)
		if quantity == 0 {
			targetIncrease := position.Quantity * avgDownPercent
			if targetIncrease < 1 {
				targetIncrease = 1
			}
			quantity = int(targetIncrease)
			c.log.Debug().
				Str("symbol", position.Symbol).
				Float64("position_quantity", position.Quantity).
				Float64("averaging_down_percent", avgDownPercent).
				Int("quantity", quantity).
				Msg("Using percentage-based quantity calculation (Kelly unavailable)")
		}

		// Cap at maxValuePerPosition
		valueEUR := float64(quantity) * currentPrice
		if valueEUR > maxValuePerPosition {
			quantity = int(maxValuePerPosition / currentPrice)
			if quantity == 0 {
				quantity = 1
			}
			valueEUR = float64(quantity) * currentPrice
		}

		// Round quantity to lot size and validate
		quantityInt := quantity
		quantityInt = RoundToLotSize(quantityInt, security.MinLot)
		if quantityInt <= 0 {
			c.log.Debug().
				Str("symbol", position.Symbol).
				Int("min_lot", security.MinLot).
				Msg("Skipping security: quantity below minimum lot size after rounding")
			continue
		}
		quantity = quantityInt

		// Recalculate value after lot size rounding
		valueEUR = float64(quantity) * currentPrice

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
		priority := c.calculatePriority(lossPercent, securityTags, config)

		// Apply quantum warning penalty (10% for averaging down - already in position)
		if config.EnableTagFiltering && len(securityTags) > 0 {
			priority = ApplyQuantumWarningPenalty(priority, securityTags, "averaging_down")
		}

		// Apply tag-based priority boosts (with regime-aware logic)
		if config.EnableTagFiltering && len(securityTags) > 0 {
			priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "averaging_down", c.securityRepo)
		}

		// Build reason
		reason := fmt.Sprintf("Averaging down: %.1f%% loss (cost basis: %.2f, current: %.2f)",
			lossPercent*100, costBasis, currentPrice)

		// Add tag-based reason enhancements
		if contains(securityTags, "quality-value") {
			reason += " [Quality Value]"
		} else if contains(securityTags, "recovery-candidate") {
			reason += " [Recovery Candidate]"
		}

		// Build tags
		tags := []string{"averaging_down", "value_opportunity"}
		if contains(securityTags, "quality-value") {
			tags = append(tags, "quality_value")
		}
		if contains(securityTags, "recovery-candidate") {
			tags = append(tags, "recovery_candidate")
		}

		candidate := domain.ActionCandidate{
			Side:     "BUY",
			ISIN:     isin,            // PRIMARY identifier ✅
			Symbol:   position.Symbol, // BOUNDARY identifier
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
	logMsg.Msg("Averaging-down opportunities identified")

	return candidates, nil
}

// calculatePriority calculates priority with optional tag-based boosting.
// More negative loss (deeper discount) and quality tags increase priority.
func (c *AveragingDownCalculator) calculatePriority(
	lossPercent float64,
	securityTags []string,
	config *domain.PlannerConfiguration,
) float64 {
	// Base priority is inverse of loss (more negative = higher priority)
	// Convert loss to positive scale: -0.20 loss = 0.20 priority, -0.05 loss = 0.05 priority
	priority := -lossPercent

	// Apply tag-based boosts only when tag filtering is enabled and tags are available
	if config == nil || !config.EnableTagFiltering || len(securityTags) == 0 {
		return priority
	}

	// Quality value gets significant boost
	if contains(securityTags, "quality-value") {
		priority *= 1.5
	}

	// Recovery candidate gets boost
	if contains(securityTags, "recovery-candidate") {
		priority *= 1.3
	}

	// High quality gets boost
	if contains(securityTags, "high-quality") {
		priority *= 1.15
	}

	// Value opportunity gets small boost
	if contains(securityTags, "value-opportunity") {
		priority *= 1.1
	}

	return priority
}
