package calculators

import (
	"fmt"
	"math"
	"sort"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
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
func (c *OpportunityBuysCalculator) Category() planningdomain.OpportunityCategory {
	return planningdomain.OpportunityCategoryOpportunityBuys
}

// Calculate identifies opportunity buy candidates.
func (c *OpportunityBuysCalculator) Calculate(
	ctx *planningdomain.OpportunityContext,
	params map[string]interface{},
) (planningdomain.CalculatorResult, error) {
	// Parameters with defaults
	minScore := GetFloatParam(params, "min_score", 0.65) // Aligned with relaxed Path 3 (0.65 opportunity score)
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	maxPositions := GetIntParam(params, "max_positions", 5)            // Default to top 5
	excludeExisting := GetBoolParam(params, "exclude_existing", false) // Exclude positions we already have

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	// Initialize exclusion collector to track pre-filtered securities
	exclusions := NewExclusionCollector(c.Name())

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping opportunity buys")
		return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	// NOTE: Cash checks removed - sequence generator handles cash feasibility
	// This allows SELL→BUY sequences where sells generate cash for buys

	// Extract config for tag filtering
	var config *planningdomain.PlannerConfiguration
	if cfg, ok := params["config"].(*planningdomain.PlannerConfiguration); ok && cfg != nil {
		config = cfg
	} else {
		config = planningdomain.NewDefaultConfiguration()
	}

	// Check which positions we already have (use ISIN for internal tracking)
	existingPositions := make(map[string]bool)
	for _, position := range ctx.EnrichedPositions {
		if position.ISIN != "" {
			existingPositions[position.ISIN] = true // ISIN key ✅
		}
	}

	// Tag-based pre-filtering (when enabled) - still uses Symbols for tag API
	var candidateMap map[string]bool
	var candidateSymbols []string

	if config.EnableTagFiltering && c.tagFilter != nil {
		symbols, err := c.tagFilter.GetOpportunityCandidates(ctx, config)
		if err != nil {
			return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, fmt.Errorf("failed to get tag-based candidates: %w", err)
		}

		if len(symbols) == 0 {
			c.log.Debug().Msg("No tag-based candidates found")
			return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
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
		// No tag filtering - process all securities with scores (ISINs from SecurityScores)
		if len(ctx.SecurityScores) == 0 {
			c.log.Debug().Msg("No security scores available")
			return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
		}

		// SecurityScores is ISIN-keyed, but we need to match with tag filter logic
		// Build candidateSymbols from Securities that have scores
		for _, security := range ctx.Securities {
			if security.ISIN != "" {
				if _, hasScore := ctx.SecurityScores[security.ISIN]; hasScore {
					candidateSymbols = append(candidateSymbols, security.Symbol)
				}
			}
		}
	}

	c.log.Debug().
		Float64("min_score", minScore).
		Int("max_positions", maxPositions).
		Bool("tag_filtering_enabled", config.EnableTagFiltering).
		Msg("Calculating opportunity buys")

	// Build list of scored securities
	type scoredSecurity struct {
		isin   string
		symbol string
		score  float64
	}
	var scoredSecurities []scoredSecurity

	for _, symbol := range candidateSymbols {
		// Look up security to get ISIN
		var security universe.Security
		var found bool
		for _, sec := range ctx.Securities {
			if sec.Symbol == symbol {
				security = sec
				found = true
				break
			}
		}
		if !found || security.ISIN == "" {
			c.log.Debug().
				Str("symbol", symbol).
				Msg("Security not found or missing ISIN, skipping")
			exclusions.Add("", symbol, "", "missing ISIN or security not found")
			continue
		}

		isin := security.ISIN
		securityName := security.Name

		// Get score by ISIN
		score, ok := ctx.SecurityScores[isin] // ISIN key ✅
		if !ok {
			exclusions.Add(isin, symbol, securityName, "no score available")
			continue
		}
		if score < minScore {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("score %.2f below minimum %.2f", score, minScore))
			continue
		}

		// Skip if we already have this position and exclude_existing is true
		if excludeExisting && existingPositions[isin] { // ISIN key ✅
			exclusions.Add(isin, symbol, securityName, "already have position (exclude_existing=true)")
			continue
		}

		// Skip if recently bought (ISIN lookup)
		if ctx.RecentlyBoughtISINs[isin] { // ISIN key ✅
			exclusions.Add(isin, symbol, securityName, "recently bought (cooling off period)")
			continue
		}

		scoredSecurities = append(scoredSecurities, scoredSecurity{
			isin:   isin,
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
	var candidates []planningdomain.ActionCandidate
	for _, scored := range scoredSecurities {
		isin := scored.isin
		symbol := scored.symbol
		score := scored.score

		// Get security info (direct ISIN lookup)
		security, ok := ctx.StocksByISIN[isin] // ISIN key ✅
		if !ok {
			c.log.Warn().
				Str("isin", isin).
				Str("symbol", symbol).
				Msg("Security not found in StocksByISIN")
			exclusions.Add(isin, symbol, "", "security not found in StocksByISIN")
			continue
		}

		securityName := security.Name

		// Check per-security constraint: AllowBuy must be true
		if !security.AllowBuy {
			c.log.Debug().
				Str("isin", isin).
				Str("symbol", symbol).
				Msg("Skipping security: allow_buy=false")
			exclusions.Add(isin, symbol, securityName, "allow_buy=false")
			continue
		}

		// Apply expected return filtering using unified calculator
		// ExpectedReturns already has:
		// - 6% absolute minimum filter applied (securities below are excluded)
		// - Priority multipliers applied
		// - Regime adjustments applied
		// - Quality-aware penalty system applied
		var expectedReturn *float64
		if ctx.ExpectedReturns != nil {
			if expRet, ok := ctx.ExpectedReturns[isin]; ok {
				expectedReturn = &expRet
			}
		}

		// If no expected return, the security was filtered by the unified calculator
		// (typically below 6% minimum return after adjustments)
		if expectedReturn == nil {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("Filtered out: no expected return (failed unified return filter)")
			exclusions.Add(isin, symbol, securityName, "below minimum expected return (unified filter)")
			continue
		}

		// Get target return for threshold comparison
		targetReturn := ctx.TargetReturn
		if targetReturn == 0 {
			targetReturn = 0.11 // Default 11%
		}
		thresholdPct := ctx.TargetReturnThresholdPct
		if thresholdPct == 0 {
			thresholdPct = 0.70 // Default 70%
		}
		minReturnThreshold := targetReturn * thresholdPct

		// Apply score penalty if expected return is below threshold
		// Note: ExpectedReturns already has penalties baked in, this adds priority adjustment
		penalty := 0.0
		if *expectedReturn < minReturnThreshold {
			shortfallRatio := (minReturnThreshold - *expectedReturn) / minReturnThreshold
			penalty = math.Min(0.2, shortfallRatio*0.3) // Up to 20% priority penalty

			// Apply penalty to score
			score = score * (1.0 - penalty)

			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Float64("expected_return", *expectedReturn).
				Float64("min_threshold", minReturnThreshold).
				Float64("penalty", penalty).
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
				exclusions.Add(isin, symbol, securityName, "value trap detected (tag-based)")
				continue
			}

			// Skip bubble risks (classical or ensemble, unless it's quality-high-cagr)
			if (contains(securityTags, "bubble-risk") || contains(securityTags, "ensemble-bubble-risk")) &&
				!contains(securityTags, "quality-high-cagr") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping bubble risk (tag-based detection)")
				exclusions.Add(isin, symbol, securityName, "bubble risk detected (tag-based)")
				continue
			}

			// Skip securities below absolute minimum return (hard filter from tags)
			if contains(securityTags, "below-minimum-return") {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - below absolute minimum return (tag-based filter)")
				exclusions.Add(isin, symbol, securityName, "below minimum return (tag-based)")
				continue
			}

			// Skip new positions if quality gate failed (inverted logic - cleaner)
			if !existingPositions[isin] && contains(securityTags, "quality-gate-fail") { // ISIN key ✅
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - quality gate failed (tag-based)")
				exclusions.Add(isin, symbol, securityName, "quality gate failed (tag-based)")
				continue
			}
		} else {
			// Score-based quality gate fallback
			qualityCheck := CheckQualityGates(ctx, isin, !existingPositions[isin], config) // ISIN parameter ✅

			if qualityCheck.IsEnsembleValueTrap {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping value trap (score-based detection)")
				exclusions.Add(isin, symbol, securityName, "value trap detected (score-based)")
				continue
			}

			if qualityCheck.IsBubbleRisk {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping bubble risk (score-based detection)")
				exclusions.Add(isin, symbol, securityName, "bubble risk detected (score-based)")
				continue
			}

			if qualityCheck.BelowMinimumReturn {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - below absolute minimum return (score-based filter)")
				exclusions.Add(isin, symbol, securityName, "below minimum return (score-based)")
				continue
			}

			if !qualityCheck.PassesQualityGate {
				c.log.Debug().
					Str("symbol", symbol).
					Str("reason", qualityCheck.QualityGateReason).
					Msg("Skipping - quality gate failed (score-based)")
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quality gate failed: %s (score-based)", qualityCheck.QualityGateReason))
				continue
			}
		}

		// Get current price (direct ISIN lookup)
		currentPrice, ok := ctx.CurrentPrices[isin] // ISIN key ✅
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available")
			exclusions.Add(isin, symbol, securityName, "no current price available")
			continue
		}

		// Calculate quantity based on Kelly-optimal size if available, otherwise use maxValuePerPosition
		targetValue := maxValuePerPosition

		// Use Kelly-optimal size if available (as fraction of portfolio value)
		if ctx.KellySizes != nil {
			if kellySize, hasKellySize := ctx.KellySizes[isin]; hasKellySize && kellySize > 0 { // ISIN key ✅
				// Kelly size is a fraction (e.g., 0.05 = 5% of portfolio)
				kellyValue := kellySize * ctx.TotalPortfolioValueEUR
				// Use Kelly size if it's smaller than maxValuePerPosition (more conservative)
				if kellyValue < maxValuePerPosition {
					targetValue = kellyValue
					c.log.Debug().
						Str("symbol", symbol).
						Str("isin", isin).
						Float64("kelly_size", kellySize).
						Float64("kelly_value", kellyValue).
						Float64("max_value", maxValuePerPosition).
						Msg("Using Kelly-optimal size for opportunity buy")
				}
			}
		}

		// NOTE: Cash cap removed - sequence generator handles cash feasibility

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
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quantity below minimum lot size %d", security.MinLot))
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
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("trade value €%.2f below minimum €%.2f", valueEUR, minTradeAmount))
			continue
		}

		// Concentration guardrail - block if would exceed limits
		passes, concentrationReason := CheckConcentrationGuardrail(isin, security.Geography, valueEUR, ctx)
		if !passes {
			c.log.Debug().
				Str("symbol", symbol).
				Str("isin", isin).
				Str("reason", concentrationReason).
				Msg("Skipping: concentration limit exceeded")
			exclusions.Add(isin, symbol, securityName, concentrationReason)
			continue
		}

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		totalCostEUR := valueEUR + transactionCost

		// NOTE: Cash check removed - sequence generator handles cash feasibility

		// Calculate priority with tag-based boosting
		priority := c.calculatePriority(score, securityTags, config)

		// Apply quantum warning penalty (30% for new positions)
		if config.EnableTagFiltering && len(securityTags) > 0 {
			priority = ApplyQuantumWarningPenalty(priority, securityTags, "opportunity_buys")
		}

		// Apply tag-based priority boosts (with regime-aware logic)
		if config.EnableTagFiltering && len(securityTags) > 0 {
			priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "opportunity_buys", c.securityRepo)
		}

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
		if !existingPositions[isin] { // ISIN key ✅
			tags = append(tags, "new_position")
		}
		if contains(securityTags, "quality-value") {
			tags = append(tags, "quality_value")
		}
		if contains(securityTags, "high-quality") {
			tags = append(tags, "high_quality")
		}

		candidate := planningdomain.ActionCandidate{
			Side:     "BUY",
			ISIN:     isin,   // PRIMARY identifier ✅
			Symbol:   symbol, // BOUNDARY identifier
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
	logMsg.Int("pre_filtered", len(exclusions.Result())).Msg("Opportunity buy candidates identified")

	return planningdomain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}

// calculatePriority calculates priority with optional tag-based boosting.
func (c *OpportunityBuysCalculator) calculatePriority(
	baseScore float64,
	securityTags []string,
	config *planningdomain.PlannerConfiguration,
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
