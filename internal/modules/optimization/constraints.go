// Package optimization provides portfolio optimization functionality.
package optimization

import (
	"fmt"
	"math"

	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/utils"
	"github.com/rs/zerolog"
)

// Constants (from Python scoring module)
const (
	MaxConcentration          = 0.20 // 20% max per security
	MaxGeographyConcentration = 0.40 // 40% max per geography
	MaxSectorConcentration    = 0.30 // 30% max per industry
	GeoAllocationTolerance    = 0.05 // ±5% from target
	IndAllocationTolerance    = 0.05 // ±5% from target
)

// ConstraintsManager translates business rules into optimization constraints.
type ConstraintsManager struct {
	maxConcentration float64
	geoTolerance     float64
	indTolerance     float64
	kellySizer       *KellyPositionSizer // Optional: Kelly sizing for upper bounds
	log              zerolog.Logger
}

// NewConstraintsManager creates a new constraints manager.
func NewConstraintsManager(log zerolog.Logger) *ConstraintsManager {
	return &ConstraintsManager{
		maxConcentration: MaxConcentration,
		geoTolerance:     GeoAllocationTolerance,
		indTolerance:     IndAllocationTolerance,
		log:              log.With().Str("component", "constraints").Logger(),
	}
}

// SetKellySizer sets the Kelly position sizer for optimal sizing.
func (cm *ConstraintsManager) SetKellySizer(kellySizer *KellyPositionSizer) {
	cm.kellySizer = kellySizer
}

// BuildConstraints builds all constraints for optimization.
// ALL PARAMETERS USE ISIN KEYS (not Symbol keys).
func (cm *ConstraintsManager) BuildConstraints(
	securities []Security,
	positions map[string]Position, // ISIN-keyed ✅
	geographyTargets map[string]float64,
	industryTargets map[string]float64,
	portfolioValue float64,
	currentPrices map[string]float64, // ISIN-keyed ✅
	expectedReturns map[string]float64, // ISIN-keyed ✅
	covMatrix [][]float64,
	isins []string, // ISIN array ✅ (renamed from symbols)
	regimeScore float64,
) (Constraints, error) {
	// Calculate weight bounds for each security (returns ISIN-keyed maps)
	minWeights, maxWeights, isins := cm.calculateWeightBounds(
		securities,
		positions, // ISIN-keyed ✅
		portfolioValue,
		currentPrices,   // ISIN-keyed ✅
		expectedReturns, // ISIN-keyed ✅
		covMatrix,
		isins, // ISIN array ✅
		regimeScore,
	)

	// Build sector constraints (uses ISIN keys)
	geoCons, industryCons := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Scale constraints if needed
	geoCons, industryCons = cm.scaleConstraints(geoCons, industryCons)

	constraints := Constraints{
		ISINs:             isins,      // ISIN array ✅
		MinWeights:        minWeights, // ISIN-keyed ✅
		MaxWeights:        maxWeights, // ISIN-keyed ✅
		SectorConstraints: append(geoCons, industryCons...),
	}

	return constraints, nil
}

