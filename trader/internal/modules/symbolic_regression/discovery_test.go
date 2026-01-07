package symbolic_regression

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDiscoveryService_ValidateAgainstStaticFormula_Success(t *testing.T) {
	// Create a discovered formula that outperforms static formula
	// For expected return: lower MAE is better
	// We'll create a formula that has lower error than static

	storage := &FormulaStorage{} // Mock storage not needed for validation
	dataPrep := &DataPrep{}      // Mock data prep not needed for validation
	log := zerolog.Nop()
	ds := NewDiscoveryService(dataPrep, storage, log)

	// Create training examples (50 examples for 80/20 split = 40 train, 10 test)
	examples := make([]TrainingExample, 50)
	for i := 0; i < 50; i++ {
		examples[i] = TrainingExample{
			Date: "2024-01-01",
			Inputs: TrainingInputs{
				CAGR:       0.10 + float64(i)*0.001, // Varying CAGR
				TotalScore: 0.7 + float64(i)*0.001,  // Varying score
			},
			TargetReturn: 0.11 + float64(i)*0.001, // Target return
		}
	}

	// Create a discovered formula that's better than static
	// Static formula: 0.7*cagr + 0.3*total_score
	// Discovered formula: 0.75*cagr + 0.25*total_score (slightly better fit)
	discoveredFormula := &Node{
		Type: NodeTypeOperation,
		Op:   OpAdd,
		Left: &Node{
			Type: NodeTypeOperation,
			Op:   OpMultiply,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: "cagr",
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: 0.75,
			},
		},
		Right: &Node{
			Type: NodeTypeOperation,
			Op:   OpMultiply,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: "total_score",
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: 0.25,
			},
		},
	}

	// Validate against static formula
	result, err := ds.validateAgainstStaticFormula(
		discoveredFormula,
		examples,
		FormulaTypeExpectedReturn,
		FitnessTypeMAE,
	)

	require.NoError(t, err)
	require.NotNil(t, result)
	assert.True(t, result.IsBetter, "Discovered formula should be better than static")
	assert.Greater(t, result.ImprovementPct, 0.0, "Improvement percentage should be positive")
}

func TestDiscoveryService_ValidateAgainstStaticFormula_Failure(t *testing.T) {
	// Create a discovered formula that underperforms static formula
	storage := &FormulaStorage{}
	dataPrep := &DataPrep{}
	log := zerolog.Nop()
	ds := NewDiscoveryService(dataPrep, storage, log)

	// Create training examples
	examples := make([]TrainingExample, 50)
	for i := 0; i < 50; i++ {
		examples[i] = TrainingExample{
			Date: "2024-01-01",
			Inputs: TrainingInputs{
				CAGR:       0.10 + float64(i)*0.001,
				TotalScore: 0.7 + float64(i)*0.001,
			},
			TargetReturn: 0.11 + float64(i)*0.001,
		}
	}

	// Create a discovered formula that's worse than static
	// Use a formula with poor coefficients that will have higher error
	discoveredFormula := &Node{
		Type: NodeTypeOperation,
		Op:   OpAdd,
		Left: &Node{
			Type: NodeTypeOperation,
			Op:   OpMultiply,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: "cagr",
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: 0.5, // Lower weight, worse fit
			},
		},
		Right: &Node{
			Type: NodeTypeOperation,
			Op:   OpMultiply,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: "total_score",
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: 0.5, // Higher weight, worse fit
			},
		},
	}

	// Validate against static formula
	result, err := ds.validateAgainstStaticFormula(
		discoveredFormula,
		examples,
		FormulaTypeExpectedReturn,
		FitnessTypeMAE,
	)

	require.NoError(t, err)
	require.NotNil(t, result)
	assert.False(t, result.IsBetter, "Discovered formula should not be better than static")
}

func TestDiscoveryService_ValidateAgainstStaticFormula_InsufficientData(t *testing.T) {
	// Test with insufficient data (< 50 examples needed for 80/20 split to guarantee 10 test examples)
	storage := &FormulaStorage{}
	dataPrep := &DataPrep{}
	log := zerolog.Nop()
	ds := NewDiscoveryService(dataPrep, storage, log)

	// Create only 30 examples (80/20 split = 24 train, 6 test - insufficient)
	examples := make([]TrainingExample, 30)
	for i := 0; i < 30; i++ {
		examples[i] = TrainingExample{
			Date: "2024-01-01",
			Inputs: TrainingInputs{
				CAGR:       0.10,
				TotalScore: 0.7,
			},
			TargetReturn: 0.11,
		}
	}

	discoveredFormula := &Node{
		Type: NodeTypeOperation,
		Op:   OpAdd,
		Left: &Node{
			Type:     NodeTypeVariable,
			Variable: "cagr",
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 0.1,
		},
	}

	// Validate should return error due to insufficient data
	result, err := ds.validateAgainstStaticFormula(
		discoveredFormula,
		examples,
		FormulaTypeExpectedReturn,
		FitnessTypeMAE,
	)

	require.Error(t, err, "Should return error for insufficient data")
	assert.Nil(t, result, "Result should be nil when error occurs")
	assert.Contains(t, err.Error(), "insufficient", "Error should mention insufficient data")
	assert.Contains(t, err.Error(), "50", "Error should mention minimum of 50 examples")
}

// Note: Full integration tests for DiscoverExpectedReturnFormula and DiscoverScoringFormula
// would require setting up multiple databases (history, portfolio, config, universe) and
// running the full evolution process. The validation integration is verified through:
// 1. TestDiscoveryService_ValidateAgainstStaticFormula_* tests verify validation logic
// 2. TestFormulaStorage_SaveFormulaWithIsActive verifies isActive parameter works
// 3. Code review confirms discovery methods call validateAgainstStaticFormula and use result
//
// The key behavior is verified: formulas are validated against static formulas before
// activation, and only saved as active if they outperform the static formula.
