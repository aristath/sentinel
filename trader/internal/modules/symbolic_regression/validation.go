package symbolic_regression

import (
	"fmt"
	"math"
)

// WalkForwardValidation performs walk-forward validation
// Trains on older data, tests on newer data
func WalkForwardValidation(
	formula *Node,
	trainExamples []TrainingExample,
	testExamples []TrainingExample,
	fitnessType FitnessType,
) map[string]float64 {
	metrics := make(map[string]float64)

	// Calculate training metrics
	trainFitness := CalculateFitness(formula, trainExamples, fitnessType)
	metrics["train_mae"] = CalculateFitness(formula, trainExamples, FitnessTypeMAE)
	metrics["train_rmse"] = CalculateFitness(formula, trainExamples, FitnessTypeRMSE)
	metrics["train_fitness"] = trainFitness

	// Calculate test metrics
	testFitness := CalculateFitness(formula, testExamples, fitnessType)
	metrics["test_mae"] = CalculateFitness(formula, testExamples, FitnessTypeMAE)
	metrics["test_rmse"] = CalculateFitness(formula, testExamples, FitnessTypeRMSE)
	metrics["test_fitness"] = testFitness

	// Calculate overfitting metric (difference between train and test)
	metrics["overfitting"] = testFitness - trainFitness

	// Calculate generalization ratio (test/train, lower is better for MAE/RMSE)
	if trainFitness > 0 {
		metrics["generalization_ratio"] = testFitness / trainFitness
	} else {
		metrics["generalization_ratio"] = math.MaxFloat64
	}

	// For Spearman, higher is better, so we want test to be close to train
	if fitnessType == FitnessTypeSpearman {
		// Spearman fitness is 1.0 - correlation, so lower is better
		// Calculate correlation from fitness
		trainCorr := 1.0 - trainFitness
		testCorr := 1.0 - testFitness
		metrics["train_spearman"] = trainCorr
		metrics["test_spearman"] = testCorr
		metrics["spearman_drop"] = trainCorr - testCorr
	}

	return metrics
}

// CompareFormulas compares two formulas on the same dataset
func CompareFormulas(
	formula1 *Node,
	formula2 *Node,
	examples []TrainingExample,
	fitnessType FitnessType,
) map[string]float64 {
	comparison := make(map[string]float64)

	// Calculate fitness for both formulas
	fitness1 := CalculateFitness(formula1, examples, fitnessType)
	fitness2 := CalculateFitness(formula2, examples, fitnessType)

	comparison["formula1_mae"] = CalculateFitness(formula1, examples, FitnessTypeMAE)
	comparison["formula2_mae"] = CalculateFitness(formula2, examples, FitnessTypeMAE)
	comparison["formula1_rmse"] = CalculateFitness(formula1, examples, FitnessTypeRMSE)
	comparison["formula2_rmse"] = CalculateFitness(formula2, examples, FitnessTypeRMSE)
	comparison["formula1_fitness"] = fitness1
	comparison["formula2_fitness"] = fitness2

	// Calculate improvement percentage
	// For MAE/RMSE: lower is better, so improvement = (fitness1 - fitness2) / fitness1
	// For Spearman: higher correlation is better, but fitness is 1.0 - correlation
	if fitnessType == FitnessTypeMAE || fitnessType == FitnessTypeRMSE {
		if fitness1 > 0 {
			improvement := (fitness1 - fitness2) / fitness1 * 100.0
			comparison["improvement_pct"] = improvement
			comparison["better_formula"] = 2.0 // Formula 2 is better if improvement > 0
			if improvement < 0 {
				comparison["better_formula"] = 1.0 // Formula 1 is better
			}
		} else {
			comparison["improvement_pct"] = 0.0
			comparison["better_formula"] = 0.0 // Tie
		}
	} else if fitnessType == FitnessTypeSpearman {
		// For Spearman, fitness is 1.0 - correlation, so lower fitness = better
		if fitness1 > 0 {
			improvement := (fitness1 - fitness2) / fitness1 * 100.0
			comparison["improvement_pct"] = improvement
			comparison["better_formula"] = 2.0
			if improvement < 0 {
				comparison["better_formula"] = 1.0
			}
		} else {
			comparison["improvement_pct"] = 0.0
			comparison["better_formula"] = 0.0
		}
	}

	// Calculate complexity difference
	complexity1 := CalculateComplexity(formula1)
	complexity2 := CalculateComplexity(formula2)
	comparison["formula1_complexity"] = float64(complexity1)
	comparison["formula2_complexity"] = float64(complexity2)
	comparison["complexity_diff"] = float64(complexity2 - complexity1)

	return comparison
}

