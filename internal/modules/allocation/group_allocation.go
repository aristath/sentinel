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
// Supports items belonging to multiple groups with proportional value splitting
func CalculateGroupAllocation(
	summary PortfolioSummary,
	countryGroups map[string][]string,
	industryGroups map[string][]string,
	countryGroupTargets map[string]float64,
	industryGroupTargets map[string]float64,
) ([]GroupAllocation, []GroupAllocation) {

	// Build multi-group mappings (item -> []groups)
	countryToGroups := buildMultiGroupMapping(countryGroups)
	industryToGroups := buildMultiGroupMapping(industryGroups)

	// Aggregate values by group (split proportionally if item is in multiple groups)
	countryGroupValues := aggregateByGroupMulti(summary.CountryAllocations, countryToGroups)
	industryGroupValues := aggregateByGroupMulti(summary.IndustryAllocations, industryToGroups)

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

// buildMultiGroupMapping creates a map from item to list of group names
// Supports items belonging to multiple groups
// e.g., {"Tech": ["Technology"], "Growth": ["Technology", "Healthcare"]}
//
//	-> {"Technology": ["Tech", "Growth"], "Healthcare": ["Growth"]}
func buildMultiGroupMapping(groups map[string][]string) map[string][]string {
	result := make(map[string][]string)
	for groupName, items := range groups {
		for _, item := range items {
			result[item] = append(result[item], groupName)
		}
	}
	return result
}

// aggregateByGroupMulti sums allocation values by group
// When an item belongs to multiple groups, its value is split equally among them
func aggregateByGroupMulti(
	allocations []PortfolioAllocation,
	itemToGroups map[string][]string,
) map[string]float64 {
	groupValues := make(map[string]float64)

	for _, alloc := range allocations {
		groups := itemToGroups[alloc.Name]
		if len(groups) == 0 {
			// Item not assigned to any group - count as "OTHER"
			groupValues["OTHER"] += alloc.CurrentValue
			continue
		}

		// Split value proportionally among all groups
		splitValue := alloc.CurrentValue / float64(len(groups))
		for _, group := range groups {
			groupValues[group] += splitValue
		}
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
