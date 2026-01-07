package symbolic_regression

import (
	"math"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNode_Evaluate_Constant(t *testing.T) {
	node := &Node{
		Type:  NodeTypeConstant,
		Value: 42.0,
	}

	result := node.Evaluate(nil)
	assert.Equal(t, 42.0, result)
}

func TestNode_Evaluate_Variable(t *testing.T) {
	node := &Node{
		Type:     NodeTypeVariable,
		Variable: "cagr",
	}

	variables := map[string]float64{
		"cagr": 0.12,
	}

	result := node.Evaluate(variables)
	assert.Equal(t, 0.12, result)
}

func TestNode_Evaluate_Add(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpAdd,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: 10.0,
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 5.0,
		},
	}

	result := node.Evaluate(nil)
	assert.Equal(t, 15.0, result)
}

func TestNode_Evaluate_Multiply(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpMultiply,
		Left: &Node{
			Type:     NodeTypeVariable,
			Variable: "cagr",
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 2.0,
		},
	}

	variables := map[string]float64{
		"cagr": 0.12,
	}

	result := node.Evaluate(variables)
	assert.Equal(t, 0.24, result)
}

func TestNode_Evaluate_Divide(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpDivide,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: 10.0,
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 2.0,
		},
	}

	result := node.Evaluate(nil)
	assert.Equal(t, 5.0, result)
}

func TestNode_Evaluate_DivideByZero(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpDivide,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: 10.0,
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 0.0,
		},
	}

	result := node.Evaluate(nil)
	// Should return a safe value (1.0) instead of infinity
	assert.True(t, !math.IsInf(result, 0) && !math.IsNaN(result))
}

func TestNode_Evaluate_Sqrt(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpSqrt,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: 16.0,
		},
	}

	result := node.Evaluate(nil)
	assert.InDelta(t, 4.0, result, 0.001)
}

func TestNode_Evaluate_Log(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpLog,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: math.E,
		},
	}

	result := node.Evaluate(nil)
	assert.InDelta(t, 1.0, result, 0.001)
}

func TestNode_Evaluate_LogNegative(t *testing.T) {
	node := &Node{
		Type: NodeTypeOperation,
		Op:   OpLog,
		Left: &Node{
			Type:  NodeTypeConstant,
			Value: -1.0,
		},
	}

	result := node.Evaluate(nil)
	// Should return safe value instead of NaN
	assert.True(t, !math.IsNaN(result))
}

func TestNode_String(t *testing.T) {
	// Formula: (cagr * 2.0) + 0.1
	node := &Node{
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
				Value: 2.0,
			},
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 0.1,
		},
	}

	str := node.String()
	// Should contain the formula representation
	assert.Contains(t, str, "cagr")
}

func TestRandomFormula_GeneratesValidFormula(t *testing.T) {
	variables := []string{"cagr", "score", "regime"}

	formula := RandomFormula(variables, 3, 5) // Max depth 3, max nodes 5

	require.NotNil(t, formula)

	// Should be able to evaluate with test variables
	variablesMap := map[string]float64{
		"cagr":   0.12,
		"score":  0.75,
		"regime": 0.3,
	}

	result := formula.Evaluate(variablesMap)
	assert.True(t, !math.IsNaN(result) && !math.IsInf(result, 0))
}

func TestMutate_ChangesFormula(t *testing.T) {
	original := &Node{
		Type:  NodeTypeConstant,
		Value: 10.0,
	}

	variables := []string{"cagr", "score"}
	mutated := Mutate(original, variables, 0.5) // 50% mutation rate

	require.NotNil(t, mutated)

	// Mutated formula should be different (or same if mutation didn't trigger)
	// Just verify it's valid
	variablesMap := map[string]float64{
		"cagr":  0.12,
		"score": 0.75,
	}

	result := mutated.Evaluate(variablesMap)
	assert.True(t, !math.IsNaN(result) && !math.IsInf(result, 0))
}

