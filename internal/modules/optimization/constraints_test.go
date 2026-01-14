package optimization

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestBuildSectorConstraints_SingleGeography(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	securities := []Security{
		{ISIN: "US0000000001", Symbol: "AAPL", Geography: "United States", Industry: "Technology"},
		{ISIN: "US0000000002", Symbol: "MSFT", Geography: "United States", Industry: "Technology"},
		{ISIN: "DE0000000001", Symbol: "SAP", Geography: "Germany", Industry: "Technology"},
	}

	geographyTargets := map[string]float64{
		"United States": 0.6,
		"Germany":       0.4,
	}
	industryTargets := map[string]float64{
		"Technology": 1.0,
	}

	geoCons, indCons := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Verify geography constraints
	assert.NotEmpty(t, geoCons)
	for _, gc := range geoCons {
		// Should have ISINs assigned to single geographies
		for isin, geo := range gc.SectorMapper {
			assert.NotContains(t, geo, ",", "Geography should be a single value, not comma-separated")
			assert.Contains(t, []string{"US0000000001", "US0000000002", "DE0000000001"}, isin)
		}
	}

	// Verify industry constraints
	assert.NotEmpty(t, indCons)
}

func TestBuildSectorConstraints_MultiGeography(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	// Security with multiple geographies (e.g., a global ETF)
	securities := []Security{
		{ISIN: "US0000000001", Symbol: "VT", Geography: "US, Europe, Asia", Industry: "ETF"},
		{ISIN: "US0000000002", Symbol: "SPY", Geography: "US", Industry: "ETF"},
	}

	geographyTargets := map[string]float64{
		"US":     0.5,
		"Europe": 0.3,
		"Asia":   0.2,
	}
	industryTargets := map[string]float64{
		"ETF": 1.0,
	}

	geoCons, _ := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Collect all sector mappers by geography
	geoISINs := make(map[string][]string)
	for _, gc := range geoCons {
		for isin, geo := range gc.SectorMapper {
			geoISINs[geo] = append(geoISINs[geo], isin)
		}
	}

	// VT (US0000000001) should appear in US, Europe, AND Asia groups
	assert.Contains(t, geoISINs["US"], "US0000000001", "VT should be in US group")
	assert.Contains(t, geoISINs["Europe"], "US0000000001", "VT should be in Europe group")
	assert.Contains(t, geoISINs["Asia"], "US0000000001", "VT should be in Asia group")

	// SPY should only be in US
	assert.Contains(t, geoISINs["US"], "US0000000002", "SPY should be in US group")
	assert.NotContains(t, geoISINs["Europe"], "US0000000002", "SPY should NOT be in Europe group")
	assert.NotContains(t, geoISINs["Asia"], "US0000000002", "SPY should NOT be in Asia group")
}

func TestBuildSectorConstraints_MultiIndustry(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	// Security with multiple industries (e.g., a conglomerate)
	securities := []Security{
		{ISIN: "US0000000001", Symbol: "GE", Geography: "US", Industry: "Industrial, Technology, Energy"},
		{ISIN: "US0000000002", Symbol: "XOM", Geography: "US", Industry: "Energy"},
	}

	geographyTargets := map[string]float64{
		"US": 1.0,
	}
	industryTargets := map[string]float64{
		"Industrial": 0.3,
		"Technology": 0.3,
		"Energy":     0.4,
	}

	_, indCons := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Collect all sector mappers by industry
	indISINs := make(map[string][]string)
	for _, ic := range indCons {
		for isin, ind := range ic.SectorMapper {
			indISINs[ind] = append(indISINs[ind], isin)
		}
	}

	// GE (US0000000001) should appear in Industrial, Technology, AND Energy groups
	assert.Contains(t, indISINs["Industrial"], "US0000000001", "GE should be in Industrial group")
	assert.Contains(t, indISINs["Technology"], "US0000000001", "GE should be in Technology group")
	assert.Contains(t, indISINs["Energy"], "US0000000001", "GE should be in Energy group")

	// XOM should only be in Energy
	assert.Contains(t, indISINs["Energy"], "US0000000002", "XOM should be in Energy group")
	assert.NotContains(t, indISINs["Industrial"], "US0000000002", "XOM should NOT be in Industrial group")
	assert.NotContains(t, indISINs["Technology"], "US0000000002", "XOM should NOT be in Technology group")
}

