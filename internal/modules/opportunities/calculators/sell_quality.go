// Package calculators provides opportunity identification calculators for portfolio management.
package calculators

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
)

// SellQualityScore represents quality-based prioritization for sell decisions.
// Lower quality = higher priority to sell (protected positions have lower priority).
type SellQualityScore struct {
	// ISIN is the security identifier
	ISIN string

	// Symbol is the trading symbol
	Symbol string

	// QualityScore is the composite quality score (0-1), where higher is better quality
	QualityScore float64

	// StabilityScore is the stability score from context (0-1)
	StabilityScore float64

	// LongTermScore is the long-term score from context (0-1)
	LongTermScore float64

	// HasNegativeTags indicates presence of negative tags (stagnant, underperforming, etc.)
	HasNegativeTags bool

	// IsHighQuality indicates this position should be protected from selling
	IsHighQuality bool

	// SellPriorityBoost is the priority multiplier (>1 = prefer selling, <1 = protect)
	SellPriorityBoost float64
}

// negativeSellTags are tags that indicate a position should be prioritized for selling.
// Positions with these tags have quality issues or performance problems.
var negativeSellTags = []string{
	"stagnant",
	"underperforming",
	"value-trap",
	"ensemble-value-trap",
	"below-minimum-return",
	"unsustainable-gains",
}

// protectedTags are tags that indicate a position should be protected from selling.
// Positions with these tags are high quality and should be kept.
var protectedTags = []string{
	"high-quality",
	"quality-high-cagr",
	"high-stability",
	"consistent-grower",
	"meets-target-return",
	"dividend-grower",
}

// CalculateSellQualityScore computes a quality-based sell priority score for a position.
//
// The algorithm:
// 1. Get stability and long-term scores from context
// 2. Calculate composite quality score (weighted average)
// 3. Check for negative tags (increase sell priority)
// 4. Check for protected tags (decrease sell priority)
// 5. Apply quality-based adjustments
//
// Returns a SellQualityScore with:
//   - SellPriorityBoost > 1.0: position should be prioritized for selling
//   - SellPriorityBoost < 1.0: position should be protected
//   - SellPriorityBoost = 1.0: neutral priority
func CalculateSellQualityScore(
	ctx *domain.OpportunityContext,
	isin string,
	securityTags []string,
	config *domain.PlannerConfiguration,
) SellQualityScore {
	result := SellQualityScore{
		ISIN:              isin,
		SellPriorityBoost: 1.0, // Default: neutral
		QualityScore:      0.5, // Default: neutral
	}

	// Get scores from context
	if ctx != nil {
		if ctx.StabilityScores != nil {
			if score, ok := ctx.StabilityScores[isin]; ok {
				result.StabilityScore = score
			}
		}
		if ctx.LongTermScores != nil {
			if score, ok := ctx.LongTermScores[isin]; ok {
				result.LongTermScore = score
			}
		}
	}

	// Calculate composite quality score
	// Weight stability more heavily (60%) as it indicates consistency
	if result.StabilityScore > 0 || result.LongTermScore > 0 {
		if result.StabilityScore > 0 && result.LongTermScore > 0 {
			result.QualityScore = result.StabilityScore*0.6 + result.LongTermScore*0.4
		} else if result.StabilityScore > 0 {
			result.QualityScore = result.StabilityScore
		} else {
			result.QualityScore = result.LongTermScore
		}
	}

	// Check for negative tags (increase sell priority)
	for _, negTag := range negativeSellTags {
		if containsTag(securityTags, negTag) {
			result.HasNegativeTags = true
			result.SellPriorityBoost *= 1.25 // 25% boost per negative tag
		}
	}

	// Check for protected tags (decrease sell priority, mark as high quality)
	for _, protTag := range protectedTags {
		if containsTag(securityTags, protTag) {
			result.IsHighQuality = true
			result.SellPriorityBoost *= 0.75 // 25% reduction per protected tag
		}
	}

	// Apply quality-based adjustment
	// Low quality (< 0.5) = boost sell priority
	// High quality (> 0.7) = reduce sell priority
	if result.QualityScore > 0 {
		if result.QualityScore < 0.5 {
			// Low quality: boost priority proportionally
			// Score 0.3 → boost of (0.5 - 0.3) = 0.2, multiplier = 1.2
			boost := 1.0 + (0.5 - result.QualityScore)
			result.SellPriorityBoost *= boost
		} else if result.QualityScore > 0.7 {
			// High quality: reduce priority and mark as high quality
			// Score 0.8 → reduction of (0.8 - 0.7) * 0.5 = 0.05, multiplier = 0.95
			reduction := (result.QualityScore - 0.7) * 0.5
			result.SellPriorityBoost *= (1.0 - reduction)
			result.IsHighQuality = true
		}
	}

	return result
}

// containsTag checks if a tag is present in a slice of tags.
func containsTag(tags []string, target string) bool {
	for _, tag := range tags {
		if tag == target {
			return true
		}
	}
	return false
}
