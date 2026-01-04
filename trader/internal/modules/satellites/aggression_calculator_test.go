package satellites

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestAggressionCalculator_FullyFunded(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 100% of target, no drawdown
	result := calc.CalculateAggression(10000, 10000, nil)

	assert.Equal(t, 1.0, result.Aggression)
	assert.Equal(t, 1.0, result.AllocationAggression)
	assert.Equal(t, 1.0, result.DrawdownAggression)
	assert.Equal(t, "equal", result.LimitingFactor)
	assert.Equal(t, 1.0, result.PctOfTarget)
	assert.Equal(t, 0.0, result.Drawdown)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_OverFunded(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 120% of target
	result := calc.CalculateAggression(12000, 10000, nil)

	assert.Equal(t, 1.0, result.Aggression)
	assert.Equal(t, 1.0, result.AllocationAggression)
	assert.Equal(t, 1.2, result.PctOfTarget)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_ReducedAggression_80Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 85% of target (no drawdown → drawdown aggression = 1.0)
	result := calc.CalculateAggression(8500, 10000, nil)

	assert.Equal(t, 0.8, result.Aggression)
	assert.Equal(t, 0.8, result.AllocationAggression)
	assert.Equal(t, 1.0, result.DrawdownAggression) // No drawdown
	assert.Equal(t, 0.85, result.PctOfTarget)
	assert.Equal(t, "allocation", result.LimitingFactor) // Allocation limits (0.8 < 1.0)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_Conservative_60Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 65% of target
	result := calc.CalculateAggression(6500, 10000, nil)

	assert.Equal(t, 0.6, result.Aggression)
	assert.Equal(t, 0.6, result.AllocationAggression)
	assert.Equal(t, 0.65, result.PctOfTarget)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_VeryConservative_40Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 45% of target
	result := calc.CalculateAggression(4500, 10000, nil)

	assert.Equal(t, 0.4, result.Aggression)
	assert.Equal(t, 0.4, result.AllocationAggression)
	assert.Equal(t, 0.45, result.PctOfTarget)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_Hibernation_Below40Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// At 35% of target (no drawdown → drawdown aggression = 1.0)
	result := calc.CalculateAggression(3500, 10000, nil)

	assert.Equal(t, 0.0, result.Aggression)
	assert.Equal(t, 0.0, result.AllocationAggression) // <40% → hibernation
	assert.Equal(t, 1.0, result.DrawdownAggression)   // No drawdown
	assert.Equal(t, 0.35, result.PctOfTarget)
	assert.Equal(t, "allocation", result.LimitingFactor) // Allocation limits (0.0 < 1.0)
	assert.True(t, result.InHibernation)
}

func TestAggressionCalculator_ModerateDrawdown_15Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 10000.0
	currentValue := 8000.0 // 20% drawdown

	result := calc.CalculateAggression(currentValue, 10000, &hwm)

	assert.Equal(t, 0.7, result.Aggression)           // Limited by drawdown
	assert.Equal(t, 0.8, result.AllocationAggression) // 80% of target
	assert.Equal(t, 0.7, result.DrawdownAggression)   // 20% drawdown → 0.7
	assert.Equal(t, "drawdown", result.LimitingFactor)
	assert.Equal(t, 0.2, result.Drawdown)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_MajorDrawdown_25Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 10000.0
	currentValue := 7000.0 // 30% drawdown

	result := calc.CalculateAggression(currentValue, 10000, &hwm)

	assert.Equal(t, 0.3, result.Aggression)           // Limited by drawdown
	assert.Equal(t, 0.6, result.AllocationAggression) // 70% of target
	assert.Equal(t, 0.3, result.DrawdownAggression)   // 30% drawdown → 0.3
	assert.Equal(t, "drawdown", result.LimitingFactor)
	assert.Equal(t, 0.3, result.Drawdown)
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_SevereDrawdown_35Pct(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 10000.0
	currentValue := 6000.0 // 40% drawdown

	result := calc.CalculateAggression(currentValue, 10000, &hwm)

	assert.Equal(t, 0.0, result.Aggression)           // Hibernation due to severe drawdown
	assert.Equal(t, 0.6, result.AllocationAggression) // 60% of target
	assert.Equal(t, 0.0, result.DrawdownAggression)   // ≥35% drawdown → 0.0
	assert.Equal(t, "drawdown", result.LimitingFactor)
	assert.Equal(t, 0.4, result.Drawdown)
	assert.True(t, result.InHibernation)
}

func TestAggressionCalculator_NoDrawdown_AboveHighWaterMark(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 10000.0
	currentValue := 11000.0 // Above high water mark

	result := calc.CalculateAggression(currentValue, 10000, &hwm)

	assert.Equal(t, 1.0, result.Aggression)
	assert.Equal(t, 0.0, result.Drawdown) // No drawdown when above HWM
	assert.False(t, result.InHibernation)
}

func TestAggressionCalculator_ZeroHighWaterMark(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 0.0

	result := calc.CalculateAggression(5000, 10000, &hwm)

	assert.Equal(t, 0.0, result.Drawdown) // No drawdown calc when HWM = 0
	assert.Equal(t, 1.0, result.DrawdownAggression)
}

func TestAggressionCalculator_ZeroTargetValue(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// Target less than 1 cent
	result := calc.CalculateAggression(5000, 0.005, nil)

	assert.Equal(t, 0.0, result.PctOfTarget)          // Protected against division by zero
	assert.Equal(t, 0.0, result.AllocationAggression) // Hibernation
	assert.True(t, result.InHibernation)
}

func TestAggressionCalculator_LimitingFactorAllocation(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hwm := 10500.0
	// 90% of target (0.8 allocation aggression), ~14% drawdown (1.0 drawdown aggression)
	result := calc.CalculateAggression(9000, 10000, &hwm)

	assert.Equal(t, 0.8, result.Aggression)           // Limited by allocation
	assert.Equal(t, 0.8, result.AllocationAggression) // 90% of target
	assert.Equal(t, 1.0, result.DrawdownAggression)   // <15% drawdown
	assert.Equal(t, "allocation", result.LimitingFactor)
}

func TestAggressionCalculator_ShouldHibernate(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	hibernating := calc.CalculateAggression(3000, 10000, nil)
	assert.True(t, calc.ShouldHibernate(hibernating))

	active := calc.CalculateAggression(8000, 10000, nil)
	assert.False(t, calc.ShouldHibernate(active))
}

func TestAggressionCalculator_ScalePositionSize(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	baseSize := 1000.0

	assert.Equal(t, 1000.0, calc.ScalePositionSize(baseSize, 1.0))
	assert.Equal(t, 800.0, calc.ScalePositionSize(baseSize, 0.8))
	assert.Equal(t, 600.0, calc.ScalePositionSize(baseSize, 0.6))
	assert.Equal(t, 400.0, calc.ScalePositionSize(baseSize, 0.4))
	assert.Equal(t, 0.0, calc.ScalePositionSize(baseSize, 0.0))
}

func TestAggressionCalculator_GetAggressionDescription_Hibernation(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	// Hibernation due to allocation
	result := calc.CalculateAggression(3000, 10000, nil)
	desc := calc.GetAggressionDescription(result)
	assert.Contains(t, desc, "HIBERNATION")
	assert.Contains(t, desc, "30.0% of target")

	// Hibernation due to drawdown
	hwm := 10000.0
	result2 := calc.CalculateAggression(6000, 10000, &hwm)
	desc2 := calc.GetAggressionDescription(result2)
	assert.Contains(t, desc2, "HIBERNATION")
	assert.Contains(t, desc2, "Drawdown at 40.0%")
}

func TestAggressionCalculator_GetAggressionDescription_Active(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	result := calc.CalculateAggression(8500, 10000, nil)
	desc := calc.GetAggressionDescription(result)
	assert.Contains(t, desc, "Funding: 85.0% of target")
	assert.Contains(t, desc, "No drawdown")
	assert.Contains(t, desc, "Aggression: 80%")
}

func TestAggressionCalculator_BoundaryConditions(t *testing.T) {
	calc := NewAggressionCalculator(zerolog.Nop())

	tests := []struct {
		name          string
		currentValue  float64
		targetValue   float64
		highWaterMark *float64
		expectedAgg   float64
	}{
		{
			name:          "Exactly 40% of target (boundary)",
			currentValue:  4000,
			targetValue:   10000,
			highWaterMark: nil,
			expectedAgg:   0.4,
		},
		{
			name:          "Just below 40% of target",
			currentValue:  3999,
			targetValue:   10000,
			highWaterMark: nil,
			expectedAgg:   0.0,
		},
		{
			name:          "Exactly 60% of target (boundary)",
			currentValue:  6000,
			targetValue:   10000,
			highWaterMark: nil,
			expectedAgg:   0.6,
		},
		{
			name:          "Exactly 80% of target (boundary)",
			currentValue:  8000,
			targetValue:   10000,
			highWaterMark: nil,
			expectedAgg:   0.8,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateAggression(tt.currentValue, tt.targetValue, tt.highWaterMark)
			assert.Equal(t, tt.expectedAgg, result.Aggression)
		})
	}
}