func TestBuildSectorConstraints_EmptyGeographyFallsBackToOther(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	securities := []Security{
		{ISIN: "US0000000001", Symbol: "AAPL", Geography: "US", Industry: "Technology"},
		{ISIN: "US0000000002", Symbol: "XYZ", Geography: "", Industry: "Technology"}, // Empty geography
	}

	geographyTargets := map[string]float64{
		"US":    0.8,
		"OTHER": 0.2,
	}
	industryTargets := map[string]float64{
		"Technology": 1.0,
	}

	geoCons, _ := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Collect all sector mappers by geography
	geoISINs := make(map[string][]string)
	for _, gc := range geoCons {
		for isin, geo := range gc.SectorMapper {
			geoISINs[geo] = append(geoISINs[geo], isin)
		}
	}

	// XYZ should fall back to OTHER
	assert.Contains(t, geoISINs["OTHER"], "US0000000002", "Security with empty geography should be in OTHER group")
}

func TestBuildSectorConstraints_EmptyIndustryFallsBackToOther(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	securities := []Security{
		{ISIN: "US0000000001", Symbol: "AAPL", Geography: "US", Industry: "Technology"},
		{ISIN: "US0000000002", Symbol: "XYZ", Geography: "US", Industry: ""}, // Empty industry
	}

	geographyTargets := map[string]float64{
		"US": 1.0,
	}
	industryTargets := map[string]float64{
		"Technology": 0.8,
		"OTHER":      0.2,
	}

	_, indCons := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Collect all sector mappers by industry
	indISINs := make(map[string][]string)
	for _, ic := range indCons {
		for isin, ind := range ic.SectorMapper {
			indISINs[ind] = append(indISINs[ind], isin)
		}
	}

	// XYZ should fall back to OTHER
	assert.Contains(t, indISINs["OTHER"], "US0000000002", "Security with empty industry should be in OTHER group")
}

func TestBuildSectorConstraints_MixedMultiAndSingle(t *testing.T) {
	cm := NewConstraintsManager(zerolog.Nop())

	securities := []Security{
		{ISIN: "US0000000001", Symbol: "GE", Geography: "US, Europe", Industry: "Industrial, Technology"},
		{ISIN: "US0000000002", Symbol: "AAPL", Geography: "US", Industry: "Technology"},
		{ISIN: "DE0000000001", Symbol: "SAP", Geography: "Europe", Industry: "Technology"},
	}

	geographyTargets := map[string]float64{
		"US":     0.6,
		"Europe": 0.4,
	}
	industryTargets := map[string]float64{
		"Industrial": 0.3,
		"Technology": 0.7,
	}

	geoCons, indCons := cm.buildSectorConstraints(securities, geographyTargets, industryTargets)

	// Collect mappings
	geoISINs := make(map[string][]string)
	for _, gc := range geoCons {
		for isin, geo := range gc.SectorMapper {
			geoISINs[geo] = append(geoISINs[geo], isin)
		}
	}

	indISINs := make(map[string][]string)
	for _, ic := range indCons {
		for isin, ind := range ic.SectorMapper {
			indISINs[ind] = append(indISINs[ind], isin)
		}
	}

	// GE should be in both US and Europe
	assert.Contains(t, geoISINs["US"], "US0000000001")
	assert.Contains(t, geoISINs["Europe"], "US0000000001")

	// AAPL should only be in US
	assert.Contains(t, geoISINs["US"], "US0000000002")
	assert.NotContains(t, geoISINs["Europe"], "US0000000002")

	// SAP should only be in Europe
	assert.Contains(t, geoISINs["Europe"], "DE0000000001")
	assert.NotContains(t, geoISINs["US"], "DE0000000001")

	// GE should be in both Industrial and Technology
	assert.Contains(t, indISINs["Industrial"], "US0000000001")
	assert.Contains(t, indISINs["Technology"], "US0000000001")

	// AAPL should only be in Technology
	assert.Contains(t, indISINs["Technology"], "US0000000002")
	assert.NotContains(t, indISINs["Industrial"], "US0000000002")

	// SAP should only be in Technology
	assert.Contains(t, indISINs["Technology"], "DE0000000001")
	assert.NotContains(t, indISINs["Industrial"], "DE0000000001")
}
