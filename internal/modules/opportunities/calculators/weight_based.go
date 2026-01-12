package calculators

import (
	"fmt"
	"sort"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// WeightBasedCalculator identifies buy/sell opportunities based on optimizer target weights.
// Enhanced with quality gates to prevent buying low-quality securities even if optimizer says so.
type WeightBasedCalculator struct {
	*BaseCalculator
	securityRepo SecurityRepository // Added for quality gate filtering
}

// NewWeightBasedCalculator creates a new weight-based calculator.
// securityRepo is required for quality gate checks (conditional on EnableTagFiltering).
func NewWeightBasedCalculator(securityRepo SecurityRepository, log zerolog.Logger) *WeightBasedCalculator {
	return &WeightBasedCalculator{
		BaseCalculator: NewBaseCalculator(log, "weight_based"),
		securityRepo:   securityRepo,
	}
}

// Name returns the calculator name.
func (c *WeightBasedCalculator) Name() string {
	return "weight_based"
}

// Category returns the opportunity category.
func (c *WeightBasedCalculator) Category() planningdomain.OpportunityCategory {
	return planningdomain.OpportunityCategoryWeightBased
}

// Calculate identifies weight-based opportunities (both buys and sells).
func (c *WeightBasedCalculator) Calculate(
	ctx *planningdomain.OpportunityContext,
	params map[string]interface{},
) (planningdomain.CalculatorResult, error) {
	// Parameters with defaults
	minWeightDiff := GetFloatParam(params, "min_weight_diff", 0.02) // 2% minimum difference
	maxValuePerTrade := GetFloatParam(params, "max_value_per_trade", 500.0)
	maxBuyPositions := GetIntParam(params, "max_buy_positions", 5)
	maxSellPositions := GetIntParam(params, "max_sell_positions", 5)
	maxSellPercentage := GetFloatParam(params, "max_sell_percentage", 1.0) // Risk management cap

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	// Initialize exclusion collector
	exclusions := NewExclusionCollector(c.Name(), ctx.DismissedFilters)

	// Check if we have target weights
	if len(ctx.TargetWeights) == 0 {
		c.log.Debug().Msg("No target weights available")
		return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	if ctx.TotalPortfolioValueEUR <= 0 {
		c.log.Debug().Msg("Invalid portfolio value")
		return planningdomain.CalculatorResult{PreFiltered: exclusions.Result()}, nil
	}

	c.log.Debug().
		Float64("min_weight_diff", minWeightDiff).
		Msg("Calculating weight-based opportunities")

	// Calculate current weights (use ISIN for internal tracking)
	// WeightInPortfolio is pre-calculated in EnrichedPosition (no lookup needed)
	currentWeights := make(map[string]float64)
	for _, position := range ctx.EnrichedPositions {
		currentWeights[position.ISIN] = position.WeightInPortfolio // ISIN key ✅
	}

	// Identify weight differences
	type weightDiff struct {
		isin      string
		current   float64
		target    float64
		diff      float64
		absSignal float64 // Absolute difference (for sorting)
	}
	var diffs []weightDiff

	// Check all target weights (now ISIN-keyed)
	for isin, targetWeight := range ctx.TargetWeights { // ISIN key ✅
		currentWeight := currentWeights[isin] // ISIN key ✅
		diff := targetWeight - currentWeight

		if diff > minWeightDiff || diff < -minWeightDiff {
			diffs = append(diffs, weightDiff{
				isin:      isin,
				current:   currentWeight,
				target:    targetWeight,
				diff:      diff,
				absSignal: diff, // Use absolute for sorting
			})
		}
	}

	// Sort by absolute difference (descending)
	sort.Slice(diffs, func(i, j int) bool {
		if diffs[i].diff > 0 && diffs[j].diff < 0 {
			return true // Buys first
		}
		if diffs[i].diff < 0 && diffs[j].diff > 0 {
			return false // Then sells
		}
		// Within same type, sort by absolute magnitude
		return abs(diffs[i].diff) > abs(diffs[j].diff)
	})

	var candidates []planningdomain.ActionCandidate
	buyCount := 0
	sellCount := 0

	for _, d := range diffs {
		isin := d.isin
		diff := d.diff

		// Get security info (direct ISIN lookup)
		security, ok := ctx.StocksByISIN[isin] // ISIN key ✅
		if !ok {
			c.log.Warn().
				Str("isin", isin).
				Msg("Security not found in StocksByISIN")
			exclusions.Add(isin, "", "", "security not found in StocksByISIN")
			continue
		}

		symbol := security.Symbol // Get Symbol for logging/tags
		securityName := security.Name

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

		if diff > 0 {
			// Need to BUY (underweight)
			if !ctx.AllowBuy {
				exclusions.Add(isin, symbol, securityName, "buying not allowed")
				continue
			}
			if buyCount >= maxBuyPositions {
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("max buy positions reached (%d)", maxBuyPositions))
				continue
			}
			if ctx.RecentlyBoughtISINs[isin] { // ISIN key ✅
				exclusions.Add(isin, symbol, securityName, "recently bought (cooling off period)")
				continue
			}
			if ctx.AvailableCashEUR <= 0 {
				exclusions.Add(isin, symbol, securityName, "no available cash")
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

			// CRITICAL: Quality gate filtering (if securityRepo is available)
			// Get config from params
			var config *planningdomain.PlannerConfiguration
			if cfg, ok := params["config"].(*planningdomain.PlannerConfiguration); ok && cfg != nil {
				config = cfg
			}

			if c.securityRepo != nil {
				securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
				useTagChecks := err == nil && config != nil && config.EnableTagFiltering && len(securityTags) > 0

				if useTagChecks {
					// Use tag-based checks (when tags are enabled)
					// Skip value traps (classical or ensemble)
					if contains(securityTags, "value-trap") || contains(securityTags, "ensemble-value-trap") {
						c.log.Debug().
							Str("symbol", symbol).
							Msg("Skipping value trap (ensemble detection)")
						exclusions.Add(isin, symbol, securityName, "value trap detected (tag-based)")
						continue
					}

					// Skip bubble risks (classical or ensemble, unless it's quality-high-cagr)
					if (contains(securityTags, "bubble-risk") || contains(securityTags, "ensemble-bubble-risk")) &&
						!contains(securityTags, "quality-high-cagr") {
						c.log.Debug().
							Str("symbol", symbol).
							Msg("Skipping bubble risk (ensemble detection)")
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

					// Require quality gate pass for new positions
					// Check if this is a new position (not in current positions)
					isNewPosition := true
					for _, pos := range ctx.EnrichedPositions {
						if pos.ISIN == isin { // ISIN comparison ✅
							isNewPosition = false
							break
						}
					}

					if isNewPosition && contains(securityTags, "quality-gate-fail") {
						c.log.Debug().
							Str("symbol", symbol).
							Str("isin", isin).
							Msg("Skipping - quality gate failed (new position)")
						exclusions.Add(isin, symbol, securityName, "quality gate failed (tag-based, new position)")
						continue
					}
				} else {
					// Use score-based checks (when tags are disabled or unavailable)
					// Check if this is a new position
					isNewPosition := true
					for _, pos := range ctx.EnrichedPositions {
						if pos.ISIN == isin { // ISIN comparison ✅
							isNewPosition = false
							break
						}
					}

					qualityCheck := CheckQualityGates(ctx, isin, isNewPosition, config) // ISIN parameter ✅

					if qualityCheck.IsEnsembleValueTrap {
						c.log.Debug().
							Str("symbol", symbol).
							Bool("classical", qualityCheck.IsValueTrap).
							Bool("quantum", qualityCheck.IsQuantumValueTrap).
							Float64("quantum_prob", qualityCheck.QuantumValueTrapProb).
							Msg("Skipping value trap (ensemble detection)")
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
							Msg("Skipping - quality gate failed (score-based check)")
						exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quality gate failed: %s (score-based)", qualityCheck.QualityGateReason))
						continue
					}
				}
			}

			// Calculate target value
			targetValue := diff * ctx.TotalPortfolioValueEUR

			// Use Kelly-optimal size if available (as upper bound)
			if ctx.KellySizes != nil {
				if kellySize, hasKellySize := ctx.KellySizes[isin]; hasKellySize && kellySize > 0 { // ISIN key ✅
					// Kelly size is a fraction (e.g., 0.05 = 5% of portfolio)
					kellyValue := kellySize * ctx.TotalPortfolioValueEUR
					// Cap target value at Kelly-optimal size (more conservative)
					if kellyValue < targetValue {
						targetValue = kellyValue
						c.log.Debug().
							Str("symbol", symbol).
							Str("isin", isin).
							Float64("kelly_size", kellySize).
							Float64("kelly_value", kellyValue).
							Float64("target_value", targetValue).
							Msg("Capping weight-based buy at Kelly-optimal size")
					}
				}
			}

			if targetValue > maxValuePerTrade {
				targetValue = maxValuePerTrade
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
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("quantity below minimum lot size %d", security.MinLot))
				continue
			}

			// Recalculate value based on rounded quantity
			valueEUR := float64(quantity) * currentPrice
			transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
			totalCostEUR := valueEUR + transactionCost

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

			if totalCostEUR > ctx.AvailableCashEUR {
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("insufficient cash: need €%.2f, have €%.2f", totalCostEUR, ctx.AvailableCashEUR))
				continue
			}

			priority := abs(diff) * 0.8

			// Boost priority if also has opportunity tags (opportunistic deviation)
			// Apply soft filters for quantum warnings (reduce priority, don't exclude)
			if c.securityRepo != nil {
				securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
				if err == nil {
					// Apply quantum warning penalty (30% for weight-based - new positions)
					priority = ApplyQuantumWarningPenalty(priority, securityTags, "weight_based")

					// Also handle quantum-value-warning (specific to value traps)
					if contains(securityTags, "quantum-value-warning") {
						priority *= 0.7 // Additional 30% reduction for value trap warning
					}

					// Boost if also a value opportunity or quality value
					if contains(securityTags, "quality-value") {
						priority *= 1.3 // 30% boost for quality value + optimizer alignment
					} else if contains(securityTags, "value-opportunity") || contains(securityTags, "high-quality") {
						priority *= 1.15 // 15% boost for opportunity + optimizer alignment
					}
					// Add optimizer-aligned tag if underweight
					if contains(securityTags, "underweight") || contains(securityTags, "slightly-underweight") {
						// Already underweight - this is optimizer-aligned, no action needed
						_ = securityTags // Explicitly acknowledge we're checking but not modifying
					}
				}
			}

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (underweight by %.1f%%)",
				d.target*100, d.current*100, diff*100)

			tags := []string{"weight_based", "buy", "underweight", "optimizer-aligned"}

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
			buyCount++

		} else {
			// Need to SELL (overweight)
			if !ctx.AllowSell {
				exclusions.Add(isin, symbol, securityName, "selling not allowed")
				continue
			}
			if sellCount >= maxSellPositions {
				exclusions.Add(isin, symbol, securityName, fmt.Sprintf("max sell positions reached (%d)", maxSellPositions))
				continue
			}
			if ctx.IneligibleISINs[isin] { // ISIN keys ✅
				exclusions.Add(isin, symbol, securityName, "marked as ineligible")
				continue
			}
			if ctx.RecentlySoldISINs[isin] { // ISIN keys ✅
				exclusions.Add(isin, symbol, securityName, "recently sold (cooling off period)")
				continue
			}

			// Check per-security constraint: AllowSell must be true
			if !security.AllowSell {
				c.log.Debug().
					Str("symbol", symbol).
					Str("isin", isin).
					Msg("Skipping security: allow_sell=false")
				exclusions.Add(isin, symbol, securityName, "allow_sell=false")
				continue
			}

			// Find position by ISIN
			var foundPosition *planningdomain.EnrichedPosition
			for i := range ctx.EnrichedPositions {
				if ctx.EnrichedPositions[i].ISIN == isin { // ISIN comparison ✅
					pos := ctx.EnrichedPositions[i]
					foundPosition = &pos
					break
				}
			}
			if foundPosition == nil {
				exclusions.Add(isin, symbol, securityName, "no position found to sell")
				continue
			}

			// Calculate target reduction
			targetReduction := abs(diff) * ctx.TotalPortfolioValueEUR
			if targetReduction > maxValuePerTrade {
				targetReduction = maxValuePerTrade
			}

			quantity := int(targetReduction / currentPrice)
			if quantity == 0 {
				quantity = 1
			}
			if float64(quantity) > foundPosition.Quantity {
				quantity = int(foundPosition.Quantity)
			}

			// Cap at MaxSellPercentage (risk management)
			if maxSellPercentage < 1.0 {
				maxAllowed := int(foundPosition.Quantity * maxSellPercentage)
				if quantity > maxAllowed {
					quantity = maxAllowed
				}
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

			// Ensure we don't exceed position quantity after rounding
			if float64(quantity) > foundPosition.Quantity {
				quantity = int(foundPosition.Quantity)
				// Re-round after limiting to position quantity
				quantity = RoundToLotSize(quantity, security.MinLot)
				if quantity <= 0 {
					c.log.Debug().
						Str("symbol", symbol).
						Int("min_lot", security.MinLot).
						Float64("position_quantity", foundPosition.Quantity).
						Msg("Skipping security: position quantity too small for minimum lot size")
					exclusions.Add(isin, symbol, securityName, fmt.Sprintf("position quantity %.0f too small for minimum lot size %d", foundPosition.Quantity, security.MinLot))
					continue
				}
			}

			valueEUR := float64(quantity) * currentPrice
			transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
			netValueEUR := valueEUR - transactionCost

			priority := abs(diff) * 0.8

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (overweight by %.1f%%)",
				d.target*100, d.current*100, abs(diff)*100)

			tags := []string{"weight_based", "sell", "overweight"}

			candidate := planningdomain.ActionCandidate{
				Side:     "SELL",
				ISIN:     isin,   // PRIMARY identifier ✅
				Symbol:   symbol, // BOUNDARY identifier
				Name:     security.Name,
				Quantity: quantity,
				Price:    currentPrice,
				ValueEUR: netValueEUR,
				Currency: string(security.Currency),
				Priority: priority,
				Reason:   reason,
				Tags:     tags,
			}

			candidates = append(candidates, candidate)
			sellCount++
		}
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Int("buys", buyCount).
		Int("sells", sellCount).
		Int("pre_filtered", len(exclusions.Result())).
		Msg("Weight-based opportunities identified")

	return planningdomain.CalculatorResult{
		Candidates:  candidates,
		PreFiltered: exclusions.Result(),
	}, nil
}

// abs returns the absolute value of a float64.
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