func TestCrossover_CombinesFormulas(t *testing.T) {
	formula1 := &Node{
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

	formula2 := &Node{
		Type: NodeTypeOperation,
		Op:   OpMultiply,
		Left: &Node{
			Type:     NodeTypeVariable,
			Variable: "score",
		},
		Right: &Node{
			Type:  NodeTypeConstant,
			Value: 2.0,
		},
	}

	child1, child2 := Crossover(formula1, formula2)

	require.NotNil(t, child1)
	require.NotNil(t, child2)

	// Both children should be valid
	variablesMap := map[string]float64{
		"cagr":  0.12,
		"score": 0.75,
	}

	result1 := child1.Evaluate(variablesMap)
	result2 := child2.Evaluate(variablesMap)

	assert.True(t, !math.IsNaN(result1) && !math.IsInf(result1, 0))
	assert.True(t, !math.IsNaN(result2) && !math.IsInf(result2, 0))
}

func TestCalculateFitness_MAE(t *testing.T) {
	// Formula: cagr (simple identity)
	formula := &Node{
		Type:     NodeTypeVariable,
		Variable: "cagr",
	}

	examples := []TrainingExample{
		{
			Inputs: TrainingInputs{
				CAGR: 0.10,
			},
			TargetReturn: 0.10,
		},
		{
			Inputs: TrainingInputs{
				CAGR: 0.12,
			},
			TargetReturn: 0.12,
		},
		{
			Inputs: TrainingInputs{
				CAGR: 0.08,
			},
			TargetReturn: 0.08,
		},
	}

	fitness := CalculateFitness(formula, examples, FitnessTypeMAE)

	// Perfect match should have very low MAE
	assert.Less(t, fitness, 0.001)
}

func TestCalculateFitness_Spearman(t *testing.T) {
	// Formula: score (simple identity)
	formula := &Node{
		Type:     NodeTypeVariable,
		Variable: "total_score",
	}

	examples := []TrainingExample{
		{
			Inputs: TrainingInputs{
				TotalScore: 0.9,
			},
			TargetReturn: 0.15, // High score -> high return
		},
		{
			Inputs: TrainingInputs{
				TotalScore: 0.7,
			},
			TargetReturn: 0.10,
		},
		{
			Inputs: TrainingInputs{
				TotalScore: 0.5,
			},
			TargetReturn: 0.05, // Low score -> low return
		},
	}

	fitness := CalculateFitness(formula, examples, FitnessTypeSpearman)

	// Fitness is 1.0 - correlation, so lower is better
	// For positive correlation, fitness should be < 1.0
	// For perfect correlation (1.0), fitness would be 0.0
	assert.Less(t, fitness, 1.0, "Fitness should be less than 1.0 for positive correlation")
	assert.GreaterOrEqual(t, fitness, 0.0, "Fitness should be non-negative")
}

func TestCalculateComplexity(t *testing.T) {
	// Simple formula: constant
	simple := &Node{
		Type:  NodeTypeConstant,
		Value: 10.0,
	}

	// Complex formula: (cagr * score) + (regime / 2.0)
	complex := &Node{
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
				Type:     NodeTypeVariable,
				Variable: "score",
			},
		},
		Right: &Node{
			Type: NodeTypeOperation,
			Op:   OpDivide,
			Left: &Node{
				Type:     NodeTypeVariable,
				Variable: "regime",
			},
			Right: &Node{
				Type:  NodeTypeConstant,
				Value: 2.0,
			},
		},
	}

	simpleComplexity := CalculateComplexity(simple)
	complexComplexity := CalculateComplexity(complex)

	assert.Less(t, simpleComplexity, complexComplexity)
}