// calculateWeightBounds calculates weight bounds for each security.
// Returns ISIN-keyed maps for min/max weights, and ISIN array.
func (cm *ConstraintsManager) calculateWeightBounds(
	securities []Security,
	positions map[string]Position, // ISIN-keyed ✅
	portfolioValue float64,
	currentPrices map[string]float64, // ISIN-keyed ✅
	expectedReturns map[string]float64, // ISIN-keyed ✅
	covMatrix [][]float64,
	isins []string, // ISIN array ✅
	regimeScore float64,
) (map[string]float64, map[string]float64, []string) {
	minWeights := make(map[string]float64)
	maxWeights := make(map[string]float64)
	constraintISINs := make([]string, 0, len(securities))

	cm.log.Debug().
		Int("num_securities", len(securities)).
		Float64("portfolio_value", portfolioValue).
		Msg("Calculating weight bounds")

	for _, security := range securities {
		isin := security.ISIN                    // Use ISIN ✅
		symbol := security.Symbol                // Keep Symbol for logging only
		position, hasPosition := positions[isin] // ISIN lookup ✅
		currentPrice := currentPrices[isin]      // ISIN lookup ✅

		// Calculate current weight
		var currentWeight float64
		if hasPosition && position.ValueEUR > 0 && portfolioValue > 0 {
			currentWeight = position.ValueEUR / portfolioValue
		}

		// Default bounds - use product-type-aware concentration limit
		lower := 0.0
		upper := cm.getMaxConcentration(security.ProductType)

		// If Kelly sizing is enabled, use Kelly-optimal size as upper bound (but still respect max concentration)
		if cm.kellySizer != nil && expectedReturns != nil && covMatrix != nil && len(isins) > 0 {
			// Use default confidence of 0.5 (moderate confidence)
			// In future enhancements, this could be derived from security scores
			confidence := 0.5

			// Use ISIN-based API
			kellySize, err := cm.kellySizer.CalculateOptimalSizeForISIN(
				isin,            // Use ISIN ✅
				expectedReturns, // ISIN-keyed ✅
				covMatrix,
				isins, // ISIN array ✅
				confidence,
				regimeScore,
			)
			if err == nil && kellySize > 0 {
				// Use Kelly size as upper bound, but cap at max concentration
				upper = math.Min(kellySize, upper)
				cm.log.Debug().
					Str("isin", isin).     // Log ISIN ✅
					Str("symbol", symbol). // Also log Symbol for readability
					Float64("kelly_size", kellySize).
					Float64("max_concentration", cm.getMaxConcentration(security.ProductType)).
					Float64("final_upper", upper).
					Msg("Using Kelly-optimal size as upper bound")
			}
		}

		// Apply user-defined portfolio targets (convert percentage to fraction)
		if security.MinPortfolioTarget > 0 {
			lower = security.MinPortfolioTarget / 100.0
		}

		if security.MaxPortfolioTarget > 0 {
			upper = security.MaxPortfolioTarget / 100.0
		}

		// Check allow_buy constraint
		if !security.AllowBuy {
			// Can't buy more, so upper bound = current weight
			upper = math.Min(upper, currentWeight)
		}

		// Check allow_sell constraint
		if !security.AllowSell {
			// Can't sell, so lower bound = current weight
			lower = math.Max(lower, currentWeight)
		}

		// Check min_lot constraint
		if hasPosition && security.MinLot > 0 && currentPrice > 0 {
			if position.Quantity <= security.MinLot {
				// Can't partially sell - it's all or nothing
				// Set lower bound to current weight (can't reduce)
				lower = math.Max(lower, currentWeight)
			} else {
				// Can sell down to min_lot worth
				minLotValue := security.MinLot * currentPrice
				minWeight := 0.0
				if portfolioValue > 0 {
					minWeight = minLotValue / portfolioValue
				}

				// Check if min_lot constraint would violate upper bound
				if minWeight > upper {
					cm.log.Warn().
						Str("symbol", symbol).
						Float64("min_weight", minWeight).
						Float64("upper", upper).
						Float64("min_lot", security.MinLot).
						Msg("min_lot constraint would create infeasible bounds - ignoring")
				} else {
					lower = math.Max(lower, minWeight)
				}
			}
		}

		// Ensure lower <= upper
		if lower > upper {
			// Constraint conflict - keep current weight
			cm.log.Warn().
				Str("isin", isin).     // Log ISIN ✅
				Str("symbol", symbol). // Also log Symbol for readability
				Float64("lower", lower).
				Float64("upper", upper).
				Float64("current_weight", currentWeight).
				Msg("Constraint conflict detected - using current weight for both bounds")
			lower = currentWeight
			upper = currentWeight
		}

		// Store in ISIN-keyed maps ✅
		constraintISINs = append(constraintISINs, isin)
		minWeights[isin] = lower // ISIN key ✅
		maxWeights[isin] = upper // ISIN key ✅
	}

	return minWeights, maxWeights, constraintISINs
}

