package satellites

import (
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWinCooldown_NoCooldown_BelowThreshold(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	status := calc.CheckWinCooldown(
		"sat1",
		0.15, // 15% return, below 20% threshold
		nil,
		30,
		0.20,
		0.25,
	)

	assert.False(t, status.InCooldown)
	assert.Nil(t, status.CooldownStart)
	assert.Nil(t, status.CooldownEnd)
	assert.Nil(t, status.TriggerGain)
	assert.Equal(t, 0, status.DaysRemaining)
	assert.Equal(t, 1.0, status.AggressionReduction)
}

func TestWinCooldown_EnterCooldown_AboveThreshold(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	status := calc.CheckWinCooldown(
		"sat1",
		0.25, // 25% return, above 20% threshold
		nil,
		30,
		0.20,
		0.25,
	)

	assert.True(t, status.InCooldown)
	assert.NotNil(t, status.CooldownStart)
	assert.NotNil(t, status.CooldownEnd)
	assert.NotNil(t, status.TriggerGain)
	assert.Equal(t, 0.25, *status.TriggerGain)
	assert.Equal(t, 30, status.DaysRemaining)
	assert.Equal(t, 0.75, status.AggressionReduction) // 1.0 - 0.25
}

func TestWinCooldown_AlreadyInCooldown_NotExpired(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Start cooldown 10 days ago
	startTime := time.Now().AddDate(0, 0, -10)
	startStr := startTime.Format(time.RFC3339)

	status := calc.CheckWinCooldown(
		"sat1",
		0.10, // Current return doesn't matter when already in cooldown
		&startStr,
		30,
		0.20,
		0.25,
	)

	assert.True(t, status.InCooldown)
	assert.Equal(t, &startStr, status.CooldownStart)
	assert.NotNil(t, status.CooldownEnd)
	assert.Nil(t, status.TriggerGain)         // Don't know original trigger
	assert.Equal(t, 19, status.DaysRemaining) // ~20 days remaining (30 - 10)
	assert.Equal(t, 0.75, status.AggressionReduction)
}

func TestWinCooldown_AlreadyInCooldown_Expired(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Start cooldown 35 days ago (past 30-day window)
	startTime := time.Now().AddDate(0, 0, -35)
	startStr := startTime.Format(time.RFC3339)

	status := calc.CheckWinCooldown(
		"sat1",
		0.10,
		&startStr,
		30,
		0.20,
		0.25,
	)

	assert.False(t, status.InCooldown) // Expired
	assert.Nil(t, status.CooldownStart)
	assert.Nil(t, status.CooldownEnd)
	assert.Nil(t, status.TriggerGain)
	assert.Equal(t, 0, status.DaysRemaining)
	assert.Equal(t, 1.0, status.AggressionReduction)
}

func TestWinCooldown_InvalidDateFormat(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	invalidDate := "not-a-valid-date"

	status := calc.CheckWinCooldown(
		"sat1",
		0.10,
		&invalidDate,
		30,
		0.20,
		0.25,
	)

	// Should return not in cooldown on parse error
	assert.False(t, status.InCooldown)
	assert.Nil(t, status.CooldownStart)
}

func TestWinCooldown_ApplyCooldownToAggression(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Not in cooldown
	noCooldown := CooldownStatus{
		BucketID:            "sat1",
		InCooldown:          false,
		AggressionReduction: 1.0,
	}
	assert.InDelta(t, 0.8, calc.ApplyCooldownToAggression(0.8, noCooldown), 0.0001)

	// In cooldown
	inCooldown := CooldownStatus{
		BucketID:            "sat1",
		InCooldown:          true,
		AggressionReduction: 0.75, // 25% reduction
	}
	assert.InDelta(t, 0.6, calc.ApplyCooldownToAggression(0.8, inCooldown), 0.0001)
}

func TestWinCooldown_CalculateRecentReturn(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	tests := []struct {
		name           string
		currentValue   float64
		startingValue  float64
		expectedReturn float64
	}{
		{
			name:           "25% gain",
			currentValue:   12500,
			startingValue:  10000,
			expectedReturn: 0.25,
		},
		{
			name:           "10% loss",
			currentValue:   9000,
			startingValue:  10000,
			expectedReturn: -0.10,
		},
		{
			name:           "No change",
			currentValue:   10000,
			startingValue:  10000,
			expectedReturn: 0.0,
		},
		{
			name:           "Zero starting value",
			currentValue:   5000,
			startingValue:  0,
			expectedReturn: 0.0,
		},
		{
			name:           "Negative starting value",
			currentValue:   5000,
			startingValue:  -1000,
			expectedReturn: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := calc.CalculateRecentReturn(tt.currentValue, tt.startingValue)
			assert.InDelta(t, tt.expectedReturn, result, 0.0001)
		})
	}
}

func TestWinCooldown_GetCooldownDescription(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Not in cooldown
	noCooldown := CooldownStatus{
		BucketID:            "sat1",
		InCooldown:          false,
		AggressionReduction: 1.0,
	}
	desc := calc.GetCooldownDescription(noCooldown)
	assert.Equal(t, "No win cooldown active", desc)

	// In cooldown with trigger
	triggerGain := 0.25
	withTrigger := CooldownStatus{
		BucketID:            "sat1",
		InCooldown:          true,
		TriggerGain:         &triggerGain,
		DaysRemaining:       20,
		AggressionReduction: 0.75,
	}
	desc = calc.GetCooldownDescription(withTrigger)
	assert.Contains(t, desc, "WIN COOLDOWN ACTIVE")
	assert.Contains(t, desc, "25.0% gain")
	assert.Contains(t, desc, "25% for 20 more days")

	// In cooldown without trigger
	withoutTrigger := CooldownStatus{
		BucketID:            "sat1",
		InCooldown:          true,
		TriggerGain:         nil,
		DaysRemaining:       15,
		AggressionReduction: 0.75,
	}
	desc = calc.GetCooldownDescription(withoutTrigger)
	assert.Contains(t, desc, "WIN COOLDOWN ACTIVE")
	assert.Contains(t, desc, "25% for 15 more days")
}

func TestWinCooldown_CustomThresholds(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Custom trigger threshold of 15%
	status := calc.CheckWinCooldown(
		"sat1",
		0.18, // 18% return
		nil,
		45,   // 45 days cooldown
		0.15, // 15% threshold
		0.30, // 30% reduction
	)

	assert.True(t, status.InCooldown)
	assert.Equal(t, 45, status.DaysRemaining)
	assert.Equal(t, 0.70, status.AggressionReduction) // 1.0 - 0.30
}

func TestWinCooldown_TimestampParsing(t *testing.T) {
	calc := NewWinCooldownCalculator(zerolog.Nop())

	// Create a cooldown status
	status := calc.CheckWinCooldown(
		"sat1",
		0.25,
		nil,
		30,
		0.20,
		0.25,
	)

	require.NotNil(t, status.CooldownStart)
	require.NotNil(t, status.CooldownEnd)

	// Verify timestamps can be parsed back
	_, err := time.Parse(time.RFC3339, *status.CooldownStart)
	assert.NoError(t, err)

	_, err = time.Parse(time.RFC3339, *status.CooldownEnd)
	assert.NoError(t, err)
}
