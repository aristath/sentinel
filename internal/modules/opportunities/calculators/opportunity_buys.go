package calculators

import (
	"fmt"
	"math"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// OpportunityBuysCalculator identifies new buying opportunities based on security scores.
// Supports optional tag-based pre-filtering for performance when EnableTagFiltering=true.
type OpportunityBuysCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo SecurityRepository
}

// NewOpportunityBuysCalculator creates a new opportunity buys calculator.
func NewOpportunityBuysCalculator(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *OpportunityBuysCalculator {
	return &OpportunityBuysCalculator{
		BaseCalculator: NewBaseCalculator(log, "opportunity_buys"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
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
	maxPositions := GetIntParam(params, "max_positions", 5)            // Default to top 5
	excludeExisting := GetBoolParam(params, "exclude_existing", false) // Exclude positions we already have

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping opportunity buys")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= minTradeAmount {
		c.log.Debug().
			Float64("available_cash", ctx.AvailableCashEUR).
			Float64("min_trade_amount", minTradeAmount).
			Msg("Insufficient cash for opportunity buys (below minimum trade amount)")
		return nil, nil
	}

	// Extract config for tag filtering
	var config *domain.PlannerConfiguration
	if cfg, ok := params["config"].(*domain.PlannerConfiguration); ok && cfg != nil {
		config = cfg
	} else {
		config = domain.NewDefaultConfiguration()
	}

	// Check which positions we already have
	existingPositions := make(map[string]bool)
	for _, position := range ctx.Positions {
		existingPositions[position.Symbol] = true
	}

	// Tag-based pre-filtering (when enabled)
	var candidateMap map[string]bool
	var candidateSymbols []string

	if config.EnableTagFiltering && c.tagFilter != nil {
		symbols, err := c.tagFilter.GetOpportunityCandidates(ctx, config)
		if err != nil {
			return nil, fmt.Errorf("failed to get tag-based candidates: %w", err)
		}

		if len(symbols) == 0 {
			c.log.Debug().Msg("No tag-based candidates found")
			return nil, nil
		}

		candidateSymbols = symbols
		candidateMap = make(map[string]bool)
		for _, symbol := range symbols {
			candidateMap[symbol] = true
		}

		c.log.Debug().
			Int("tag_candidates", len(candidateSymbols)).
			Msg("Tag-based pre-filtering complete")
	} else {
		// No tag filtering - process all securities with scores
		if len(ctx.SecurityScores) == 0 {
			c.log.Debug().Msg("No security scores available")
			return nil, nil
		}

		for symbol := range ctx.SecurityScores {
			candidateSymbols = append(candidateSymbols, symbol)
		}
	}

	c.log.Debug().
		Float64("min_score", minScore).
		Int("max_positions", maxPositions).
		Bool("tag_filtering_enabled", config.EnableTagFiltering).
		Msg("Calculating opportunity buys")

	// Build list of scored securities
	type scoredSecurity struct {
		symbol string
		score  float64
	}
	var scoredSecurities []scoredSecurity

	for _, symbol := range candidateSymbols {
		// Get score
		score, ok := ctx.SecurityScores[symbol]
		if !ok || score < minScore {
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

		// Get security info
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("Security not found in stocks map")
			continue
		}

		// Check per-security constraint: AllowBuy must be true
		if !security.AllowBuy {
			c.log.Debug().
				Str("symbol", symbol).
				Msg("Skipping security: allow_buy=false")
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

		// Quality gate checks (tag-based or score-based)
		var securityTags []string
		useTagChecks := false
		if config.EnableTagFiltering && c.securityRepo != nil {
			tags, err := c.securityRepo.GetTagsForSecurity(symbol)
			if err == nil && len(tags) > 0 {
				securityTags = tags
				useTagChecks = true
			}
		}

		if useTagChecks {
			// Tag-based quality gates
			// Skip value traps (classical or ensemble)
			if contains(securityTags, "value-trap") || contains(securityTags, "ensemble-value-trap") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping value trap (tag-based detection)")
				continue
			}

			// Skip bubble risks (classical or ensemble, unless it's quality-high-cagr)
			if (contains(securityTags, "bubble-risk") || contains(securityTags, "ensemble-bubble-risk")) &&
				!contains(securityTags, "quality-high-cagr") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping bubble risk (tag-based detection)")
				continue
			}

			// Skip securities below absolute minimum return (hard filter from tags)
			if contains(securityTags, "below-minimum-return") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - below absolute minimum return (tag-based filter)")
				continue
			}

			// Require quality gate pass for new positions
			if !existingPositions[symbol] && !contains(securityTags, "quality-gate-pass") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - quality gate failed (tag-based)")
				continue
			}
		} else {
			// Score-based quality gate fallback
			qualityCheck := CheckQualityGates(ctx, symbol, !existingPositions[symbol], config)

			if qualityCheck.IsEnsembleValueTrap {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping value trap (score-based detection)")
				continue
			}

			if qualityCheck.IsBubbleRisk {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping bubble risk (score-based detection)")
				continue
			}

			if qualityCheck.BelowMinimumReturn {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - below absolute minimum return (score-based filter)")
				continue
			}

			if !qualityCheck.PassesQualityGate {
				c.log.Debug().
					Str("symbol", symbol).
					Str("reason", qualityCheck.QualityGateReason).
					Msg("Skipping - quality gate failed (score-based)")
				continue
			}
		}

		// Get current price
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, symbol)
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available")
			continue
		}

		// Calculate quantity based on Kelly-optimal size if available, otherwise use maxValuePerPosition
		targetValue := maxValuePerPosition

		// Use Kelly-optimal size if available (as fraction of portfolio value)
		if ctx.KellySizes != nil {
			if kellySize, hasKellySize := ctx.KellySizes[symbol]; hasKellySize && kellySize > 0 {
				// Kelly size is a fraction (e.g., 0.05 = 5% of portfolio)
				kellyValue := kellySize * ctx.TotalPortfolioValueEUR
				// Use Kelly size if it's smaller than maxValuePerPosition (more conservative)
				if kellyValue < maxValuePerPosition {
					targetValue = kellyValue
					c.log.Debug().
						Str("symbol", symbol).
						Float64("kelly_size", kellySize).
						Float64("kelly_value", kellyValue).
						Float64("max_value", maxValuePerPosition).
						Msg("Using Kelly-optimal size for opportunity buy")
				}
			}
		}

		if targetValue > ctx.AvailableCashEUR {
			targetValue = ctx.AvailableCashEUR
		}

		quantity := int(targetValue / currentPrice)
		if quantity == 0 {
			quantity = 1
		}

		// Round quantity to lot size and validate
		quantity = RoundToLotSize(quantity, security.MinLot)
		if quantity <= 0 {
			c.log.Debug().
				Str("symbol", symbol).
				Int("min_lot", security.MinLot).
				Msg("Skipping security: quantity below minimum lot size after rounding")
			continue
		}

		// Recalculate value based on rounded quantity
		valueEUR := float64(quantity) * currentPrice

		// Check if rounded quantity still meets minimum trade amount
		if valueEUR < minTradeAmount {
			c.log.Debug().
				Str("symbol", symbol).
				Float64("trade_value", valueEUR).
				Float64("min_trade_amount", minTradeAmount).
				Msg("Skipping trade below minimum trade amount after lot size rounding")
			continue
		}

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		totalCostEUR := valueEUR + transactionCost

		// Check if we have enough cash
		if totalCostEUR > ctx.AvailableCashEUR {
			continue
		}

		// Calculate priority with tag-based boosting
		priority := c.calculatePriority(score, securityTags, config)

		// Build reason
		reason := fmt.Sprintf("High score: %.2f - opportunity buy", score)

		// Add tag-based reason enhancements
		if contains(securityTags, "quality-value") {
			reason += " [Quality Value]"
		} else if contains(securityTags, "high-quality") && contains(securityTags, "value-opportunity") {
			reason += " [High Quality Value]"
		}
		if contains(securityTags, "excellent-total-return") {
			reason += " [Excellent Returns]"
		}

		// Build tags
		tags := []string{"opportunity_buy", "high_score"}
		if !existingPositions[symbol] {
			tags = append(tags, "new_position")
		}
		if contains(securityTags, "quality-value") {
			tags = append(tags, "quality_value")
		}
		if contains(securityTags, "high-quality") {
			tags = append(tags, "high_quality")
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

	// Sort by priority descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Priority > candidates[j].Priority
	})

	logMsg := c.log.Info().Int("candidates", len(candidates))
	if candidateMap != nil {
		logMsg = logMsg.Int("filtered_from", len(candidateMap))
	}
	logMsg.Msg("Opportunity buy candidates identified")

	return candidates, nil
}