// ValidateDiscoveredFormula validates a discovered formula against current static formula
func ValidateDiscoveredFormula(
	discoveredFormula *Node,
	staticFormula *Node,
	trainExamples []TrainingExample,
	testExamples []TrainingExample,
	fitnessType FitnessType,
) (*ValidationResult, error) {
	// Walk-forward validation for discovered formula
	discoveredMetrics := WalkForwardValidation(discoveredFormula, trainExamples, testExamples, fitnessType)

	// Walk-forward validation for static formula
	staticMetrics := WalkForwardValidation(staticFormula, trainExamples, testExamples, fitnessType)

	// Compare formulas
	comparison := CompareFormulas(staticFormula, discoveredFormula, testExamples, fitnessType)

	result := &ValidationResult{
		DiscoveredMetrics: discoveredMetrics,
		StaticMetrics:     staticMetrics,
		Comparison:        comparison,
		IsBetter:          false,
	}

	// Determine if discovered formula is better
	// For MAE/RMSE: lower is better
	// For Spearman: higher correlation is better (but fitness is 1.0 - correlation)
	if fitnessType == FitnessTypeMAE || fitnessType == FitnessTypeRMSE {
		discoveredTestFitness := discoveredMetrics["test_fitness"]
		staticTestFitness := staticMetrics["test_fitness"]
		result.IsBetter = discoveredTestFitness < staticTestFitness
		// Calculate improvement percentage, handling division by zero
		if staticTestFitness > 0 {
			result.ImprovementPct = (staticTestFitness - discoveredTestFitness) / staticTestFitness * 100.0
		} else {
			// If static fitness is 0 (perfect), any improvement is infinite
			// Set to 0.0 to indicate improvement can't be calculated
			result.ImprovementPct = 0.0
		}
	} else if fitnessType == FitnessTypeSpearman {
		discoveredTestCorr := discoveredMetrics["test_spearman"]
		staticTestCorr := staticMetrics["test_spearman"]
		result.IsBetter = discoveredTestCorr > staticTestCorr
		if staticTestCorr > 0 {
			result.ImprovementPct = (discoveredTestCorr - staticTestCorr) / staticTestCorr * 100.0
		}
	}

	return result, nil
}

// ValidationResult contains validation results comparing discovered vs static formulas
type ValidationResult struct {
	DiscoveredMetrics map[string]float64
	StaticMetrics     map[string]float64
	Comparison        map[string]float64
	IsBetter          bool
	ImprovementPct    float64
}

// BuildStaticExpectedReturnFormula builds the static expected return formula as a Node
// Static formula: (totalReturnCAGR * cagrWeight) + (targetReturn * scoreFactor * scoreWeight)
// For validation, we'll use a simplified version: cagr * 0.7 + total_score * 0.3
func BuildStaticExpectedReturnFormula() *Node {
	// Simplified static formula: 0.7 * cagr + 0.3 * total_score
	return &Node{
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
				Value: 0.7,
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
				Value: 0.3,
			},
		},
	}
}

// BuildStaticScoringFormula builds the static scoring formula as a Node
// Static formula uses weighted sum of all 8 group scores
// Weights match ScoreWeights in security.go:
//
//	long_term: 0.25, fundamentals: 0.20, dividends: 0.18, opportunity: 0.12,
//	short_term: 0.08, technicals: 0.07, opinion: 0.05, diversification: 0.05
func BuildStaticScoringFormula() *Node {
	// Build weighted sum: 0.25*long_term + 0.20*fundamentals + 0.18*dividends +
	//                     0.12*opportunity + 0.08*short_term + 0.07*technicals +
	//                     0.05*opinion + 0.05*diversification

	// Helper to create weight*variable nodes
	makeWeighted := func(variable string, weight float64) *Node {
		return &Node{
			Type: NodeTypeOperation,
			Op:   OpMultiply,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: variable,
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: weight,
			},
		}
	}

	// Build the sum tree: ((((a+b)+c)+d)+e)+f)+g)+h
	// Start with the first two terms
	root := &Node{
		Type:  NodeTypeOperation,
		Op:    OpAdd,
		Left:  makeWeighted("long_term", 0.25),
		Right: makeWeighted("fundamentals", 0.20),
	}

	// Add remaining terms
	terms := []struct {
		variable string
		weight   float64
	}{
		{"dividends", 0.18},
		{"opportunity", 0.12},
		{"short_term", 0.08},
		{"technicals", 0.07},
		{"opinion", 0.05},
		{"diversification", 0.05},
	}

	for _, term := range terms {
		root = &Node{
			Type:  NodeTypeOperation,
			Op:    OpAdd,
			Left:  root,
			Right: makeWeighted(term.variable, term.weight),
		}
	}

	return root
}

// SplitDataForWalkForward splits data into training and testing sets for walk-forward validation
func SplitDataForWalkForward(
	examples []TrainingExample,
	splitDate string, // YYYY-MM-DD format
) ([]TrainingExample, []TrainingExample, error) {
	var train []TrainingExample
	var test []TrainingExample

	for _, ex := range examples {
		if ex.Date < splitDate {
			train = append(train, ex)
		} else {
			test = append(test, ex)
		}
	}

	if len(train) == 0 {
		return nil, nil, fmt.Errorf("no training examples before split date")
	}
	if len(test) == 0 {
		return nil, nil, fmt.Errorf("no test examples after split date")
	}

	return train, test, nil
}
