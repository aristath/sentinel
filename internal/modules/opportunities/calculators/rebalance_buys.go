package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// RebalanceBuysCalculator identifies underweight positions to buy for rebalancing.
// Supports optional tag-based pre-filtering for performance when EnableTagFiltering=true.
type RebalanceBuysCalculator struct {
	*BaseCalculator
	tagFilter    TagFilter
	securityRepo SecurityRepository
}

// NewRebalanceBuysCalculator creates a new rebalance buys calculator.
func NewRebalanceBuysCalculator(
	tagFilter TagFilter,
	securityRepo SecurityRepository,
	log zerolog.Logger,
) *RebalanceBuysCalculator {
	return &RebalanceBuysCalculator{
		BaseCalculator: NewBaseCalculator(log, "rebalance_buys"),
		tagFilter:      tagFilter,
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *RebalanceBuysCalculator) Name() string {
	return "rebalance_buys"
}

// Category returns the opportunity category.
func (c *RebalanceBuysCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryRebalanceBuys
}

// Calculate identifies rebalance buy opportunities.
func (c *RebalanceBuysCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) (domain.CalculatorResult, error) {
	// Parameters with defaults
	minUnderweightThreshold := GetFloatParam(params, "min_underweight_threshold", 0.05) // 5% underweight
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	minScore := GetFloatParam(params, "min_score", 0.65)    // Aligned with relaxed Path 3 (0.65 opportunity score)
	maxPositions := GetIntParam(params, "max_positions", 0) // 0 = unlimited

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	// Initialize exclusion collector
	exclusions := NewExclusionCollector(c.Name(), ctx.DismissedFilters)

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
			return domain.CalculatorResult{PreFiltered: exclusions.Result()}, fmt.Errorf("failed to get tag-based candidates: %w", err)
		}

		if len(candidateSymbols) == 0 {
			c.log.Debug().Msg("No tag-based candidates found")
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

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping rebalance buys")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	if ctx.AvailableCashEUR <= minTradeAmount {
		c.log.Debug().
			Float64("available_cash", ctx.AvailableCashEUR).
			Float64("min_trade_amount", minTradeAmount).
			Msg("No available cash (below minimum trade amount)")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	// Check if we have country allocations and weights
	if ctx.CountryAllocations == nil || ctx.CountryWeights == nil {
		c.log.Debug().Msg("No country allocation data available")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	c.log.Debug().
		Float64("min_underweight_threshold", minUnderweightThreshold).
		Msg("Calculating rebalance buys")

	// Identify underweight countries
	underweightCountries := make(map[string]float64)
	for country, targetAllocation := range ctx.CountryWeights {
		currentAllocation := ctx.CountryAllocations[country]
		underweight := targetAllocation - currentAllocation
		if underweight > minUnderweightThreshold {
			underweightCountries[country] = underweight
			c.log.Debug().
				Str("country", country).
				Float64("current", currentAllocation).
				Float64("target", targetAllocation).
				Float64("underweight", underweight).
				Msg("Underweight country identified")
		}
	}

	if len(underweightCountries) == 0 {
		c.log.Debug().Msg("No underweight countries")
		return domain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	// Build candidates for securities in underweight countries
	type scoredCandidate struct {
		isin        string
		symbol      string
		group       string
		underweight float64
		score       float64
	}
	var scoredCandidates []scoredCandidate

	for isin, security := range ctx.StocksByISIN {
		symbol := security.Symbol
		securityName := security.Name

		// Skip if recently bought (ISIN lookup)
		if ctx.RecentlyBoughtISINs[isin] { // ISIN key ✅
			exclusions.Add(isin, symbol, securityName, "recently bought (cooling off period)")
			continue
		}

		// Skip if tag-based pre-filtering is enabled and symbol not in candidate set
		if config.EnableTagFiltering && candidateMap != nil {
			if !candidateMap[symbol] {
				exclusions.Add(isin, symbol, securityName, "no matching opportunity tags")
				continue
			}
		}

		// Get security and extract country
		country := security.Country
		if country == "" {
			exclusions.Add(isin, symbol, securityName, "no country assigned")
			continue
		}

		// Check per-security constraint: AllowBuy must be true
		if !security.AllowBuy {
			c.log.Debug().
				Str("symbol", symbol).
				Msg("Skipping security: allow_buy=false")
			exclusions.Add(isin, symbol, securityName, "allow_buy=false")
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

		// Check if this group is underweight
		underweight, ok := underweightCountries[group]
		if !ok {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("country group %s is not underweight", group))
			continue
		}

		// Get security score (ISIN lookup)
		score := 0.5 // Default neutral score
		if ctx.SecurityScores != nil {
			if s, ok := ctx.SecurityScores[isin]; ok { // ISIN key ✅
				score = s
			}
		}

		// Filter by minimum score
		if score < minScore {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("score %.2f below minimum %.2f", score, minScore))
			continue
		}

		// Quality gate checks - CRITICAL protection against bad trades
		if config.EnableTagFiltering && c.securityRepo != nil {
			// Tag-based quality checks (when enabled)
			securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
			if err == nil {
				// Check for exclusion tags (inverted logic - skip if present)
				if contains(securityTags, "value-trap") || contains(securityTags, "ensemble-value-trap") {
					c.log.Debug().
						Str("symbol", symbol).
						Msg("Skipping - value trap detected (tag-based check)")
					exclusions.Add(isin, symbol, securityName, "value trap detected (tag-based)")
					continue
				}
				if contains(securityTags, "bubble-risk") || contains(securityTags, "ensemble-bubble-risk") {
					c.log.Debug().
						Str("symbol", symbol).
						Msg("Skipping - bubble risk detected (tag-based check)")
					exclusions.Add(isin, symbol, securityName, "bubble risk detected (tag-based)")
					continue
				}
				if contains(securityTags, "below-minimum-return") {
					c.log.Debug().
						Str("symbol", symbol).
						Msg("Skipping - below minimum return (tag-based check)")
					exclusions.Add(isin, symbol, securityName, "below minimum return (tag-based)")
					continue
				}
				// Skip if quality gate failed (inverted logic - cleaner)
				if contains(securityTags, "quality-gate-fail") {
					c.log.Debug().
						Str("symbol", symbol).
						Msg("Skipping - quality gate failed (tag-based check)")
					exclusions.Add(isin, symbol, securityName, "quality gate failed (tag-based)")
					continue
				}
			}
		} else {
			// Score-based fallback when tag filtering is disabled
			qualityCheck := CheckQualityGates(ctx, isin, true, config) // ISIN parameter ✅
			if qualityCheck.IsEnsembleValueTrap {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - value trap detected (score-based check)")
				exclusions.Add(isin, symbol, securityName, "value trap detected (score-based)")
				continue
			}
			if qualityCheck.IsBubbleRisk {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - bubble risk detected (score-based check)")
				exclusions.Add(isin, symbol, securityName, "bubble risk detected (score-based)")
				continue
			}
			if qualityCheck.BelowMinimumReturn {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - below minimum return (score-based check)")
				exclusions.Add(isin, symbol, securityName, "below minimum return (score-based)")
				continue
			}
			if !qualityCheck.PassesQualityGate {
				c.log.Debug().
					Str("symbol", symbol).
					Msg("Skipping - quality gate failed (score-based check)")
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quality gate failed: %s (score-based)", qualityCheck.QualityGateReason))
				continue
			}
		}

		scoredCandidates = append(scoredCandidates, scoredCandidate{
			isin:        isin,
			symbol:      symbol,
			group:       group,
			underweight: underweight,
			score:       score,
		})
	}

	// Sort by combined priority (underweight * score)
	sort.Slice(scoredCandidates, func(i, j int) bool {
		priorityI := scoredCandidates[i].underweight * scoredCandidates[i].score
		priorityJ := scoredCandidates[j].underweight * scoredCandidates[j].score
		return priorityI > priorityJ
	})

	// Limit if needed
	if maxPositions > 0 && len(scoredCandidates) > maxPositions {
		scoredCandidates = scoredCandidates[:maxPositions]
	}

	// Create action candidates
	var candidates []domain.ActionCandidate
	for _, scored := range scoredCandidates {
		isin := scored.isin
		symbol := scored.symbol

		// Get security info (direct ISIN lookup)
		security, ok := ctx.StocksByISIN[isin] // ISIN key ✅
		if !ok {
			exclusions.Add(isin, symbol, "", "security not found in StocksByISIN")
			continue
		}

		securityName := security.Name

		// Get current price (direct ISIN lookup)
		currentPrice, ok := ctx.CurrentPrices[isin] // ISIN key ✅
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("No current price available")
			exclusions.Add(isin, symbol, securityName, "no current price available")
			continue
		}

		// Calculate quantity
		targetValue := maxValuePerPosition
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

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		totalCostEUR := valueEUR + transactionCost

		// Check if we have enough cash
		if totalCostEUR > ctx.AvailableCashEUR {
			exclusions.Add(isin, symbol, securityName, fmt.Sprintf("insufficient cash: need €%.2f, have €%.2f", totalCostEUR, ctx.AvailableCashEUR))
			continue
		}

		// Priority based on underweight and score
		priority := scored.underweight * scored.score * 0.6

		// Apply quantum warning penalty and priority boosts (30% for rebalance buys - new positions)
		if config.EnableTagFiltering && c.securityRepo != nil {
			securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
			if err == nil && len(securityTags) > 0 {
				priority = ApplyQuantumWarningPenalty(priority, securityTags, "rebalance_buys")
				priority = ApplyTagBasedPriorityBoosts(priority, securityTags, "rebalance_buys", c.securityRepo)
			}
		}

		// Build reason
		reason := fmt.Sprintf("Rebalance: %s underweight by %.1f%% (score: %.2f)",
			scored.group, scored.underweight*100, scored.score)

		// Build tags
		tags := []string{"rebalance", "buy", "underweight"}

		candidate := domain.ActionCandidate{
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

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("underweight_countries", len(underweightCountries)).
		Int("pre_filtered", len(exclusions.Result())).
		Msg("Rebalance buy opportunities identified")

	return domain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}
