package scorers

import "math"

// OpinionScorer calculates analyst opinion score
// Faithful translation from Python: app/modules/scoring/domain/groups/opinion.py
type OpinionScorer struct{}

// OpinionScore represents the result of opinion scoring
type OpinionScore struct {
	Score      float64            `json:"score"`      // Total score (0-1)
	Components map[string]float64 `json:"components"` // Individual component scores
}

// NewOpinionScorer creates a new opinion scorer
func NewOpinionScorer() *OpinionScorer {
	return &OpinionScorer{}
}

// Calculate calculates the opinion score from analyst data
// Components:
// - Analyst Recommendation (60%): Buy/Hold/Sell consensus
// - Price Target (40%): Upside potential
func (os *OpinionScorer) Calculate(
	recommendationScore *float64, // Already normalized 0-1 from analyst ratings
	upsidePct *float64, // Price target upside percentage
) OpinionScore {
	recScore := 0.5
	if recommendationScore != nil {
		recScore = *recommendationScore
	}

	// Target score: 0% upside = 0.5, 20%+ upside = 1.0, -20% = 0.0
	targetScore := 0.5
	if upsidePct != nil {
		upside := *upsidePct / 100 // Convert percentage to decimal
		targetScore = 0.5 + (upside * 2.5)
		targetScore = math.Max(0, math.Min(1, targetScore))
	}

	// Combined (60% recommendation, 40% target)
	totalScore := recScore*0.60 + targetScore*0.40

	return OpinionScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"recommendation": round3(recScore),
			"price_target":   round3(targetScore),
		},
	}
}
