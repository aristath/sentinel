// Package calculators provides opportunity identification calculators for portfolio management.
package calculators

import (
	"math"
	"sort"

	"github.com/aristath/sentinel/internal/modules/planning/domain"
)

// MaxSellPercentageAbsolute is the absolute maximum percentage of any position
// that can be sold in a single recommendation. This prevents selling 100% of a position.
const MaxSellPercentageAbsolute = 0.80

// GeographySellPlan represents a calculated sell plan for an overweight geography.
// It distributes the required reduction across positions based on quality scoring.
type GeographySellPlan struct {
	// Geography is the overweight geography (e.g., "US", "Europe")
	Geography string

	// OverweightPercent is the amount by which the geography exceeds its target (e.g., 0.10 = 10% overweight)
	OverweightPercent float64

	// TotalValueToReduce is the total EUR value that needs to be sold to reach target allocation
	TotalValueToReduce float64

	// PositionSells contains the individual sell plans for each position
	PositionSells []PositionSellPlan
}

// PositionSellPlan represents the calculated sell for a single position.
type PositionSellPlan struct {
	// ISIN is the primary identifier for the position
	ISIN string

	// Symbol is the trading symbol
	Symbol string

	// Name is the security name
	Name string

	// CurrentValueEUR is the current market value of the position in EUR
	CurrentValueEUR float64

	// SellQuantity is the number of shares to sell
	SellQuantity int

	// SellValueEUR is the estimated EUR value of the sell
	SellValueEUR float64

	// SellPercentage is the percentage of the position being sold (0.0-1.0)
	SellPercentage float64

	// QualityPriority is the quality-based priority (higher = more likely to sell)
	QualityPriority float64
}

