package calculators

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// AveragingDownCalculator identifies opportunities to average down on underperforming positions.
type AveragingDownCalculator struct {
	*BaseCalculator
}

// NewAveragingDownCalculator creates a new averaging down calculator.
func NewAveragingDownCalculator(log zerolog.Logger) *AveragingDownCalculator {
	return &AveragingDownCalculator{
		BaseCalculator: NewBaseCalculator(log, "averaging_down"),
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
	minLossThreshold := GetFloatParam(params, "min_loss_threshold", -0.10) // -10% minimum loss
	maxLossThreshold := GetFloatParam(params, "max_loss_threshold", -0.30) // -30% maximum loss (safety)
	minScore := GetFloatParam(params, "min_score", 0.6)                    // Minimum security score
	maxValuePerPosition := GetFloatParam(params, "max_value_per_position", 500.0)
	maxPositions := GetIntParam(params, "max_positions", 0) // 0 = unlimited

	// Calculate minimum trade amount based on transaction costs (default: 1% max cost ratio)
	maxCostRatio := GetFloatParam(params, "max_cost_ratio", 0.01) // Default 1% max cost
	minTradeAmount := ctx.CalculateMinTradeAmount(maxCostRatio)

	if !ctx.AllowBuy {
		c.log.Debug().Msg("Buying not allowed, skipping averaging down")
		return nil, nil
	}

	if ctx.AvailableCashEUR <= minTradeAmount {
		c.log.Debug().
			Float64("available_cash", ctx.AvailableCashEUR).
			Float64("min_trade_amount", minTradeAmount).
			Msg("No available cash (below minimum trade amount), skipping averaging down")
		return nil, nil
	}

	var candidates []domain.ActionCandidate

	c.log.Debug().
		Float64("min_loss_threshold", minLossThreshold).
		Float64("max_loss_threshold", maxLossThreshold).
		Float64("min_score", minScore).
		Msg("Calculating averaging-down opportunities")

	for _, position := range ctx.Positions {
		// Use ISIN if available, otherwise fallback to symbol
		isin := position.ISIN
		if isin == "" {
			isin = position.Symbol // Fallback for CASH positions
		}

		// Skip if recently bought
		if ctx.RecentlyBought[position.Symbol] {
			continue
		}

		// Get security info (try ISIN first, fallback to symbol)
		security, ok := ctx.GetSecurityByISINOrSymbol(isin, position.Symbol)
		if !ok {
			continue
		}

		// Get current price (try ISIN first, fallback to symbol)
		currentPrice, ok := ctx.GetPriceByISINOrSymbol(isin, position.Symbol)
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", position.Symbol).
				Str("isin", isin).
				Msg("No current price available")
			continue
		}

		// Calculate loss
		costBasis := position.AverageCost
		if costBasis <= 0 {
			continue
		}

		lossPercent := (currentPrice - costBasis) / costBasis

		// Check if loss is in the averaging-down range
		if lossPercent >= minLossThreshold || lossPercent <= maxLossThreshold {
			continue // Either not enough loss, or too much loss (safety)
		}

		// Check security score if available
		if ctx.SecurityScores != nil {
			if score, ok := ctx.SecurityScores[position.Symbol]; ok {
				if score < minScore {
					c.log.Debug().
						Str("symbol", position.Symbol).
						Float64("score", score).
						Float64("min_score", minScore).
						Msg("Security score too low for averaging down")
					continue
				}
			}
		}

		// Calculate quantity to buy (aim for ~10% increase in position size)
		targetIncrease := float64(position.Quantity) * 0.10
		if targetIncrease < 1 {
			targetIncrease = 1
		}

		quantity := int(targetIncrease)
		if quantity == 0 {
			quantity = 1
		}

		// Calculate value
		valueEUR := float64(quantity) * currentPrice

		// Limit to max value per position
		if valueEUR > maxValuePerPosition {
			quantity = int(maxValuePerPosition / currentPrice)
			if quantity == 0 {
				quantity = 1
			}
			valueEUR = float64(quantity) * currentPrice
		}

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

		// Calculate priority (greater loss = higher priority, but capped)
		// Normalize loss to 0-1 range
		normalizedLoss := (lossPercent - maxLossThreshold) / (minLossThreshold - maxLossThreshold)
		priority := normalizedLoss * 0.7 // Scale down relative to other opportunities

		// Build reason
		reason := fmt.Sprintf("%.1f%% loss (cost basis: %.2f, current: %.2f) - averaging down",
			lossPercent*100, costBasis, currentPrice)

		// Build tags
		tags := []string{"averaging_down", "value_opportunity"}

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

	// Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Msg("Averaging-down opportunities identified")

	return candidates, nil
}