// buildSectorConstraints builds geography and industry sector constraints.
// Uses ISIN keys in SectorMapper.
// geographyTargets and industryTargets are raw weights that get normalized internally.
func (cm *ConstraintsManager) buildSectorConstraints(
	securities []Security,
	geographyTargets map[string]float64,
	industryTargets map[string]float64,
) ([]SectorConstraint, []SectorConstraint) {
	// Normalize targets for constraint building
	normalizedGeographyTargets := allocation.NormalizeWeights(geographyTargets)
	normalizedIndustryTargets := allocation.NormalizeWeights(industryTargets)

	// Group securities by geography (use ISINs)
	// Parse comma-separated geographies so securities can belong to multiple groups
	geographyGroups := make(map[string][]string)
	for _, security := range securities {
		geographies := utils.ParseCSV(security.Geography)
		if len(geographies) == 0 {
			geographies = []string{"OTHER"}
		}
		for _, geography := range geographies {
			geographyGroups[geography] = append(geographyGroups[geography], security.ISIN)
		}
	}

	cm.log.Info().
		Int("num_geography_groups", len(geographyGroups)).
		Msg("Grouped securities by geography")

	// Group securities by industry (use ISINs)
	// Parse comma-separated industries so securities can belong to multiple groups
	industryGroups := make(map[string][]string)
	for _, security := range securities {
		industries := utils.ParseCSV(security.Industry)
		if len(industries) == 0 {
			industries = []string{"OTHER"}
		}
		for _, industry := range industries {
			industryGroups[industry] = append(industryGroups[industry], security.ISIN)
		}
	}

	cm.log.Info().
		Int("num_industry_groups", len(industryGroups)).
		Msg("Grouped securities by industry")

	// Build geography constraints
	geographyConstraints := make([]SectorConstraint, 0)
	for geography, isins := range geographyGroups { // Renamed from symbols
		target := normalizedGeographyTargets[geography]
		if target > 0 {
			// Calculate tolerance-based bounds
			toleranceUpper := math.Min(1.0, target+cm.geoTolerance)
			// Enforce hard limit: cap at MaxGeographyConcentration
			hardUpper := math.Min(toleranceUpper, MaxGeographyConcentration)

			mapper := make(map[string]string)
			for _, isin := range isins { // Use ISIN ✅
				mapper[isin] = geography // ISIN → geography ✅
			}

			geographyConstraints = append(geographyConstraints, SectorConstraint{
				SectorMapper: mapper,
				SectorLower:  map[string]float64{geography: math.Max(0.0, target-cm.geoTolerance)},
				SectorUpper:  map[string]float64{geography: hardUpper},
			})
		}
	}

	// Scale down geography constraint upper bounds if they sum to > 100%
	if len(geographyConstraints) > 0 {
		geographyMaxSum := 0.0
		for _, c := range geographyConstraints {
			for _, upper := range c.SectorUpper {
				geographyMaxSum += upper
			}
		}

		if geographyMaxSum > 1.0 {
			cm.log.Warn().
				Float64("geography_max_sum", geographyMaxSum).
				Msg("Geography constraint upper bounds sum > 100% - scaling down proportionally")

			scaleFactor := 1.0 / geographyMaxSum
			for i := range geographyConstraints {
				for name, upper := range geographyConstraints[i].SectorUpper {
					newUpper := upper * scaleFactor
					// Ensure upper is still >= lower
					lower := geographyConstraints[i].SectorLower[name]
					geographyConstraints[i].SectorUpper[name] = math.Max(newUpper, lower)
				}
			}
		}
	}

	// Build industry constraints
	// Count industries with targets
	numIndustryConstraints := 0
	for industry := range industryGroups {
		if normalizedIndustryTargets[industry] > 0 {
			numIndustryConstraints++
		}
	}

	// Adjust max concentration based on number of industries
	effectiveMaxConcentration := MaxSectorConcentration
	if numIndustryConstraints == 1 {
		effectiveMaxConcentration = 0.70 // 70% for single industry
	} else if numIndustryConstraints == 2 {
		effectiveMaxConcentration = 0.50 // 50% each for 2 industries
	} else if numIndustryConstraints <= 4 {
		effectiveMaxConcentration = 0.40 // 40% for 3-4 industries
		cm.log.Info().
			Int("num_industry_constraints", numIndustryConstraints).
			Msg("Using 40% max concentration for industry groups")
	}

	industryConstraints := make([]SectorConstraint, 0)
	for industry, isins := range industryGroups { // Renamed from symbols
		target := normalizedIndustryTargets[industry]
		if target > 0 {
			// Calculate tolerance-based bounds
			toleranceUpper := math.Min(1.0, target+cm.indTolerance)
			// Enforce hard limit: cap at effectiveMaxConcentration
			hardUpper := math.Min(toleranceUpper, effectiveMaxConcentration)

			mapper := make(map[string]string)
			for _, isin := range isins { // Use ISIN ✅
				mapper[isin] = industry // ISIN → industry ✅
			}

			industryConstraints = append(industryConstraints, SectorConstraint{
				SectorMapper: mapper,
				SectorLower:  map[string]float64{industry: math.Max(0.0, target-cm.indTolerance)},
				SectorUpper:  map[string]float64{industry: hardUpper},
			})
		}
	}

	cm.log.Info().
		Int("geography_constraints", len(geographyConstraints)).
		Int("industry_constraints", len(industryConstraints)).
		Msg("Built sector constraints")

	return geographyConstraints, industryConstraints
}

// getMaxConcentration returns the maximum concentration limit based on product type
// Implements product-type-aware concentration limits as per PRODUCT_TYPE_DIFFERENTIATION.md
func (cm *ConstraintsManager) getMaxConcentration(productType string) float64 {
	switch productType {
	case "EQUITY":
		return 0.20 // 20% max for individual stocks
	case "ETF", "MUTUALFUND":
		// Treat ETFs and Mutual Funds identically (both are diversified products)
		// For now, use 0.30 (30%) for all diversified products
		// Future: Detect broad-market vs sector/country ETFs
		return 0.30
	case "ETC":
		return 0.12 // 12% max for commodities (different asset class, lower for retirement funds)
	default:
		return 0.20 // Default to 20% for UNKNOWN or other types
	}
}

