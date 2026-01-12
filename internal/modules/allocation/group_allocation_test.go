package allocation

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBuildMultiGroupMapping(t *testing.T) {
	tests := []struct {
		name     string
		groups   map[string][]string
		expected map[string][]string
	}{
		{
			name: "single group per item",
			groups: map[string][]string{
				"Tech":   {"Technology", "Software"},
				"Health": {"Healthcare", "Pharma"},
			},
			expected: map[string][]string{
				"Technology": {"Tech"},
				"Software":   {"Tech"},
				"Healthcare": {"Health"},
				"Pharma":     {"Health"},
			},
		},
		{
			name: "item in multiple groups",
			groups: map[string][]string{
				"Tech":   {"Technology", "Software"},
				"Growth": {"Technology", "Healthcare"},
			},
			expected: map[string][]string{
				"Technology": {"Tech", "Growth"},
				"Software":   {"Tech"},
				"Healthcare": {"Growth"},
			},
		},
		{
			name:     "empty groups",
			groups:   map[string][]string{},
			expected: map[string][]string{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := buildMultiGroupMapping(tt.groups)

			// Check all expected items are present with correct groups
			for item, expectedGroups := range tt.expected {
				assert.Contains(t, result, item, "result should contain item %s", item)
				assert.ElementsMatch(t, expectedGroups, result[item],
					"item %s should have groups %v, got %v", item, expectedGroups, result[item])
			}

			// Check no unexpected items
			assert.Equal(t, len(tt.expected), len(result),
				"result should have same number of items as expected")
		})
	}
}

func TestAggregateByGroupMulti_SingleGroup(t *testing.T) {
	// Test when each item belongs to exactly one group
	allocations := []PortfolioAllocation{
		{Name: "Technology", CurrentValue: 1000},
		{Name: "Healthcare", CurrentValue: 500},
		{Name: "Finance", CurrentValue: 750},
	}

	itemToGroups := map[string][]string{
		"Technology": {"Tech"},
		"Healthcare": {"Health"},
		"Finance":    {"Financial"},
	}

	result := aggregateByGroupMulti(allocations, itemToGroups)

	assert.Equal(t, 1000.0, result["Tech"], "Tech group should have 1000")
	assert.Equal(t, 500.0, result["Health"], "Health group should have 500")
	assert.Equal(t, 750.0, result["Financial"], "Financial group should have 750")
}

func TestAggregateByGroupMulti_MultipleGroups(t *testing.T) {
	// Test when an item belongs to multiple groups - value should be split equally
	allocations := []PortfolioAllocation{
		{Name: "Technology", CurrentValue: 1000}, // In both Tech and Growth
		{Name: "Healthcare", CurrentValue: 600},  // Only in Health
	}

	itemToGroups := map[string][]string{
		"Technology": {"Tech", "Growth"}, // Split between 2 groups
		"Healthcare": {"Health"},
	}

	result := aggregateByGroupMulti(allocations, itemToGroups)

	// Technology ($1000) should be split 50/50 between Tech and Growth
	assert.Equal(t, 500.0, result["Tech"], "Tech group should get half of Technology's value")
	assert.Equal(t, 500.0, result["Growth"], "Growth group should get half of Technology's value")
	assert.Equal(t, 600.0, result["Health"], "Health group should get full Healthcare value")
}

func TestAggregateByGroupMulti_ThreeGroups(t *testing.T) {
	// Test item in three groups - value split three ways
	allocations := []PortfolioAllocation{
		{Name: "Semiconductors", CurrentValue: 900}, // In Tech, Growth, and Cyclical
	}

	itemToGroups := map[string][]string{
		"Semiconductors": {"Tech", "Growth", "Cyclical"},
	}

	result := aggregateByGroupMulti(allocations, itemToGroups)

	// $900 split three ways = $300 each
	assert.Equal(t, 300.0, result["Tech"], "Tech should get 1/3 of value")
	assert.Equal(t, 300.0, result["Growth"], "Growth should get 1/3 of value")
	assert.Equal(t, 300.0, result["Cyclical"], "Cyclical should get 1/3 of value")
}

