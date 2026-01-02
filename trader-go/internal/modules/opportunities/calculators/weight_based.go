package calculators

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// WeightBasedCalculator identifies buy/sell opportunities based on optimizer target weights.
type WeightBasedCalculator struct {
	*BaseCalculator
}

// NewWeightBasedCalculator creates a new weight-based calculator.
func NewWeightBasedCalculator(log zerolog.Logger) *WeightBasedCalculator {
	return &WeightBasedCalculator{
		BaseCalculator: NewBaseCalculator(log, "weight_based"),
	}
}

// Name returns the calculator name.
func (c *WeightBasedCalculator) Name() string {
	return "weight_based"
}

// Category returns the opportunity category.
func (c *WeightBasedCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryWeightBased
}

// Calculate identifies weight-based opportunities (both buys and sells).
func (c *WeightBasedCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minWeightDiff := GetFloatParam(params, "min_weight_diff", 0.02)       // 2% minimum difference
	maxValuePerTrade := GetFloatParam(params, "max_value_per_trade", 500.0)
	maxBuyPositions := GetIntParam(params, "max_buy_positions", 5)
	maxSellPositions := GetIntParam(params, "max_sell_positions", 5)

	// Check if we have target weights
	if ctx.TargetWeights == nil || len(ctx.TargetWeights) == 0 {
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
		symbol      string
		current     float64
		target      float64
		diff        float64
		absSignal   float64 // Absolute difference (for sorting)
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

	var candidates []domain.ActionCandidate
	buyCount := 0
	sellCount := 0

	for _, d := range diffs {
		symbol := d.symbol
		diff := d.diff

		// Get security info
		security, ok := ctx.StocksBySymbol[symbol]
		if !ok {
			c.log.Warn().
				Str("symbol", symbol).
				Msg("Security not found")
			continue
		}

		// Get current price
		currentPrice, ok := ctx.CurrentPrices[symbol]
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", symbol).
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

			if totalCostEUR > ctx.AvailableCashEUR {
				continue
			}

			priority := abs(diff) * 0.8

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (underweight by %.1f%%)",
				d.target*100, d.current*100, diff*100)

			tags := []string{"weight_based", "buy", "underweight"}

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
			var position *domain.Position
			for i := range ctx.Positions {
				if ctx.Positions[i].Symbol == symbol {
					position = &ctx.Positions[i]
					break
				}
			}
			if position == nil {
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
			if quantity > position.Quantity {
				quantity = position.Quantity
			}

			valueEUR := float64(quantity) * currentPrice
			transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
			netValueEUR := valueEUR - transactionCost

			priority := abs(diff) * 0.8

			reason := fmt.Sprintf("Target weight: %.1f%%, current: %.1f%% (overweight by %.1f%%)",
				d.target*100, d.current*100, abs(diff)*100)

			tags := []string{"weight_based", "sell", "overweight"}

			candidate := domain.ActionCandidate{
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

func init() {
	// Auto-register on import
	DefaultCalculatorRegistry.Register(NewWeightBasedCalculator(zerolog.Nop()))
}
