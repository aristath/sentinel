package satellites

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestGraduatedReawakening_StartReawakening(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	status := calc.StartReawakening("sat1")

	assert.Equal(t, "sat1", status.BucketID)
	assert.True(t, status.InReawakening)
	assert.Equal(t, 1, status.CurrentStage)
	assert.Equal(t, 0, status.ConsecutiveWins)
	assert.Equal(t, 0.25, status.AggressionMultiplier)
	assert.Equal(t, 0, status.TradesSinceAwakening)
	assert.False(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_CheckStatus_NotInReawakening(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	status := calc.CheckReawakeningStatus("sat1", false, 0, 0, 0)

	assert.False(t, status.InReawakening)
	assert.Equal(t, 4, status.CurrentStage)
	assert.Equal(t, 1.0, status.AggressionMultiplier)
	assert.True(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_CheckStatus_FullyComplete(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Stage 4 = fully complete
	status := calc.CheckReawakeningStatus("sat1", true, 4, 3, 5)

	assert.False(t, status.InReawakening) // Exits reawakening at stage 4
	assert.Equal(t, 4, status.CurrentStage)
	assert.Equal(t, 1.0, status.AggressionMultiplier)
	assert.True(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_CheckStatus_Stage1(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// 0 consecutive wins → stage 1
	status := calc.CheckReawakeningStatus("sat1", true, 1, 0, 2)

	assert.True(t, status.InReawakening)
	assert.Equal(t, 1, status.CurrentStage)
	assert.Equal(t, 0.25, status.AggressionMultiplier)
	assert.False(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_CheckStatus_Stage2(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// 1 consecutive win → stage 2
	status := calc.CheckReawakeningStatus("sat1", true, 2, 1, 3)

	assert.True(t, status.InReawakening)
	assert.Equal(t, 2, status.CurrentStage)
	assert.Equal(t, 0.50, status.AggressionMultiplier)
	assert.False(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_CheckStatus_Stage3(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// 2 consecutive wins → stage 3
	status := calc.CheckReawakeningStatus("sat1", true, 3, 2, 4)

	assert.True(t, status.InReawakening)
	assert.Equal(t, 3, status.CurrentStage)
	assert.Equal(t, 0.75, status.AggressionMultiplier)
	assert.False(t, status.ReadyForFullAggression)
}

func TestGraduatedReawakening_RecordTradeResult_FirstWin(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	initial := calc.StartReawakening("sat1")
	assert.Equal(t, 1, initial.CurrentStage) // Start at 25%

	// Record first win
	afterWin := calc.RecordTradeResult(initial, true)

	assert.True(t, afterWin.InReawakening)
	assert.Equal(t, 2, afterWin.CurrentStage) // Advance to 50%
	assert.Equal(t, 1, afterWin.ConsecutiveWins)
	assert.Equal(t, 0.50, afterWin.AggressionMultiplier)
	assert.Equal(t, 1, afterWin.TradesSinceAwakening)
	assert.False(t, afterWin.ReadyForFullAggression)
}

func TestGraduatedReawakening_RecordTradeResult_SecondWin(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Start at stage 2
	stage2 := ReawakeningStatus{
		BucketID:               "sat1",
		InReawakening:          true,
		CurrentStage:           2,
		ConsecutiveWins:        1,
		AggressionMultiplier:   0.50,
		TradesSinceAwakening:   1,
		ReadyForFullAggression: false,
	}

	// Record second win
	afterWin := calc.RecordTradeResult(stage2, true)

	assert.True(t, afterWin.InReawakening)
	assert.Equal(t, 3, afterWin.CurrentStage) // Advance to 75%
	assert.Equal(t, 2, afterWin.ConsecutiveWins)
	assert.Equal(t, 0.75, afterWin.AggressionMultiplier)
	assert.Equal(t, 2, afterWin.TradesSinceAwakening)
	assert.False(t, afterWin.ReadyForFullAggression)
}

func TestGraduatedReawakening_RecordTradeResult_ThirdWin_FullyReawakened(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Start at stage 3
	stage3 := ReawakeningStatus{
		BucketID:               "sat1",
		InReawakening:          true,
		CurrentStage:           3,
		ConsecutiveWins:        2,
		AggressionMultiplier:   0.75,
		TradesSinceAwakening:   2,
		ReadyForFullAggression: false,
	}

	// Record third win
	afterWin := calc.RecordTradeResult(stage3, true)

	assert.False(t, afterWin.InReawakening) // Fully reawakened!
	assert.Equal(t, 4, afterWin.CurrentStage)
	assert.Equal(t, 3, afterWin.ConsecutiveWins)
	assert.Equal(t, 1.0, afterWin.AggressionMultiplier)
	assert.Equal(t, 3, afterWin.TradesSinceAwakening)
	assert.True(t, afterWin.ReadyForFullAggression)
}

func TestGraduatedReawakening_RecordTradeResult_LossResetsToStage1(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Start at stage 3 (after 2 wins)
	stage3 := ReawakeningStatus{
		BucketID:               "sat1",
		InReawakening:          true,
		CurrentStage:           3,
		ConsecutiveWins:        2,
		AggressionMultiplier:   0.75,
		TradesSinceAwakening:   2,
		ReadyForFullAggression: false,
	}

	// Record loss
	afterLoss := calc.RecordTradeResult(stage3, false)

	assert.True(t, afterLoss.InReawakening)               // Still in reawakening
	assert.Equal(t, 1, afterLoss.CurrentStage)            // Reset to stage 1
	assert.Equal(t, 0, afterLoss.ConsecutiveWins)         // Reset wins
	assert.Equal(t, 0.25, afterLoss.AggressionMultiplier) // Back to 25%
	assert.Equal(t, 3, afterLoss.TradesSinceAwakening)    // Increment trades
	assert.False(t, afterLoss.ReadyForFullAggression)
}

func TestGraduatedReawakening_RecordTradeResult_NotInReawakening(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	notReawakening := ReawakeningStatus{
		BucketID:               "sat1",
		InReawakening:          false,
		CurrentStage:           4,
		ConsecutiveWins:        3,
		AggressionMultiplier:   1.0,
		TradesSinceAwakening:   5,
		ReadyForFullAggression: true,
	}

	// Recording trade result when not in reawakening should return unchanged
	afterTrade := calc.RecordTradeResult(notReawakening, true)

	assert.Equal(t, notReawakening, afterTrade)
}

func TestGraduatedReawakening_ApplyReawakeningToAggression(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Not in reawakening
	notReawakening := ReawakeningStatus{
		InReawakening:        false,
		AggressionMultiplier: 1.0,
	}
	assert.Equal(t, 0.8, calc.ApplyReawakeningToAggression(0.8, notReawakening))

	// Stage 1 (25%)
	stage1 := ReawakeningStatus{
		BucketID:             "sat1",
		InReawakening:        true,
		CurrentStage:         1,
		AggressionMultiplier: 0.25,
	}
	assert.Equal(t, 0.2, calc.ApplyReawakeningToAggression(0.8, stage1))

	// Stage 2 (50%)
	stage2 := ReawakeningStatus{
		BucketID:             "sat1",
		InReawakening:        true,
		CurrentStage:         2,
		AggressionMultiplier: 0.50,
	}
	assert.Equal(t, 0.4, calc.ApplyReawakeningToAggression(0.8, stage2))

	// Stage 3 (75%)
	stage3 := ReawakeningStatus{
		BucketID:             "sat1",
		InReawakening:        true,
		CurrentStage:         3,
		AggressionMultiplier: 0.75,
	}
	assert.InDelta(t, 0.6, calc.ApplyReawakeningToAggression(0.8, stage3), 0.0001)
}

func TestGraduatedReawakening_GetReawakeningDescription(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Not in reawakening, no trades
	notStarted := ReawakeningStatus{
		InReawakening:        false,
		TradesSinceAwakening: 0,
	}
	desc := calc.GetReawakeningDescription(notStarted)
	assert.Equal(t, "Not in re-awakening process", desc)

	// Fully reawakened after trades
	completed := ReawakeningStatus{
		InReawakening:        false,
		ConsecutiveWins:      3,
		TradesSinceAwakening: 5,
	}
	desc = calc.GetReawakeningDescription(completed)
	assert.Contains(t, desc, "Fully re-awakened after 3 consecutive wins (5 trades total)")

	// In reawakening stage 1
	stage1 := ReawakeningStatus{
		BucketID:             "sat1",
		InReawakening:        true,
		CurrentStage:         1,
		ConsecutiveWins:      0,
		AggressionMultiplier: 0.25,
	}
	desc = calc.GetReawakeningDescription(stage1)
	assert.Contains(t, desc, "RE-AWAKENING: Stage 1/4 (25% aggression)")
	assert.Contains(t, desc, "0 consecutive wins so far, need 3 more")
	assert.Contains(t, desc, "Any loss resets to 25%")

	// In reawakening stage 2
	stage2 := ReawakeningStatus{
		BucketID:             "sat1",
		InReawakening:        true,
		CurrentStage:         2,
		ConsecutiveWins:      1,
		AggressionMultiplier: 0.50,
	}
	desc = calc.GetReawakeningDescription(stage2)
	assert.Contains(t, desc, "Stage 2/4 (50% aggression)")
	assert.Contains(t, desc, "1 consecutive wins so far, need 2 more")
}

func TestGraduatedReawakening_FullWorkflow(t *testing.T) {
	calc := NewGraduatedReawakeningCalculator(zerolog.Nop())

	// Start reawakening
	status := calc.StartReawakening("sat1")
	assert.Equal(t, 1, status.CurrentStage)
	assert.Equal(t, 0.25, status.AggressionMultiplier)

	// First win → stage 2
	status = calc.RecordTradeResult(status, true)
	assert.Equal(t, 2, status.CurrentStage)
	assert.Equal(t, 0.50, status.AggressionMultiplier)

	// Loss → reset to stage 1
	status = calc.RecordTradeResult(status, false)
	assert.Equal(t, 1, status.CurrentStage)
	assert.Equal(t, 0.25, status.AggressionMultiplier)

	// Three wins in a row → fully reawakened
	status = calc.RecordTradeResult(status, true) // → stage 2
	status = calc.RecordTradeResult(status, true) // → stage 3
	status = calc.RecordTradeResult(status, true) // → stage 4 (complete)

	assert.False(t, status.InReawakening)
	assert.Equal(t, 4, status.CurrentStage)
	assert.Equal(t, 1.0, status.AggressionMultiplier)
	assert.True(t, status.ReadyForFullAggression)
}
