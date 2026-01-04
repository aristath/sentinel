package satellites

import (
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// CooldownStatus represents cooldown status for a bucket
// Faithful translation from Python: app/modules/satellites/domain/win_cooldown.py
type CooldownStatus struct {
	BucketID            string   `json:"bucket_id"`
	InCooldown          bool     `json:"in_cooldown"`
	CooldownStart       *string  `json:"cooldown_start"` // ISO timestamp
	CooldownEnd         *string  `json:"cooldown_end"`   // ISO timestamp
	TriggerGain         *float64 `json:"trigger_gain"`   // Gain % that triggered cooldown
	DaysRemaining       int      `json:"days_remaining"`
	AggressionReduction float64  `json:"aggression_reduction"` // Multiplier (e.g., 0.75 for 25% reduction)
}

// WinCooldownCalculator prevents overconfidence after hot streaks
//
// After exceptional gains (>20% in a month), temporarily reduce aggression
// to prevent overleveraging during euphoric periods. Helps enforce discipline
// and avoid giving back gains during market reversals.
type WinCooldownCalculator struct {
	log zerolog.Logger
}

// NewWinCooldownCalculator creates a new win cooldown calculator
func NewWinCooldownCalculator(log zerolog.Logger) *WinCooldownCalculator {
	return &WinCooldownCalculator{
		log: log.With().Str("component", "win_cooldown").Logger(),
	}
}

// CheckWinCooldown checks if bucket should enter or is in win cooldown
//
// Args:
//
//	bucketID: Bucket ID
//	recentReturn: Recent return (e.g., 0.25 for 25%)
//	currentCooldownStart: Existing cooldown start date (if any)
//	cooldownDays: How long cooldown lasts (default 30 days)
//	triggerThreshold: Return threshold to trigger (default 20%)
//	aggressionReduction: How much to reduce aggression (default 25%)
//
// Returns:
//
//	CooldownStatus indicating current state
func (c *WinCooldownCalculator) CheckWinCooldown(
	bucketID string,
	recentReturn float64,
	currentCooldownStart *string,
	cooldownDays int,
	triggerThreshold float64,
	aggressionReduction float64,
) CooldownStatus {
	now := time.Now()

	// Check if already in cooldown
	if currentCooldownStart != nil {
		startDate, err := time.Parse(time.RFC3339, *currentCooldownStart)
		if err != nil {
			c.log.Error().
				Str("bucket_id", bucketID).
				Str("cooldown_start", *currentCooldownStart).
				Err(err).
				Msg("Failed to parse cooldown start date")
			// Return not in cooldown on parse error
			return CooldownStatus{
				BucketID:            bucketID,
				InCooldown:          false,
				CooldownStart:       nil,
				CooldownEnd:         nil,
				TriggerGain:         nil,
				DaysRemaining:       0,
				AggressionReduction: 1.0,
			}
		}

		endDate := startDate.AddDate(0, 0, cooldownDays)

		if now.Before(endDate) {
			daysRemaining := int(endDate.Sub(now).Hours() / 24)
			c.log.Info().
				Str("bucket_id", bucketID).
				Int("days_remaining", daysRemaining).
				Msg("In win cooldown")

			endDateStr := endDate.Format(time.RFC3339)
			return CooldownStatus{
				BucketID:            bucketID,
				InCooldown:          true,
				CooldownStart:       currentCooldownStart,
				CooldownEnd:         &endDateStr,
				TriggerGain:         nil, // Don't know original trigger
				DaysRemaining:       daysRemaining,
				AggressionReduction: 1.0 - aggressionReduction,
			}
		} else {
			// Cooldown expired
			c.log.Info().Str("bucket_id", bucketID).Msg("Win cooldown expired")
			return CooldownStatus{
				BucketID:            bucketID,
				InCooldown:          false,
				CooldownStart:       nil,
				CooldownEnd:         nil,
				TriggerGain:         nil,
				DaysRemaining:       0,
				AggressionReduction: 1.0,
			}
		}
	}

	// Check if should enter cooldown
	if recentReturn >= triggerThreshold {
		cooldownStart := now.Format(time.RFC3339)
		cooldownEnd := now.AddDate(0, 0, cooldownDays).Format(time.RFC3339)

		c.log.Warn().
			Str("bucket_id", bucketID).
			Float64("recent_return_pct", recentReturn*100).
			Float64("threshold_pct", triggerThreshold*100).
			Int("cooldown_days", cooldownDays).
			Msg("Entering win cooldown!")

		triggerGainCopy := recentReturn
		return CooldownStatus{
			BucketID:            bucketID,
			InCooldown:          true,
			CooldownStart:       &cooldownStart,
			CooldownEnd:         &cooldownEnd,
			TriggerGain:         &triggerGainCopy,
			DaysRemaining:       cooldownDays,
			AggressionReduction: 1.0 - aggressionReduction,
		}
	}

	// Not in cooldown and below threshold
	return CooldownStatus{
		BucketID:            bucketID,
		InCooldown:          false,
		CooldownStart:       nil,
		CooldownEnd:         nil,
		TriggerGain:         nil,
		DaysRemaining:       0,
		AggressionReduction: 1.0,
	}
}

// ApplyCooldownToAggression applies cooldown reduction to aggression level
//
// Args:
//
//	baseAggression: Base aggression from aggression_calculator
//	cooldownStatus: Current cooldown status
//
// Returns:
//
//	Adjusted aggression (reduced if in cooldown)
func (c *WinCooldownCalculator) ApplyCooldownToAggression(
	baseAggression float64,
	cooldownStatus CooldownStatus,
) float64 {
	if !cooldownStatus.InCooldown {
		return baseAggression
	}

	// Apply reduction
	adjusted := baseAggression * cooldownStatus.AggressionReduction

	c.log.Info().
		Str("bucket_id", cooldownStatus.BucketID).
		Float64("base_aggression_pct", baseAggression*100).
		Float64("adjusted_aggression_pct", adjusted*100).
		Float64("reduction_pct", (1-cooldownStatus.AggressionReduction)*100).
		Msg("Win cooldown applied")

	return adjusted
}

// CalculateRecentReturn calculates return over a period
//
// Args:
//
//	currentValue: Current bucket value
//	startingValue: Starting bucket value
//
// Returns:
//
//	Return as decimal (e.g., 0.25 for 25%)
func (c *WinCooldownCalculator) CalculateRecentReturn(
	currentValue float64,
	startingValue float64,
) float64 {
	if startingValue <= 0 {
		return 0.0
	}

	return (currentValue - startingValue) / startingValue
}

// GetCooldownDescription returns human-readable description of cooldown status
func (c *WinCooldownCalculator) GetCooldownDescription(cooldownStatus CooldownStatus) string {
	if !cooldownStatus.InCooldown {
		return "No win cooldown active"
	}

	reductionPct := (1 - cooldownStatus.AggressionReduction) * 100

	if cooldownStatus.TriggerGain != nil {
		return fmt.Sprintf(
			"WIN COOLDOWN ACTIVE: Triggered by %.1f%% gain. "+
				"Aggression reduced by %.0f%% for %d more days. "+
				"Prevents overconfidence after hot streak.",
			*cooldownStatus.TriggerGain*100,
			reductionPct,
			cooldownStatus.DaysRemaining,
		)
	} else {
		return fmt.Sprintf(
			"WIN COOLDOWN ACTIVE: Aggression reduced by %.0f%% for %d more days.",
			reductionPct,
			cooldownStatus.DaysRemaining,
		)
	}
}
