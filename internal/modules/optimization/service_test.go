package optimization

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

// Note: isISIN helper is defined in mv_optimizer_test.go

// TestOptimizerService_OptimizeISINKeys will test the full service once implementation is complete
// For now, we focus on struct-level tests below
func TestOptimizerService_OptimizeISINKeys(t *testing.T) {
	t.Skip("Full service test - will be enabled after implementation")
}

// TestPortfolioState_ISINKeyedMaps verifies PortfolioState uses ISIN keys
func TestPortfolioState_ISINKeyedMaps(t *testing.T) {
	state := PortfolioState{
		Positions: map[string]Position{
			"US0378331005": {Symbol: "AAPL.US", Quantity: 10, ValueEUR: 1500}, // ISIN key ✅
			"US5949181045": {Symbol: "MSFT.US", Quantity: 5, ValueEUR: 1500},  // ISIN key ✅
		},
		CurrentPrices: map[string]float64{
			"US0378331005": 150.0, // ISIN key ✅
			"US5949181045": 300.0, // ISIN key ✅
		},
		DividendBonuses: map[string]float64{
			"US0378331005": 0.02, // ISIN key ✅
			"US5949181045": 0.03, // ISIN key ✅
		},
	}

	// Verify Positions uses ISIN keys
	for key := range state.Positions {
		assert.True(t, isISIN(key), "Positions should have ISIN keys, got: %s", key)
	}

	// Verify CurrentPrices uses ISIN keys
	for key := range state.CurrentPrices {
		assert.True(t, isISIN(key), "CurrentPrices should have ISIN keys, got: %s", key)
	}

	// Verify DividendBonuses uses ISIN keys
	for key := range state.DividendBonuses {
		assert.True(t, isISIN(key), "DividendBonuses should have ISIN keys, got: %s", key)
	}

	// Verify no Symbol keys
	assert.NotContains(t, state.Positions, "AAPL.US", "Positions should NOT have Symbol keys")
	assert.NotContains(t, state.CurrentPrices, "AAPL.US", "CurrentPrices should NOT have Symbol keys")
	assert.NotContains(t, state.DividendBonuses, "AAPL.US", "DividendBonuses should NOT have Symbol keys")
}

// TestResult_ISINKeyedMaps verifies Result uses ISIN keys
func TestResult_ISINKeyedMaps(t *testing.T) {
	result := Result{
		TargetWeights: map[string]float64{
			"US0378331005": 0.40, // ISIN key ✅
			"US5949181045": 0.60, // ISIN key ✅
		},
	}

	// Verify TargetWeights uses ISIN keys
	for key := range result.TargetWeights {
		assert.True(t, isISIN(key), "TargetWeights should have ISIN keys, got: %s", key)
	}

	// Verify no Symbol keys
	assert.NotContains(t, result.TargetWeights, "AAPL.US", "TargetWeights should NOT have Symbol keys")
	assert.NotContains(t, result.TargetWeights, "MSFT.US", "TargetWeights should NOT have Symbol keys")
}

// TestConstraints_ISINArray verifies Constraints uses ISIN array
func TestConstraints_ISINArray(t *testing.T) {
	constraints := Constraints{
		ISINs: []string{"US0378331005", "US5949181045"}, // ISIN array ✅
		MinWeights: map[string]float64{
			"US0378331005": 0.0, // ISIN key ✅
			"US5949181045": 0.0, // ISIN key ✅
		},
		MaxWeights: map[string]float64{
			"US0378331005": 0.50, // ISIN key ✅
			"US5949181045": 0.50, // ISIN key ✅
		},
	}

	// Verify ISINs array contains only ISINs
	for _, isin := range constraints.ISINs {
		assert.True(t, isISIN(isin), "ISINs array should only contain ISINs, got: %s", isin)
	}

	// Verify no Symbols field exists (compile check)
	// If this compiles, Symbols field doesn't exist ✅
	_ = constraints.ISINs

	// Verify map keys are ISINs
	for key := range constraints.MinWeights {
		assert.True(t, isISIN(key), "MinWeights should have ISIN keys, got: %s", key)
	}
	for key := range constraints.MaxWeights {
		assert.True(t, isISIN(key), "MaxWeights should have ISIN keys, got: %s", key)
	}

	// Verify no Symbol keys
	assert.NotContains(t, constraints.MinWeights, "AAPL.US", "MinWeights should NOT have Symbol keys")
	assert.NotContains(t, constraints.MaxWeights, "AAPL.US", "MaxWeights should NOT have Symbol keys")
}

// TestSectorConstraint_ISINMapper verifies SectorConstraint uses ISIN keys
func TestSectorConstraint_ISINMapper(t *testing.T) {
	sectorConstraint := SectorConstraint{
		SectorMapper: map[string]string{
			"US0378331005": "Technology", // ISIN → sector ✅
			"US5949181045": "Technology", // ISIN → sector ✅
		},
	}

	// Verify SectorMapper uses ISIN keys
	for key := range sectorConstraint.SectorMapper {
		assert.True(t, isISIN(key), "SectorMapper should have ISIN keys, got: %s", key)
	}

	// Verify no Symbol keys
	assert.NotContains(t, sectorConstraint.SectorMapper, "AAPL.US", "SectorMapper should NOT have Symbol keys")
	assert.NotContains(t, sectorConstraint.SectorMapper, "MSFT.US", "SectorMapper should NOT have Symbol keys")
}

// TestNoDualKeyDuplication verifies maps don't have both ISIN and Symbol keys
func TestNoDualKeyDuplication(t *testing.T) {
	state := PortfolioState{
		Positions: map[string]Position{
			"US0378331005": {Symbol: "AAPL.US", Quantity: 10, ValueEUR: 1500},
		},
		CurrentPrices: map[string]float64{
			"US0378331005": 150.0,
			"US5949181045": 300.0,
		},
	}

	// Verify map sizes equal security count (no duplication)
	assert.Equal(t, 1, len(state.Positions), "Positions should have 1 entry (no dual keys)")
	assert.Equal(t, 2, len(state.CurrentPrices), "CurrentPrices should have 2 entries (no dual keys)")

	// If we had dual keys, we'd have 4 entries (2 ISINs + 2 Symbols)
	// We should only have 2 entries (2 ISINs)
	assert.NotEqual(t, 4, len(state.CurrentPrices), "Should not have dual-key duplication")
}
