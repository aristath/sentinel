package scheduler

import (
	"time"
)

// TagUpdateFrequency defines the update frequency for a group of tags
type TagUpdateFrequency struct {
	TagIDs      []string
	Frequency   time.Duration
	Description string
}

// TagUpdateFrequencies defines per-tag update frequencies as specified in TAG_BASED_OPTIMIZATION.md
var TagUpdateFrequencies = []TagUpdateFrequency{
	// Very dynamic: 10 minutes (price/technical tags that change intraday)
	{
		TagIDs: []string{
			"oversold", "overbought", "below-ema", "above-ema",
			"bollinger-oversold", "volatility-spike", "near-52w-high",
			"below-52w-high", "valuation-stretch",
			"regime-volatile",
		},
		Frequency:   10 * time.Minute,
		Description: "Price/technical tags",
	},
	// Dynamic: Hourly (opportunity/risk tags that change with market conditions)
	{
		TagIDs: []string{
			"value-opportunity", "deep-value", "undervalued-pe",
			"value-trap", "quality-value",
			"positive-momentum", "recovery-candidate", "overvalued",
			"overweight", "underweight", "concentration-risk",
			"needs-rebalance", "slightly-overweight", "slightly-underweight",
			"unsustainable-gains",
			"regime-sideways-value",
		},
		Frequency:   1 * time.Hour,
		Description: "Opportunity/risk tags",
	},
	// Stable: Daily (quality/characteristic tags that change slowly)
	{
		TagIDs: []string{
			// Quality tags
			"high-quality", "stable", "strong-fundamentals",
			"quality-gate-pass", "quality-gate-fail",
			"consistent-grower",

			// Bubble detection tags
			"bubble-risk", "quality-high-cagr",
			"high-sharpe", "high-sortino", "poor-risk-adjusted",

			// Total return tags
			"high-total-return", "excellent-total-return",
			"dividend-total-return", "moderate-total-return",

			// Dividend tags
			"high-dividend", "dividend-opportunity", "dividend-grower",

			// Score tags
			"high-score", "good-opportunity",

			// Risk tags
			"volatile", "high-volatility", "underperforming", "stagnant",
			"high-drawdown", "low-risk", "medium-risk", "high-risk",

			// Profile tags
			"growth", "value", "dividend-focused", "short-term-opportunity",

			// Regime tags
			"regime-bear-safe", "regime-bull-growth",

			// Optimizer tags
			"target-aligned",
		},
		Frequency:   24 * time.Hour,
		Description: "Quality/characteristic tags",
	},
	// Very stable: Weekly (long-term characteristics that rarely change)
	{
		TagIDs: []string{
			"long-term",
		},
		Frequency:   7 * 24 * time.Hour,
		Description: "Long-term characteristics",
	},
}

// GetTagFrequencyMap creates a map from tag ID to frequency duration
func GetTagFrequencyMap() map[string]time.Duration {
	freqMap := make(map[string]time.Duration)
	for _, freq := range TagUpdateFrequencies {
		for _, tagID := range freq.TagIDs {
			freqMap[tagID] = freq.Frequency
		}
	}
	return freqMap
}

// GetTagsByFrequency returns all tag IDs for a given frequency tier
func GetTagsByFrequency(frequency time.Duration) []string {
	for _, freq := range TagUpdateFrequencies {
		if freq.Frequency == frequency {
			return freq.TagIDs
		}
	}
	return []string{}
}

// GetTagsNeedingUpdate determines which tags need updating based on their frequency
// and last update time. Returns a map of tag IDs that need updating.
func GetTagsNeedingUpdate(
	currentTags map[string]time.Time, // tagID -> last update time
	now time.Time,
) map[string]bool {
	freqMap := GetTagFrequencyMap()
	tagsNeedingUpdate := make(map[string]bool)

	// Check each tag that has a frequency defined
	for tagID, frequency := range freqMap {
		lastUpdate, hasTag := currentTags[tagID]
		if !hasTag {
			// Tag doesn't exist yet - needs to be created
			tagsNeedingUpdate[tagID] = true
		} else {
			// Check if enough time has passed since last update
			timeSinceUpdate := now.Sub(lastUpdate)
			if timeSinceUpdate >= frequency {
				tagsNeedingUpdate[tagID] = true
			}
		}
	}

	return tagsNeedingUpdate
}