// CalculateGeographySellPlan calculates optimal sell quantities for an overweight geography.
//
// Algorithm:
// 1. Calculate total value to reduce: overweightPercent * portfolioValue
// 2. Sort positions by sell priority (low quality first, using SortPositionsBySellPriority)
// 3. For each position:
//   - Cap at min(maxSellPercentage, MaxSellPercentageAbsolute) of position
//   - Calculate proportional share of reduction
//   - Apply quality-based priority adjustment
//   - Round to lot size
//
// 4. Return plan with all position sells
//
// This replaces the incorrect formula: sellPercentage = overweight / (overweight + threshold)
// which incorrectly approached 100% regardless of actual reduction needs.
func CalculateGeographySellPlan(
	geography string,
	overweightPercent float64,
	positions []domain.EnrichedPosition,
	ctx *domain.OpportunityContext,
	maxSellPercentage float64,
	securityRepo SecurityRepository,
	config *domain.PlannerConfiguration,
) (*GeographySellPlan, error) {
	plan := &GeographySellPlan{
		Geography:          geography,
		OverweightPercent:  overweightPercent,
		TotalValueToReduce: 0,
		PositionSells:      []PositionSellPlan{},
	}

	// Handle empty positions
	if len(positions) == 0 {
		return plan, nil
	}

	// Handle nil context
	if ctx == nil {
		return plan, nil
	}

	// Calculate total value to reduce from this geography
	plan.TotalValueToReduce = overweightPercent * ctx.TotalPortfolioValueEUR

	// If nothing to reduce, return empty plan
	if plan.TotalValueToReduce <= 0 {
		return plan, nil
	}

	// Calculate total position value in this geography
	// Note: MarketValueEUR might not be set, so calculate from price * quantity as fallback
	totalPositionValue := 0.0
	for _, pos := range positions {
		marketValue := pos.MarketValueEUR
		if marketValue <= 0 && pos.CurrentPrice > 0 && pos.Quantity > 0 {
			marketValue = pos.Quantity * pos.CurrentPrice
		}
		totalPositionValue += marketValue
	}

	// If no value in positions, return empty plan
	if totalPositionValue <= 0 {
		return plan, nil
	}

	// Sort positions by sell priority (low quality first)
	sortedPositions := SortPositionsBySellPriority(positions, ctx, securityRepo, config)

	// Calculate effective max sell percentage (respect both config and absolute limit)
	effectiveMaxSell := math.Min(maxSellPercentage, MaxSellPercentageAbsolute)

	// Track remaining value to reduce
	remainingToReduce := plan.TotalValueToReduce

	// Process each position
	for _, pos := range sortedPositions {
		if remainingToReduce <= 0 {
			break
		}

		// Skip positions that can't be sold
		if !pos.AllowSell {
			continue
		}

		// Skip positions with zero quantity or price
		if pos.Quantity <= 0 || pos.CurrentPrice <= 0 {
			continue
		}

		// Calculate market value (fallback to price * quantity if not set)
		marketValue := pos.MarketValueEUR
		if marketValue <= 0 {
			marketValue = pos.Quantity * pos.CurrentPrice
		}

		// Calculate maximum sellable value for this position
		maxSellValue := marketValue * effectiveMaxSell
		_ = int(pos.Quantity * effectiveMaxSell) // Reserved for future use

		// Calculate proportional share of reduction for this position
		positionShare := marketValue / totalPositionValue
		targetSellValue := plan.TotalValueToReduce * positionShare

		// Get quality score for priority adjustment
		var qualityPriority float64 = 1.0
		if securityRepo != nil {
			tags, _ := securityRepo.GetTagsForSecurity(pos.Symbol)
			qualityScore := CalculateSellQualityScore(ctx, pos.ISIN, tags, config)
			qualityPriority = qualityScore.SellPriorityBoost
		}

		// Adjust target by quality priority (higher priority = sell more)
		adjustedSellValue := targetSellValue * qualityPriority

		// Cap at maximum sellable value
		actualSellValue := math.Min(adjustedSellValue, maxSellValue)

		// Cap at remaining value to reduce
		actualSellValue = math.Min(actualSellValue, remainingToReduce)

		// Convert to quantity
		quantity := int(actualSellValue / pos.CurrentPrice)

		// Round to lot size
		if pos.MinLot > 1 {
			quantity = RoundToLotSize(quantity, pos.MinLot)
		}

		// Skip if quantity is zero after rounding
		if quantity <= 0 {
			continue
		}

		// Ensure we don't exceed max sell percentage after rounding
		if float64(quantity) > pos.Quantity*effectiveMaxSell {
			quantity = int(pos.Quantity * effectiveMaxSell)
			if pos.MinLot > 1 {
				quantity = (quantity / pos.MinLot) * pos.MinLot // Round down to lot size
			}
		}

		// Skip if still zero
		if quantity <= 0 {
			continue
		}

		// Calculate final values
		sellValue := float64(quantity) * pos.CurrentPrice
		sellPercentage := float64(quantity) / pos.Quantity

		// Create position sell plan
		posSell := PositionSellPlan{
			ISIN:            pos.ISIN,
			Symbol:          pos.Symbol,
			Name:            pos.SecurityName,
			CurrentValueEUR: pos.MarketValueEUR,
			SellQuantity:    quantity,
			SellValueEUR:    sellValue,
			SellPercentage:  sellPercentage,
			QualityPriority: qualityPriority,
		}

		plan.PositionSells = append(plan.PositionSells, posSell)

		// Update remaining value to reduce
		remainingToReduce -= sellValue
	}

	return plan, nil
}

// SortPositionsBySellPriority sorts positions for selling based on quality.
// Low quality positions come first (highest priority to sell).
// High quality positions come last (should be protected).
func SortPositionsBySellPriority(
	positions []domain.EnrichedPosition,
	ctx *domain.OpportunityContext,
	securityRepo SecurityRepository,
	config *domain.PlannerConfiguration,
) []domain.EnrichedPosition {
	if len(positions) == 0 {
		return positions
	}

	// Create scored positions
	type scoredPosition struct {
		position domain.EnrichedPosition
		priority float64 // Higher = sell first
	}

	scored := make([]scoredPosition, len(positions))
	for i, pos := range positions {
		var priority float64 = 1.0

		// Get quality-based priority
		if ctx != nil {
			var tags []string
			if securityRepo != nil {
				tags, _ = securityRepo.GetTagsForSecurity(pos.Symbol)
			}
			qualityScore := CalculateSellQualityScore(ctx, pos.ISIN, tags, config)
			priority = qualityScore.SellPriorityBoost
		}

		scored[i] = scoredPosition{
			position: pos,
			priority: priority,
		}
	}

	// Sort by priority descending (higher = sell first)
	sort.Slice(scored, func(i, j int) bool {
		return scored[i].priority > scored[j].priority
	})

	// Extract sorted positions
	result := make([]domain.EnrichedPosition, len(positions))
	for i, sp := range scored {
		result[i] = sp.position
	}

	return result
}
