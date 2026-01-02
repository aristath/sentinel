package calculators

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// ProfitTakingCalculator identifies opportunities to take profits from positions with gains.
type ProfitTakingCalculator struct {
	*BaseCalculator
}

// NewProfitTakingCalculator creates a new profit taking calculator.
func NewProfitTakingCalculator(log zerolog.Logger) *ProfitTakingCalculator {
	return &ProfitTakingCalculator{
		BaseCalculator: NewBaseCalculator(log, "profit_taking"),
	}
}

// Name returns the calculator name.
func (c *ProfitTakingCalculator) Name() string {
	return "profit_taking"
}

// Category returns the opportunity category.
func (c *ProfitTakingCalculator) Category() domain.OpportunityCategory {
	return domain.OpportunityCategoryProfitTaking
}

// Calculate identifies profit-taking opportunities.
func (c *ProfitTakingCalculator) Calculate(
	ctx *domain.OpportunityContext,
	params map[string]interface{},
) ([]domain.ActionCandidate, error) {
	// Parameters with defaults
	minGainThreshold := GetFloatParam(params, "min_gain_threshold", 0.15)     // 15% minimum gain
	windfallThreshold := GetFloatParam(params, "windfall_threshold", 0.30)    // 30% for windfall
	minHoldDays := GetIntParam(params, "min_hold_days", 90)                   // Minimum holding period
	sellPercentage := GetFloatParam(params, "sell_percentage", 1.0)           // Sell 100% by default
	maxPositions := GetIntParam(params, "max_positions", 0)                   // 0 = unlimited

	if !ctx.AllowSell {
		c.log.Debug().Msg("Selling not allowed, skipping profit taking")
		return nil, nil
	}

	var candidates []domain.ActionCandidate

	c.log.Debug().
		Float64("min_gain_threshold", minGainThreshold).
		Float64("windfall_threshold", windfallThreshold).
		Int("min_hold_days", minHoldDays).
		Msg("Calculating profit-taking opportunities")

	for _, position := range ctx.Positions {
		// Skip if ineligible
		if ctx.IneligibleSymbols[position.Symbol] {
			continue
		}

		// Skip if recently sold
		if ctx.RecentlySold[position.Symbol] {
			continue
		}

		// Get current price
		currentPrice, ok := ctx.CurrentPrices[position.Symbol]
		if !ok || currentPrice <= 0 {
			c.log.Warn().
				Str("symbol", position.Symbol).
				Msg("No current price available")
			continue
		}

		// Calculate gain
		costBasis := position.AverageCost
		if costBasis <= 0 {
			continue
		}

		gainPercent := (currentPrice - costBasis) / costBasis

		// Check if gain meets threshold
		if gainPercent < minGainThreshold {
			continue
		}

		// Get security info
		security, ok := ctx.StocksBySymbol[position.Symbol]
		if !ok {
			continue
		}

		// Determine if windfall
		isWindfall := gainPercent >= windfallThreshold

		// Calculate quantity to sell
		quantity := position.Quantity
		if sellPercentage < 1.0 {
			quantity = int(float64(position.Quantity) * sellPercentage)
			if quantity == 0 {
				quantity = 1
			}
		}

		// Calculate value
		valueEUR := float64(quantity) * currentPrice

		// Apply transaction costs
		transactionCost := ctx.TransactionCostFixed + (valueEUR * ctx.TransactionCostPercent)
		netValueEUR := valueEUR - transactionCost

		// Calculate priority (higher gain = higher priority)
		priority := gainPercent

		// Windfall gets extra priority boost
		if isWindfall {
			priority *= 1.5
		}

		// Build reason
		reason := fmt.Sprintf("%.1f%% gain (cost basis: %.2f, current: %.2f)",
			gainPercent*100, costBasis, currentPrice)

		if isWindfall {
			reason = fmt.Sprintf("Windfall: %s", reason)
		}

		// Build tags
		tags := []string{"profit_taking"}
		if isWindfall {
			tags = append(tags, "windfall")
		}

		candidate := domain.ActionCandidate{
			Side:     "SELL",
			Symbol:   position.Symbol,
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
	}

	// Limit to max positions if specified
	if maxPositions > 0 && len(candidates) > maxPositions {
		// Sort by priority (descending) and take top N
		// For now, just truncate (sorting will be done by caller)
		candidates = candidates[:maxPositions]
	}

	c.log.Info().
		Int("candidates", len(candidates)).
		Msg("Profit-taking opportunities identified")

	return candidates, nil
}

func init() {
	// Auto-register on import
	// Will be replaced with actual logger when registry is initialized
	DefaultCalculatorRegistry.Register(NewProfitTakingCalculator(zerolog.Nop()))
}