func TestAggregateByGroupMulti_UnassignedItem(t *testing.T) {
	// Test item not assigned to any group goes to OTHER
	allocations := []PortfolioAllocation{
		{Name: "Technology", CurrentValue: 1000},
		{Name: "Unknown", CurrentValue: 500}, // Not in any group
	}

	itemToGroups := map[string][]string{
		"Technology": {"Tech"},
		// "Unknown" intentionally not mapped
	}

	result := aggregateByGroupMulti(allocations, itemToGroups)

	assert.Equal(t, 1000.0, result["Tech"], "Tech should have Technology's value")
	assert.Equal(t, 500.0, result["OTHER"], "OTHER should have unassigned item's value")
}

func TestAggregateByGroupMulti_CombinedValues(t *testing.T) {
	// Test that values from multiple items in the same group are summed
	allocations := []PortfolioAllocation{
		{Name: "Technology", CurrentValue: 1000}, // In Tech and Growth
		{Name: "Software", CurrentValue: 400},    // In Tech only
		{Name: "Healthcare", CurrentValue: 600},  // In Growth only
	}

	itemToGroups := map[string][]string{
		"Technology": {"Tech", "Growth"}, // 500 to each
		"Software":   {"Tech"},           // 400 to Tech
		"Healthcare": {"Growth"},         // 600 to Growth
	}

	result := aggregateByGroupMulti(allocations, itemToGroups)

	// Tech: 500 (half of Technology) + 400 (Software) = 900
	assert.Equal(t, 900.0, result["Tech"], "Tech should sum split Technology + full Software")

	// Growth: 500 (half of Technology) + 600 (Healthcare) = 1100
	assert.Equal(t, 1100.0, result["Growth"], "Growth should sum split Technology + full Healthcare")
}

func TestCalculateGroupAllocation_WithMultiGroup(t *testing.T) {
	// Integration test for the full CalculateGroupAllocation function
	summary := PortfolioSummary{
		TotalValue: 10000,
		IndustryAllocations: []PortfolioAllocation{
			{Name: "Technology", CurrentValue: 4000},
			{Name: "Healthcare", CurrentValue: 3000},
			{Name: "Finance", CurrentValue: 3000},
		},
		CountryAllocations: []PortfolioAllocation{
			{Name: "United States", CurrentValue: 7000},
			{Name: "Germany", CurrentValue: 3000},
		},
	}

	// Industry groups with multi-group membership
	industryGroups := map[string][]string{
		"Tech":   {"Technology"},            // Technology only in Tech
		"Growth": {"Technology", "Finance"}, // Technology and Finance in Growth
		"Health": {"Healthcare"},
	}

	// Country groups (single membership)
	countryGroups := map[string][]string{
		"North America": {"United States"},
		"Europe":        {"Germany"},
	}

	industryTargets := map[string]float64{
		"Tech":   0.30,
		"Growth": 0.40,
		"Health": 0.30,
	}

	countryTargets := map[string]float64{
		"North America": 0.70,
		"Europe":        0.30,
	}

	countryAllocs, industryAllocs := CalculateGroupAllocation(
		summary,
		countryGroups,
		industryGroups,
		countryTargets,
		industryTargets,
	)

	// Verify country allocations (single group - no splitting)
	countryMap := make(map[string]GroupAllocation)
	for _, a := range countryAllocs {
		countryMap[a.Name] = a
	}

	assert.Equal(t, 7000.0, countryMap["North America"].CurrentValue)
	assert.Equal(t, 3000.0, countryMap["Europe"].CurrentValue)

	// Verify industry allocations with splitting
	industryMap := make(map[string]GroupAllocation)
	for _, a := range industryAllocs {
		industryMap[a.Name] = a
	}

	// Technology ($4000) is in both Tech and Growth, split 50/50:
	// Tech: 2000 (half of Technology)
	// Growth: 2000 (half of Technology) + 1500 (half of Finance) = 3500
	// Health: 3000 (full Healthcare)
	// Finance is in Growth only, so full 3000... wait, Finance is split too
	// Let me recalculate:
	// - Technology ($4000) in [Tech, Growth] -> $2000 each
	// - Finance ($3000) in [Growth] -> $3000 to Growth
	// - Healthcare ($3000) in [Health] -> $3000 to Health

	// Tech: $2000
	// Growth: $2000 + $3000 = $5000
	// Health: $3000

	assert.Equal(t, 2000.0, industryMap["Tech"].CurrentValue,
		"Tech should have half of Technology's value")
	assert.Equal(t, 5000.0, industryMap["Growth"].CurrentValue,
		"Growth should have half of Technology plus all of Finance")
	assert.Equal(t, 3000.0, industryMap["Health"].CurrentValue,
		"Health should have all of Healthcare")
}
