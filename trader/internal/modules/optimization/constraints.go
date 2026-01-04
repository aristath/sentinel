package optimization

import (
	"fmt"
	"math"

	"github.com/rs/zerolog"
)

// Constants (from Python scoring module)
const (
	MaxConcentration        = 0.20 // 20% max per security
	MaxCountryConcentration = 0.40 // 40% max per country
	MaxSectorConcentration  = 0.30 // 30% max per industry
	GeoAllocationTolerance  = 0.05 // ±5% from target
	IndAllocationTolerance  = 0.05 // ±5% from target
)

// ConstraintsManager translates business rules into optimization constraints.
type ConstraintsManager struct {
	maxConcentration float64
	geoTolerance     float64
	indTolerance     float64
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

// BuildConstraints builds all constraints for optimization.
func (cm *ConstraintsManager) BuildConstraints(
	securities []Security,
	positions map[string]Position,
	countryTargets map[string]float64,
	industryTargets map[string]float64,
	portfolioValue float64,
	currentPrices map[string]float64,
) (Constraints, error) {
	// Calculate weight bounds for each security
	weightBounds, symbols := cm.calculateWeightBounds(securities, positions, portfolioValue, currentPrices)

	// Build sector constraints
	countryCons, industryCons := cm.buildSectorConstraints(securities, countryTargets, industryTargets)

	// Scale constraints if needed
	countryCons, industryCons = cm.scaleConstraints(countryCons, industryCons)

	constraints := Constraints{
		WeightBounds:      weightBounds,
		SectorConstraints: append(countryCons, industryCons...),
		Symbols:           symbols,
	}

	return constraints, nil
}

// calculateWeightBounds calculates weight bounds for each security.
func (cm *ConstraintsManager) calculateWeightBounds(
	securities []Security,
	positions map[string]Position,
	portfolioValue float64,
	currentPrices map[string]float64,
) ([][2]float64, []string) {
	bounds := make([][2]float64, 0, len(securities))
	symbols := make([]string, 0, len(securities))

	cm.log.Debug().
		Int("num_securities", len(securities)).
		Float64("portfolio_value", portfolioValue).
		Msg("Calculating weight bounds")

	for _, security := range securities {
		symbol := security.Symbol
		position, hasPosition := positions[symbol]
		currentPrice := currentPrices[symbol]

		// Calculate current weight
		var currentWeight float64
		if hasPosition && position.ValueEUR > 0 && portfolioValue > 0 {
			currentWeight = position.ValueEUR / portfolioValue
		}

		// Default bounds
		lower := 0.0
		upper := cm.maxConcentration

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
				Str("symbol", symbol).
				Float64("lower", lower).
				Float64("upper", upper).
				Float64("current_weight", currentWeight).
				Msg("Constraint conflict detected - using current weight for both bounds")
			lower = currentWeight
			upper = currentWeight
		}

		symbols = append(symbols, symbol)
		bounds = append(bounds, [2]float64{lower, upper})
	}

	return bounds, symbols
}