// calculatePriority calculates priority with optional tag-based boosting.
func (c *OpportunityBuysCalculator) calculatePriority(
	baseScore float64,
	securityTags []string,
	config *domain.PlannerConfiguration,
) float64 {
	priority := baseScore

	// Apply tag-based boosts only when tag filtering is enabled and tags are available
	if config == nil || !config.EnableTagFiltering || len(securityTags) == 0 {
		return priority
	}

	// Quantum warnings reduce priority
	if contains(securityTags, "quantum-bubble-warning") {
		priority *= 0.7
	}
	if contains(securityTags, "quantum-value-warning") {
		priority *= 0.7
	}

	// Quality value gets strong boost
	if contains(securityTags, "quality-value") {
		priority *= 1.4
	} else if contains(securityTags, "high-quality") && contains(securityTags, "value-opportunity") {
		priority *= 1.3
	}

	// Deep value gets boost
	if contains(securityTags, "deep-value") {
		priority *= 1.2
	}

	// Oversold high-quality securities get boost
	if contains(securityTags, "oversold") && contains(securityTags, "high-quality") {
		priority *= 1.15
	}

	// Excellent returns get strong boost
	if contains(securityTags, "excellent-total-return") {
		priority *= 1.25
	} else if contains(securityTags, "high-total-return") {
		priority *= 1.15
	}

	// Quality high-CAGR gets boost
	if contains(securityTags, "quality-high-cagr") {
		priority *= 1.2
	}

	// Recovery candidates get moderate boost
	if contains(securityTags, "recovery-candidate") {
		priority *= 1.1
	}

	// Dividend growers get boost
	if contains(securityTags, "dividend-grower") {
		priority *= 1.15
	} else if contains(securityTags, "high-dividend") {
		priority *= 1.1
	}

	// Cap at 1.0 (max priority)
	return math.Min(1.0, priority)
}