func TestGetFloatValue(t *testing.T) {
	tests := []struct {
		name     string
		ptr      *float64
		expected float64
	}{
		{"nil pointer", nil, 0.0},
		{"valid pointer", floatPtr(3.14), 3.14},
		{"zero value", floatPtr(0.0), 0.0},
		{"negative value", floatPtr(-5.5), -5.5},
		{"large value", floatPtr(1000.0), 1000.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := getFloatValue(tt.ptr)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetVariableMap(t *testing.T) {
	sharpe := 1.5
	sortino := 2.0
	rsi := 65.0
	maxDrawdown := -0.15

	inputs := TrainingInputs{
		LongTermScore:       0.8,
		FundamentalsScore:   0.7,
		DividendsScore:      0.6,
		OpportunityScore:    0.9,
		ShortTermScore:      0.5,
		TechnicalsScore:     0.75,
		OpinionScore:        0.65,
		DiversificationScore: 0.85,
		TotalScore:          0.75,
		CAGR:                0.12,
		DividendYield:       0.03,
		Volatility:          0.18,
		RegimeScore:         0.3,
		SharpeRatio:         &sharpe,
		SortinoRatio:        &sortino,
		RSI:                 &rsi,
		MaxDrawdown:         &maxDrawdown,
	}

	variables := getVariableMap(inputs)

	assert.Equal(t, 0.8, variables["long_term"])
	assert.Equal(t, 0.7, variables["fundamentals"])
	assert.Equal(t, 0.6, variables["dividends"])
	assert.Equal(t, 0.9, variables["opportunity"])
	assert.Equal(t, 0.5, variables["short_term"])
	assert.Equal(t, 0.75, variables["technicals"])
	assert.Equal(t, 0.65, variables["opinion"])
	assert.Equal(t, 0.85, variables["diversification"])
	assert.Equal(t, 0.75, variables["total_score"])
	assert.Equal(t, 0.12, variables["cagr"])
	assert.Equal(t, 0.03, variables["dividend_yield"])
	assert.Equal(t, 0.18, variables["volatility"])
	assert.Equal(t, 0.3, variables["regime"])
	assert.Equal(t, 1.5, variables["sharpe"])
	assert.Equal(t, 2.0, variables["sortino"])
	assert.Equal(t, 65.0, variables["rsi"])
	assert.Equal(t, -0.15, variables["max_drawdown"])
}

func TestGetVariableMap_NilPointers(t *testing.T) {
	inputs := TrainingInputs{
		TotalScore: 0.75,
		CAGR:       0.12,
		// All pointer fields are nil
	}

	variables := getVariableMap(inputs)

	// Non-pointer fields should be present
	assert.Equal(t, 0.75, variables["total_score"])
	assert.Equal(t, 0.12, variables["cagr"])

	// Pointer fields should default to 0.0
	assert.Equal(t, 0.0, variables["sharpe"])
	assert.Equal(t, 0.0, variables["sortino"])
	assert.Equal(t, 0.0, variables["rsi"])
	assert.Equal(t, 0.0, variables["max_drawdown"])
}

func TestRank(t *testing.T) {
	tests := []struct {
		name     string
		values   []float64
		expected []float64
	}{
		{
			name:     "ascending order",
			values:   []float64{1.0, 2.0, 3.0, 4.0},
			expected: []float64{1.0, 2.0, 3.0, 4.0},
		},
		{
			name:     "descending order",
			values:   []float64{4.0, 3.0, 2.0, 1.0},
			expected: []float64{4.0, 3.0, 2.0, 1.0},
		},
		{
			name:     "mixed order",
			values:   []float64{3.0, 1.0, 4.0, 2.0},
			expected: []float64{3.0, 1.0, 4.0, 2.0},
		},
		{
			name:     "with ties",
			values:   []float64{1.0, 2.0, 2.0, 3.0},
			expected: []float64{1.0, 2.5, 2.5, 4.0}, // Average of ranks 2 and 3
		},
		{
			name:     "all same values",
			values:   []float64{5.0, 5.0, 5.0},
			expected: []float64{2.0, 2.0, 2.0}, // Average of ranks 1, 2, 3 = 2.0
		},
		{
			name:     "single value",
			values:   []float64{10.0},
			expected: []float64{1.0},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := rank(tt.values)
			assert.Equal(t, len(tt.expected), len(result))
			for i := range result {
				assert.InDelta(t, tt.expected[i], result[i], 0.01)
			}
		})
	}
}

func TestPearsonCorrelation(t *testing.T) {
	tests := []struct {
		name     string
		x        []float64
		y        []float64
		expected float64
		tol      float64
	}{
		{
			name:     "perfect positive correlation",
			x:        []float64{1.0, 2.0, 3.0, 4.0},
			y:        []float64{2.0, 4.0, 6.0, 8.0},
			expected: 1.0,
			tol:      0.01,
		},
		{
			name:     "perfect negative correlation",
			x:        []float64{1.0, 2.0, 3.0, 4.0},
			y:        []float64{8.0, 6.0, 4.0, 2.0},
			expected: -1.0,
			tol:      0.01,
		},
		{
			name:     "no correlation",
			x:        []float64{1.0, 2.0, 3.0, 4.0},
			y:        []float64{1.0, 1.0, 1.0, 1.0},
			expected: 0.0,
			tol:      0.01,
		},
		{
			name:     "different lengths",
			x:        []float64{1.0, 2.0},
			y:        []float64{1.0},
			expected: 0.0,
			tol:      0.01,
		},
		{
			name:     "less than 2 values",
			x:        []float64{1.0},
			y:        []float64{2.0},
			expected: 0.0,
			tol:      0.01,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := pearsonCorrelation(tt.x, tt.y)
			assert.InDelta(t, tt.expected, result, tt.tol)
		})
	}
}

func TestSpearmanCorrelation(t *testing.T) {
	tests := []struct {
		name     string
		x        []float64
		y        []float64
		expected float64
		tol      float64
	}{
		{
			name:     "perfect positive correlation",
			x:        []float64{1.0, 2.0, 3.0, 4.0},
			y:        []float64{2.0, 4.0, 6.0, 8.0},
			expected: 1.0,
			tol:      0.01,
		},
		{
			name:     "perfect negative correlation",
			x:        []float64{1.0, 2.0, 3.0, 4.0},
			y:        []float64{4.0, 3.0, 2.0, 1.0},
			expected: -1.0,
			tol:      0.01,
		},
		{
			name:     "with ties",
			x:        []float64{1.0, 2.0, 2.0, 4.0},
			y:        []float64{1.0, 2.0, 3.0, 4.0},
			expected: 0.945, // Approximate with ties
			tol:      0.1,
		},
		{
			name:     "different lengths",
			x:        []float64{1.0, 2.0},
			y:        []float64{1.0},
			expected: 0.0,
			tol:      0.01,
		},
		{
			name:     "less than 2 values",
			x:        []float64{1.0},
			y:        []float64{2.0},
			expected: 0.0,
			tol:      0.01,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := spearmanCorrelation(tt.x, tt.y)
			assert.InDelta(t, tt.expected, result, tt.tol)
		})
	}
}