// buildSectorConstraints builds country and industry sector constraints.
func (cm *ConstraintsManager) buildSectorConstraints(
	securities []Security,
	countryTargets map[string]float64,
	industryTargets map[string]float64,
) ([]SectorConstraint, []SectorConstraint) {
	// Group securities by country
	countryGroups := make(map[string][]string)
	for _, security := range securities {
		country := security.Country
		if country == "" {
			country = "OTHER"
		}
		countryGroups[country] = append(countryGroups[country], security.Symbol)
	}

	cm.log.Info().
		Int("num_country_groups", len(countryGroups)).
		Msg("Grouped securities by country")

	// Group securities by industry
	industryGroups := make(map[string][]string)
	for _, security := range securities {
		industry := security.Industry
		if industry == "" {
			industry = "OTHER"
		}
		industryGroups[industry] = append(industryGroups[industry], security.Symbol)
	}

	cm.log.Info().
		Int("num_industry_groups", len(industryGroups)).
		Msg("Grouped securities by industry")

	// Build country constraints
	countryConstraints := make([]SectorConstraint, 0)
	for country, symbols := range countryGroups {
		target := countryTargets[country]
		if target > 0 {
			// Calculate tolerance-based bounds
			toleranceUpper := math.Min(1.0, target+cm.geoTolerance)
			// Enforce hard limit: cap at MaxCountryConcentration
			hardUpper := math.Min(toleranceUpper, MaxCountryConcentration)

			mapper := make(map[string]string)
			for _, symbol := range symbols {
				mapper[symbol] = country
			}

			countryConstraints = append(countryConstraints, SectorConstraint{
				SectorMapper: mapper,
				SectorLower:  map[string]float64{country: math.Max(0.0, target-cm.geoTolerance)},
				SectorUpper:  map[string]float64{country: hardUpper},
			})
		}
	}

	// Scale down country constraint upper bounds if they sum to > 100%
	if len(countryConstraints) > 0 {
		countryMaxSum := 0.0
		for _, c := range countryConstraints {
			for _, upper := range c.SectorUpper {
				countryMaxSum += upper
			}
		}

		if countryMaxSum > 1.0 {
			cm.log.Warn().
				Float64("country_max_sum", countryMaxSum).
				Msg("Country constraint upper bounds sum > 100% - scaling down proportionally")

			scaleFactor := 1.0 / countryMaxSum
			for i := range countryConstraints {
				for name, upper := range countryConstraints[i].SectorUpper {
					newUpper := upper * scaleFactor
					// Ensure upper is still >= lower
					lower := countryConstraints[i].SectorLower[name]
					countryConstraints[i].SectorUpper[name] = math.Max(newUpper, lower)
				}
			}
		}
	}

	// Build industry constraints
	// Count industries with targets
	numIndustryConstraints := 0
	for industry := range industryGroups {
		if industryTargets[industry] > 0 {
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
	for industry, symbols := range industryGroups {
		target := industryTargets[industry]
		if target > 0 {
			// Calculate tolerance-based bounds
			toleranceUpper := math.Min(1.0, target+cm.indTolerance)
			// Enforce hard limit: cap at effectiveMaxConcentration
			hardUpper := math.Min(toleranceUpper, effectiveMaxConcentration)

			mapper := make(map[string]string)
			for _, symbol := range symbols {
				mapper[symbol] = industry
			}

			industryConstraints = append(industryConstraints, SectorConstraint{
				SectorMapper: mapper,
				SectorLower:  map[string]float64{industry: math.Max(0.0, target-cm.indTolerance)},
				SectorUpper:  map[string]float64{industry: hardUpper},
			})
		}
	}

	cm.log.Info().
		Int("country_constraints", len(countryConstraints)).
		Int("industry_constraints", len(industryConstraints)).
		Msg("Built sector constraints")

	return countryConstraints, industryConstraints
}

// scaleConstraints scales down minimums if too restrictive.
func (cm *ConstraintsManager) scaleConstraints(
	countryConstraints []SectorConstraint,
	industryConstraints []SectorConstraint,
) ([]SectorConstraint, []SectorConstraint) {
	// Calculate sums
	indMinSum := 0.0
	for _, c := range industryConstraints {
		for _, lower := range c.SectorLower {
			indMinSum += lower
		}
	}

	countryMinSum := 0.0
	for _, c := range countryConstraints {
		for _, lower := range c.SectorLower {
			countryMinSum += lower
		}
	}

	totalMinSum := countryMinSum + indMinSum

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
		// Scale both country and industry minimums proportionally if combined > 70%
		cm.log.Warn().
			Float64("country_min_sum", countryMinSum).
			Float64("ind_min_sum", indMinSum).
			Float64("total_min_sum", totalMinSum).
			Msg("Combined minimums > 70% - scaling down both proportionally to 60%")

		scaleFactor := 0.60 / totalMinSum
		for i := range countryConstraints {
			for name, lower := range countryConstraints[i].SectorLower {
				newLower := lower * scaleFactor
				upper := countryConstraints[i].SectorUpper[name]
				countryConstraints[i].SectorLower[name] = math.Min(newLower, upper)
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

	return countryConstraints, industryConstraints
}

// GetConstraintSummary generates a summary of constraints for diagnostics.
func (cm *ConstraintsManager) GetConstraintSummary(
	constraints Constraints,
) ConstraintsSummary {
	totalSecurities := len(constraints.WeightBounds)
	securitiesWithBounds := 0
	totalMinWeight := 0.0
	totalMaxWeight := 0.0

	for _, bounds := range constraints.WeightBounds {
		if bounds[0] > 0 || bounds[1] < cm.maxConcentration {
			securitiesWithBounds++
		}
		totalMinWeight += bounds[0]
		totalMaxWeight += bounds[1]
	}

	// Count sector constraints
	countryConstraints := 0
	for _, sc := range constraints.SectorConstraints {
		// Simple heuristic: if sector name contains common country codes, it's a country constraint
		// Otherwise, it's an industry constraint
		// In practice, this would be tracked separately
		if len(sc.SectorMapper) > 0 {
			countryConstraints++
		}
	}

	return ConstraintsSummary{
		TotalSecurities:      totalSecurities,
		SecuritiesWithBounds: securitiesWithBounds,
		CountryConstraints:   countryConstraints,
		IndustryConstraints:  len(constraints.SectorConstraints) - countryConstraints,
		TotalMinWeight:       totalMinWeight,
		TotalMaxWeight:       totalMaxWeight,
	}
}

// ValidateConstraints checks if constraints are feasible.
func (cm *ConstraintsManager) ValidateConstraints(constraints Constraints) error {
	// Check if total minimums exceed 100%
	totalMin := 0.0
	for _, bounds := range constraints.WeightBounds {
		totalMin += bounds[0]
	}

	if totalMin > 1.0 {
		return fmt.Errorf("total minimum weights %.2f%% exceed 100%%", totalMin*100)
	}

	// Check if each bound is valid (lower <= upper)
	for i, bounds := range constraints.WeightBounds {
		if bounds[0] > bounds[1] {
			return fmt.Errorf("security %s has invalid bounds: lower=%.4f > upper=%.4f",
				constraints.Symbols[i], bounds[0], bounds[1])
		}
	}

	return nil
}