// scaleConstraints scales down minimums if too restrictive.
func (cm *ConstraintsManager) scaleConstraints(
	geographyConstraints []SectorConstraint,
	industryConstraints []SectorConstraint,
) ([]SectorConstraint, []SectorConstraint) {
	// Calculate sums
	indMinSum := 0.0
	for _, c := range industryConstraints {
		for _, lower := range c.SectorLower {
			indMinSum += lower
		}
	}

	geographyMinSum := 0.0
	for _, c := range geographyConstraints {
		for _, lower := range c.SectorLower {
			geographyMinSum += lower
		}
	}

	totalMinSum := geographyMinSum + indMinSum

	// Scale down if industry minimums alone exceed 100%
	if indMinSum > 1.0 {
		cm.log.Warn().
			Float64("ind_min_sum", indMinSum).
			Msg("Industry constraint minimums sum > 100% - scaling down")

		scaleFactor := 1.0 / indMinSum
		for i := range industryConstraints {
			for name, lower := range industryConstraints[i].SectorLower {
				newLower := lower * scaleFactor
				upper := industryConstraints[i].SectorUpper[name]
				industryConstraints[i].SectorLower[name] = math.Min(newLower, upper)
			}
		}
	} else if totalMinSum > 0.70 {
		// Scale both geography and industry minimums proportionally if combined > 70%
		cm.log.Warn().
			Float64("geography_min_sum", geographyMinSum).
			Float64("ind_min_sum", indMinSum).
			Float64("total_min_sum", totalMinSum).
			Msg("Combined minimums > 70% - scaling down both proportionally to 60%")

		scaleFactor := 0.60 / totalMinSum
		for i := range geographyConstraints {
			for name, lower := range geographyConstraints[i].SectorLower {
				newLower := lower * scaleFactor
				upper := geographyConstraints[i].SectorUpper[name]
				geographyConstraints[i].SectorLower[name] = math.Min(newLower, upper)
			}
		}
		for i := range industryConstraints {
			for name, lower := range industryConstraints[i].SectorLower {
				newLower := lower * scaleFactor
				upper := industryConstraints[i].SectorUpper[name]
				industryConstraints[i].SectorLower[name] = math.Min(newLower, upper)
			}
		}
	}

	return geographyConstraints, industryConstraints
}

// GetConstraintSummary generates a summary of constraints for diagnostics.
func (cm *ConstraintsManager) GetConstraintSummary(
	constraints Constraints,
) ConstraintsSummary {
	totalSecurities := len(constraints.ISINs) // Use ISINs ✅
	securitiesWithBounds := 0
	totalMinWeight := 0.0
	totalMaxWeight := 0.0

	// Iterate over ISIN-keyed maps ✅
	for _, isin := range constraints.ISINs {
		minWeight := constraints.MinWeights[isin]
		maxWeight := constraints.MaxWeights[isin]
		if minWeight > 0 || maxWeight < cm.maxConcentration {
			securitiesWithBounds++
		}
		totalMinWeight += minWeight
		totalMaxWeight += maxWeight
	}

	// Count sector constraints
	geographyConstraintCount := 0
	for _, sc := range constraints.SectorConstraints {
		// Simple heuristic: if sector name contains common geography codes, it's a geography constraint
		// Otherwise, it's an industry constraint
		// In practice, this would be tracked separately
		if len(sc.SectorMapper) > 0 {
			geographyConstraintCount++
		}
	}

	return ConstraintsSummary{
		TotalSecurities:      totalSecurities,
		SecuritiesWithBounds: securitiesWithBounds,
		GeographyConstraints: geographyConstraintCount,
		IndustryConstraints:  len(constraints.SectorConstraints) - geographyConstraintCount,
		TotalMinWeight:       totalMinWeight,
		TotalMaxWeight:       totalMaxWeight,
	}
}

// ValidateConstraints checks if constraints are feasible.
func (cm *ConstraintsManager) ValidateConstraints(constraints Constraints) error {
	// Check if total minimums exceed 100%
	totalMin := 0.0
	for _, isin := range constraints.ISINs { // Use ISINs ✅
		totalMin += constraints.MinWeights[isin]
	}

	if totalMin > 1.0 {
		return fmt.Errorf("total minimum weights %.2f%% exceed 100%%", totalMin*100)
	}

	// Check if each bound is valid (lower <= upper)
	for _, isin := range constraints.ISINs { // Use ISINs ✅
		minWeight := constraints.MinWeights[isin]
		maxWeight := constraints.MaxWeights[isin]
		if minWeight > maxWeight {
			return fmt.Errorf("security %s has invalid bounds: lower=%.4f > upper=%.4f",
				isin, minWeight, maxWeight)
		}
	}

	return nil
}