func TestCalculateMAE(t *testing.T) {
	// Simple formula: returns constant 5.0
	formula := &Node{
		Type:  NodeTypeConstant,
		Value: 5.0,
	}

	examples := []TrainingExample{
		{
			Inputs:      TrainingInputs{TotalScore: 0.5},
			TargetReturn: 5.0,
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.6},
			TargetReturn: 6.0,
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.7},
			TargetReturn: 4.0,
		},
	}

	result := calculateMAE(formula, examples)
	// MAE = (|5-5| + |5-6| + |5-4|) / 3 = (0 + 1 + 1) / 3 = 2/3 ≈ 0.667
	expected := (0.0 + 1.0 + 1.0) / 3.0
	assert.InDelta(t, expected, result, 0.01)
}

func TestCalculateRMSE(t *testing.T) {
	// Simple formula: returns constant 5.0
	formula := &Node{
		Type:  NodeTypeConstant,
		Value: 5.0,
	}

	examples := []TrainingExample{
		{
			Inputs:      TrainingInputs{TotalScore: 0.5},
			TargetReturn: 5.0,
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.6},
			TargetReturn: 6.0,
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.7},
			TargetReturn: 4.0,
		},
	}

	result := calculateRMSE(formula, examples)
	// RMSE = sqrt((0² + 1² + 1²) / 3) = sqrt(2/3) ≈ 0.816
	expected := math.Sqrt((0.0 + 1.0 + 1.0) / 3.0)
	assert.InDelta(t, expected, result, 0.01)
}

func TestCalculateSpearman(t *testing.T) {
	// Formula: returns total_score (simple identity)
	formula := &Node{
		Type:     NodeTypeVariable,
		Variable: "total_score",
	}

	examples := []TrainingExample{
		{
			Inputs:      TrainingInputs{TotalScore: 0.9},
			TargetReturn: 0.15, // High score -> high return
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.7},
			TargetReturn: 0.10,
		},
		{
			Inputs:      TrainingInputs{TotalScore: 0.5},
			TargetReturn: 0.05, // Low score -> low return
		},
	}

	result := calculateSpearman(formula, examples)
	// Spearman returns 1.0 - correlation, so for positive correlation it should be < 1.0
	assert.Less(t, result, 1.0)
	assert.GreaterOrEqual(t, result, 0.0)

	// Test with less than 2 examples (should return 1.0)
	shortExamples := []TrainingExample{
		{
			Inputs:      TrainingInputs{TotalScore: 0.5},
			TargetReturn: 0.05,
		},
	}
	result2 := calculateSpearman(formula, shortExamples)
	assert.Equal(t, 1.0, result2)
}
