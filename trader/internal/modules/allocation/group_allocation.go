package allocation

import (
	"math"
	"sort"
)

// GroupAllocation represents allocation for a single group
type GroupAllocation struct {
	Name         string  `json:"name"`
	TargetPct    float64 `json:"target_pct"`
	CurrentPct   float64 `json:"current_pct"`
	CurrentValue float64 `json:"current_value"`
	Deviation    float64 `json:"deviation"`
}

// CalculateGroupAllocation aggregates allocations by user-defined groups
// Faithful translation of Python logic from app/modules/allocation/api/allocation.py
func CalculateGroupAllocation(
	summary PortfolioSummary,
	countryGroups map[string][]string,
	industryGroups map[string][]string,
	countryGroupTargets map[string]float64,
	industryGroupTargets map[string]float64,
) ([]GroupAllocation, []GroupAllocation) {

	// Build reverse mappings (item -> group)
	countryToGroup := buildReverseMapping(countryGroups)
	industryToGroup := buildReverseMapping(industryGroups)

	// Aggregate values by group
	countryGroupValues := aggregateByGroup(summary.CountryAllocations, countryToGroup)
	industryGroupValues := aggregateByGroup(summary.IndustryAllocations, industryToGroup)

	// Build results
	countryGroupAllocs := buildGroupAllocations(
		countryGroupValues,
		countryGroupTargets,
		summary.TotalValue,
	)
	industryGroupAllocs := buildGroupAllocations(
		industryGroupValues,
		industryGroupTargets,
		summary.TotalValue,
	)

	return countryGroupAllocs, industryGroupAllocs
}

// buildReverseMapping creates a map from item to group name
// e.g., {"North America": ["United States", "Canada"]} -> {"United States": "North America", "Canada": "North America"}
func buildReverseMapping(groups map[string][]string) map[string]string {
	result := make(map[string]string)
	for groupName, items := range groups {
		for _, item := range items {
			result[item] = groupName
		}
	}
	return result
}

// aggregateByGroup sums allocation values by group
func aggregateByGroup(
	allocations []PortfolioAllocation,
	itemToGroup map[string]string,
) map[string]float64 {
	groupValues := make(map[string]float64)

	for _, alloc := range allocations {
		group := itemToGroup[alloc.Name]
		if group == "" {
			group = "OTHER"
		}
		groupValues[group] += alloc.CurrentValue
	}

	return groupValues
}

// buildGroupAllocations creates GroupAllocation structs from group values and targets
func buildGroupAllocations(
	groupValues map[string]float64,
	groupTargets map[string]float64,
	totalValue float64,
) []GroupAllocation {
	// Collect all group names (from both values and targets)
	groupNames := make(map[string]bool)
	for name := range groupValues {
		groupNames[name] = true
	}
	for name := range groupTargets {
		groupNames[name] = true
	}

	// Build allocations
	var allocations []GroupAllocation
	for groupName := range groupNames {
		currentValue := groupValues[groupName]
		targetPct := groupTargets[groupName]

		var currentPct float64
		if totalValue > 0 {
			currentPct = currentValue / totalValue
		}

		allocations = append(allocations, GroupAllocation{
			Name:         groupName,
			TargetPct:    targetPct,
			CurrentPct:   round(currentPct, 4),
			CurrentValue: round(currentValue, 2),
			Deviation:    round(currentPct-targetPct, 4),
		})
	}

	// Sort by name for consistent output
	sort.Slice(allocations, func(i, j int) bool {
		return allocations[i].Name < allocations[j].Name
	})

	return allocations
}

// round rounds a float64 to n decimal places
func round(val float64, decimals int) float64 {
	multiplier := math.Pow(10, float64(decimals))
	return math.Round(val*multiplier) / multiplier
}
