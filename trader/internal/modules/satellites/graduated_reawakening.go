package satellites

import (
	"fmt"

	"github.com/rs/zerolog"
)

// ReawakeningStatus represents re-awakening status for a bucket recovering from hibernation
// Faithful translation from Python: app/modules/satellites/domain/graduated_reawakening.py
type ReawakeningStatus struct {
	BucketID               string  `json:"bucket_id"`
	InReawakening          bool    `json:"in_reawakening"`
	CurrentStage           int     `json:"current_stage"` // 0=not started, 1=25%, 2=50%, 3=75%, 4=100%
	ConsecutiveWins        int     `json:"consecutive_wins"`
	AggressionMultiplier   float64 `json:"aggression_multiplier"` // 0.25, 0.5, 0.75, or 1.0
	TradesSinceAwakening   int     `json:"trades_since_awakening"`
	ReadyForFullAggression bool    `json:"ready_for_full_aggression"`
}

// Re-awakening stage multipliers
var reawakeningStages = map[int]float64{
	0: 0.0,  // Hibernating
	1: 0.25, // First stage - 25%
	2: 0.50, // Second stage - 50%
	3: 0.75, // Third stage - 75%
	4: 1.00, // Fully re-awakened
}

// GraduatedReawakeningCalculator manages cautious recovery after hibernation
//
// After a satellite exits hibernation, gradually increase position sizes:
// - First trade: 25% of normal size
// - After win: 50% of normal size
// - After second win: 75% of normal size
// - After third win: 100% (fully re-awakened)
// - Any loss during re-awakening: Reset to 25%
//
// This prevents immediately jumping back to full aggression after a severe
// drawdown, ensuring the strategy proves itself before full capital deployment.
type GraduatedReawakeningCalculator struct {
	log zerolog.Logger
}

// NewGraduatedReawakeningCalculator creates a new graduated reawakening calculator
func NewGraduatedReawakeningCalculator(log zerolog.Logger) *GraduatedReawakeningCalculator {
	return &GraduatedReawakeningCalculator{
		log: log.With().Str("component", "graduated_reawakening").Logger(),
	}
}

// CheckReawakeningStatus checks current re-awakening status
//
// Args:
//
//	bucketID: Bucket ID
//	currentlyInReawakening: Whether bucket is currently in re-awakening
//	currentStage: Current stage (1-4)
//	consecutiveWins: Consecutive wins since awakening
//	tradesSinceAwakening: Total trades since awakening
//
// Returns:
//
//	ReawakeningStatus with current state
func (c *GraduatedReawakeningCalculator) CheckReawakeningStatus(
	bucketID string,
	currentlyInReawakening bool,
	currentStage int,
	consecutiveWins int,
	tradesSinceAwakening int,
) ReawakeningStatus {
	if !currentlyInReawakening || currentStage >= 4 {
		// Not in re-awakening or fully complete
		return ReawakeningStatus{
			BucketID:               bucketID,
			InReawakening:          false,
			CurrentStage:           4,
			ConsecutiveWins:        consecutiveWins,
			AggressionMultiplier:   1.0,
			TradesSinceAwakening:   tradesSinceAwakening,
			ReadyForFullAggression: true,
		}
	}

	// In re-awakening - determine stage based on consecutive wins
	var stage int
	if consecutiveWins >= 3 {
		stage = 4 // Fully re-awakened after 3 wins
	} else if consecutiveWins == 2 {
		stage = 3 // 75% after 2 wins
	} else if consecutiveWins == 1 {
		stage = 2 // 50% after 1 win
	} else {
		stage = 1 // 25% initially or after a loss
	}

	multiplier := reawakeningStages[stage]
	fullyReady := stage >= 4

	c.log.Info().
		Str("bucket_id", bucketID).
		Int("stage", stage).
		Float64("multiplier_pct", multiplier*100).
		Int("consecutive_wins", consecutiveWins).
		Msgf("Re-awakening stage %d/4", stage)

	return ReawakeningStatus{
		BucketID:               bucketID,
		InReawakening:          true,
		CurrentStage:           stage,
		ConsecutiveWins:        consecutiveWins,
		AggressionMultiplier:   multiplier,
		TradesSinceAwakening:   tradesSinceAwakening,
		ReadyForFullAggression: fullyReady,
	}
}

// StartReawakening starts graduated re-awakening process
//
// Called when a bucket exits hibernation.
//
// Args:
//
//	bucketID: Bucket ID
//
// Returns:
//
//	ReawakeningStatus at initial stage (25%)
func (c *GraduatedReawakeningCalculator) StartReawakening(bucketID string) ReawakeningStatus {
	c.log.Warn().
		Str("bucket_id", bucketID).
		Msg("Starting graduated re-awakening - beginning at 25% aggression until proven")

	return ReawakeningStatus{
		BucketID:               bucketID,
		InReawakening:          true,
		CurrentStage:           1,
		ConsecutiveWins:        0,
		AggressionMultiplier:   0.25,
		TradesSinceAwakening:   0,
		ReadyForFullAggression: false,
	}
}

