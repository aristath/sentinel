package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/domain"
	planningdomain "github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// WeightBasedCalculator identifies buy/sell opportunities based on optimizer target weights.
// Enhanced with quality gates to prevent buying low-quality securities even if optimizer says so.
type WeightBasedCalculator struct {
	*BaseCalculator
	securityRepo *universe.SecurityRepository // Added for quality gate filtering
}

// NewWeightBasedCalculator creates a new weight-based calculator.
func NewWeightBasedCalculator(log zerolog.Logger) *WeightBasedCalculator {
	return &WeightBasedCalculator{
		BaseCalculator: NewBaseCalculator(log, "weight_based"),
		securityRepo:   nil, // Optional - quality gates only work if provided
	}
}

// NewWeightBasedCalculatorWithQualityGates creates a new weight-based calculator with quality gate support.
func NewWeightBasedCalculatorWithQualityGates(securityRepo *universe.SecurityRepository, log zerolog.Logger) *WeightBasedCalculator {
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
) ([]planningdomain.ActionCandidate, error) {
	// Parameters with defaults
	minWeightDiff := GetFloatParam(params, "min_weight_diff", 0.02) // 2% minimum difference
	maxValuePerTrade := GetFloatParam(params, "max_value_per_trade", 500.0)
	maxBuyPositions := GetIntParam(params, "max_buy_positions", 5)
	maxSellPositions := GetIntParam(params, "max_sell_positions", 5)

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	// Check if we have target weights
	if len(ctx.TargetWeights) == 0 {
		c.log.Debug().Msg("No target weights available")
		return nil, nil
	}

	if ctx.TotalPortfolioValueEUR <= 0 {
		c.log.Debug().Msg("Invalid portfolio value")
		return nil, nil
	}

	c.log.Debug().
		Float64("min_weight_diff", minWeightDiff).
		Msg("Calculating weight-based opportunities")

	// Calculate current weights
	currentWeights := make(map[string]float64)
	for _, position := range ctx.Positions {
		currentPrice, ok := ctx.CurrentPrices[position.Symbol]
		if !ok || currentPrice <= 0 {
			continue
		}
		positionValue := float64(position.Quantity) * currentPrice
		currentWeights[position.Symbol] = positionValue / ctx.TotalPortfolioValueEUR
	}

	// Identify weight differences
	type weightDiff struct {
		symbol    string
		current   float64
		target    float64
		diff      float64
		absSignal float64 // Absolute difference (for sorting)
	}
	var diffs []weightDiff

	// Check all target weights
	for symbol, targetWeight := range ctx.TargetWeights {
		currentWeight := currentWeights[symbol]
		diff := targetWeight - currentWeight

		if diff > minWeightDiff || diff < -minWeightDiff {
			diffs = append(diffs, weightDiff{
				symbol:    symbol,
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
		symbol := d.symbol
		diff := d.diff

		// Get security info (SecurityScores uses symbol as key, so we look up by symbol first)
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("Security not found")
			continue
		}

		// Use ISIN if available, otherwise fallback to symbol
		isin := security.ISIN
		if isin == "" {
			isin = symbol // Fallback for CASH positions or securities without ISIN
		}

		// Get current price (try ISIN first, fallback to symbol)
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, symbol)
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
				Str("isin", isin).
				Msg("No current price available")
			continue
		}

		if diff > 0 {
			// Need to BUY (underweight)
			if !ctx.AllowBuy || buyCount >= maxBuyPositions {
				continue
			}
			if ctx.RecentlyBought[symbol] {
				continue
			}
			if ctx.AvailableCashEUR <= 0 {
				continue
			}

			// CRITICAL: Quality gate filtering (if securityRepo is available)
			if c.securityRepo != nil {
				securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
				if err == nil {
					// Skip value traps (classical or ensemble)
					if contains(securityTags, "value-trap") || contains(securityTags, "ensemble-value-trap") {
						c.log.Debug().
							Str("symbol", symbol).
							Msg("Skipping value trap (ensemble detection)")
						continue
					}

					// Skip bubble risks (classical or ensemble, unless it's quality-high-cagr)
					if (contains(securityTags, "bubble-risk") || contains(securityTags, "ensemble-bubble-risk")) &&
						!contains(securityTags, "quality-high-cagr") {
						c.log.Debug().
							Str("symbol", symbol).
							Msg("Skipping bubble risk (ensemble detection)")
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
					// Check if this is a new position (not in current positions)
					isNewPosition := true
					for _, pos := range ctx.Positions {
						if pos.Symbol == symbol {
							isNewPosition = false
							break
						}
					}

					if isNewPosition && !contains(securityTags, "quality-gate-pass") {
						c.log.Debug().
							Str("symbol", symbol).
							Msg("Skipping - quality gate failed (new position)")
						continue
					}
				}
			}

			// Calculate target value
			targetValue := diff * ctx.TotalPortfolioValueEUR
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

			valueEUR := float64(quantity) * currentPrice
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

			if totalCostEUR > ctx.AvailableCashEUR {
				continue
			}

			priority := abs(diff) * 0.8

			// Boost priority if also has opportunity tags (opportunistic deviation)
			// Apply soft filters for quantum warnings (reduce priority, don't exclude)
			if c.securityRepo != nil {
				securityTags, err := c.securityRepo.GetTagsForSecurity(symbol)
				if err == nil {
					// Soft filter: reduce priority for quantum warnings
					if contains(securityTags, "quantum-bubble-warning") {
						priority *= 0.7 // Reduce by 30%
					}
					if contains(securityTags, "quantum-value-warning") {
						priority *= 0.7 // Reduce by 30%
					}

					// Boost if also a value opportunity or quality value
					if contains(securityTags, "quality-value") {
						priority *= 1.3 // 30% boost for quality value + optimizer alignment
					} else if contains(securityTags, "value-opportunity") || contains(securityTags, "high-quality") {
						priority *= 1.15 // 15% boost for opportunity + optimizer alignment
					}
					// Add optimizer-aligned tag if underweight
					if contains(securityTags, "underweight") || contains(securityTags, "slightly-underweight") {
						// Already underweight - this is optimizer-aligned
					}
				}
			}

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (underweight by %.1f%%)",
				d.target*100, d.current*100, diff*100)

			tags := []string{"weight_based", "buy", "underweight", "optimizer-aligned"}

			candidate := planningdomain.ActionCandidate{
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
			buyCount++

		} else {
			// Need to SELL (overweight)
			if !ctx.AllowSell || sellCount >= maxSellPositions {
				continue
			}
			if ctx.IneligibleSymbols[symbol] || ctx.RecentlySold[symbol] {
				continue
			}

			// Find position
			var foundPosition *domain.Position
			for i := range ctx.Positions {
				if ctx.Positions[i].Symbol == symbol {
					pos := ctx.Positions[i]
					foundPosition = &pos
					break
				}
			}
			if foundPosition == nil {
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

			valueEUR := float64(quantity) * currentPrice
			transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
			netValueEUR := valueEUR - transactionCost

			priority := abs(diff) * 0.8

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (overweight by %.1f%%)",
				d.target*100, d.current*100, abs(diff)*100)

			tags := []string{"weight_based", "sell", "overweight"}

			candidate := planningdomain.ActionCandidate{
				Side:     "SELL",
				Symbol:   symbol,
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
		Msg("Weight-based opportunities identified")

	return candidates, nil
}

// abs returns the absolute value of a float64.
func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