// RecordTradeResult records a trade result and updates re-awakening status
//
// Args:
//
//	currentStatus: Current re-awakening status
//	isWin: Whether the trade was profitable
//
// Returns:
//
//	Updated ReawakeningStatus
func (c *GraduatedReawakeningCalculator) RecordTradeResult(
	currentStatus ReawakeningStatus,
	isWin bool,
) ReawakeningStatus {
	if !currentStatus.InReawakening {
		// Not in re-awakening, nothing to update
		return currentStatus
	}

	trades := currentStatus.TradesSinceAwakening + 1

	if isWin {
		// Increment consecutive wins, advance stage
		wins := currentStatus.ConsecutiveWins + 1

		if wins >= 3 {
			// Fully re-awakened!
			c.log.Info().
				Str("bucket_id", currentStatus.BucketID).
				Msg("FULLY RE-AWAKENED after 3 consecutive wins! Resuming 100% aggression.")

			return ReawakeningStatus{
				BucketID:               currentStatus.BucketID,
				InReawakening:          false,
				CurrentStage:           4,
				ConsecutiveWins:        wins,
				AggressionMultiplier:   1.0,
				TradesSinceAwakening:   trades,
				ReadyForFullAggression: true,
			}
		} else {
			// Advance to next stage
			newStage := wins + 1 // Stage 2 after 1 win, stage 3 after 2 wins
			newMultiplier := reawakeningStages[newStage]

			c.log.Info().
				Str("bucket_id", currentStatus.BucketID).
				Int("new_stage", newStage).
				Float64("new_multiplier_pct", newMultiplier*100).
				Int("consecutive_wins", wins).
				Msgf("Re-awakening progress - advanced to stage %d/4", newStage)

			return ReawakeningStatus{
				BucketID:               currentStatus.BucketID,
				InReawakening:          true,
				CurrentStage:           newStage,
				ConsecutiveWins:        wins,
				AggressionMultiplier:   newMultiplier,
				TradesSinceAwakening:   trades,
				ReadyForFullAggression: false,
			}
		}
	} else {
		// Loss - reset to stage 1 (25%)
		c.log.Warn().
			Str("bucket_id", currentStatus.BucketID).
			Int("previous_stage", currentStatus.CurrentStage).
			Msg("Re-awakening RESET due to loss! Back to 25% aggression")

		return ReawakeningStatus{
			BucketID:               currentStatus.BucketID,
			InReawakening:          true,
			CurrentStage:           1,
			ConsecutiveWins:        0,
			AggressionMultiplier:   0.25,
			TradesSinceAwakening:   trades,
			ReadyForFullAggression: false,
		}
	}
}

// ApplyReawakeningToAggression applies re-awakening multiplier to aggression
//
// Args:
//
//	baseAggression: Base aggression from aggression_calculator
//	reawakeningStatus: Current re-awakening status
//
// Returns:
//
//	Adjusted aggression (reduced if in re-awakening)
func (c *GraduatedReawakeningCalculator) ApplyReawakeningToAggression(
	baseAggression float64,
	reawakeningStatus ReawakeningStatus,
) float64 {
	if !reawakeningStatus.InReawakening {
		return baseAggression
	}

	adjusted := baseAggression * reawakeningStatus.AggressionMultiplier

	c.log.Info().
		Str("bucket_id", reawakeningStatus.BucketID).
		Int("stage", reawakeningStatus.CurrentStage).
		Float64("base_aggression_pct", baseAggression*100).
		Float64("adjusted_aggression_pct", adjusted*100).
		Float64("multiplier_pct", reawakeningStatus.AggressionMultiplier*100).
		Msgf("Re-awakening stage %d/4", reawakeningStatus.CurrentStage)

	return adjusted
}

// GetReawakeningDescription returns human-readable description of re-awakening status
func (c *GraduatedReawakeningCalculator) GetReawakeningDescription(
	reawakeningStatus ReawakeningStatus,
) string {
	if !reawakeningStatus.InReawakening {
		if reawakeningStatus.TradesSinceAwakening > 0 {
			return fmt.Sprintf(
				"Fully re-awakened after %d consecutive wins (%d trades total)",
				reawakeningStatus.ConsecutiveWins,
				reawakeningStatus.TradesSinceAwakening,
			)
		} else {
			return "Not in re-awakening process"
		}
	}

	stage := reawakeningStatus.CurrentStage
	multiplier := reawakeningStatus.AggressionMultiplier
	wins := reawakeningStatus.ConsecutiveWins
	winsNeeded := 3 - wins

	return fmt.Sprintf(
		"RE-AWAKENING: Stage %d/4 (%.0f%% aggression). "+
			"%d consecutive wins so far, need %d more to fully re-awaken. "+
			"Any loss resets to 25%%.",
		stage,
		multiplier*100,
		wins,
		winsNeeded,
	)
}
